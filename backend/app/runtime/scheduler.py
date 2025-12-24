from __future__ import annotations

import asyncio
import json
from typing import Dict, List, Set

from ..analysis import python as py_analysis
from ..analysis import sql as sql_analysis
from ..domain.models import Cell, Notebook
from ..events.bus import EventBus
from ..events.models import SseEvent
from ..graph.dag import DependencyGraph, build_graph
from ..repo.base import NotebookRepository
from .pool_manager import PoolManager
from .python_executor import execute_python
from .sql_executor import execute_sql


class Scheduler:
    """Runs cells reactively and emits events."""

    def __init__(
        self,
        repo: NotebookRepository,
        event_bus: EventBus,
        pool_manager: PoolManager,
    ) -> None:
        self.repo = repo
        self.event_bus = event_bus
        self.pool_manager = pool_manager
        self._python_globals: Dict[str, object] = {"__builtins__": __builtins__}
        self._run_counter = 0
        self._execution_lock = asyncio.Lock()  # Prevents concurrent executions

    async def run_cell(self, cell_id: str) -> int:
        """Execute a cell and all its downstream dependencies reactively.

        Args:
            cell_id: ID of the cell to execute

        Returns:
            Run ID for this execution

        Note:
            This method acquires an execution lock to prevent concurrent runs.
            If a cell fails, only its descendants are skipped, not all downstream cells.
        """
        # Prevent concurrent executions
        async with self._execution_lock:
            self._run_counter += 1
            run_id = self._run_counter

            notebook = await self.repo.get_notebook()

            # Save old defs before re-analysis (for clearing stale variables)
            old_defs: Dict[str, Set[str]] = {cell.id: cell.defs for cell in notebook.cells}

            analyses = self._analyze_cells(notebook.cells)
            await self._persist_analysis(analyses)
            print("[DEBUG] Cell analysis:")
            for cid, cell in analyses.items():
                print(f"  {cid}: defs={cell.defs}, refs={cell.refs}")

            # Build dependency graph - handle errors gracefully
            try:
                graph = build_graph(await self.repo.list_cells())
                impacted = graph.impacted_subgraph(cell_id)
                order = graph.topo_order(impacted)
                print(f"[DEBUG] Cell {cell_id} triggered execution")
                print(f"[DEBUG] Graph adjacency: {graph.adjacency}")
                print(f"[DEBUG] Impacted subgraph: {impacted}")
                print(f"[DEBUG] Execution order: {order}")
            except ValueError as exc:
                # Duplicate definitions or cycle detected
                await self.event_bus.publish(
                    SseEvent(event="run_started", runId=run_id, data={"cellId": cell_id})
                )
                await self._handle_error(
                    cell_id,
                    run_id,
                    f"Dependency error: {exc}\n\nPlease check for:\n"
                    "• Duplicate variable/function definitions across cells\n"
                    "• Circular dependencies between cells",
                )
                await self.event_bus.publish(
                    SseEvent(event="run_finished", runId=run_id, data={"cellId": cell_id})
                )
                return run_id

            await self.event_bus.publish(
                SseEvent(event="run_started", runId=run_id, data={"cellId": cell_id})
            )

            # Track failed cells to skip their descendants
            failed_cells: Set[str] = set()

            for cid in order:
                # Check if any upstream dependency failed
                cell = self._find_cell(notebook.cells, cid)
                upstream_failed = any(
                    failed_cell_id in failed_cells
                    for failed_cell_id in self._get_dependencies(cell, graph)
                )

                if upstream_failed:
                    # Skip this cell because a dependency failed
                    await self.repo.set_cell_status(cell.id, "idle", run_id)
                    continue

                await self.repo.set_cell_status(cell.id, "running", run_id)
                await self.event_bus.publish(
                    SseEvent(
                        event="cell_status",
                        runId=run_id,
                        data={"cellId": cell.id, "status": "running"},
                    )
                )

                if cell.type == "python":
                    # Clear old definitions before re-execution
                    for var_name in old_defs.get(cell.id, set()):
                        self._python_globals.pop(var_name, None)
                        print(f"[DEBUG] Cleared old variable '{var_name}' from cell {cell.id}")
                    await self._execute_python_cell(cell, run_id, failed_cells)
                else:
                    await self._execute_sql_cell(cell, notebook, run_id, failed_cells)

            await self.event_bus.publish(
                SseEvent(event="run_finished", runId=run_id, data={"cellId": cell_id})
            )
            return run_id

    async def _execute_python_cell(
        self, cell: Cell, run_id: int, failed_cells: Set[str]
    ) -> None:
        """Execute a Python cell."""
        result = await execute_python(cell.code, self._python_globals)
        outputs = _compact_outputs(result.stdout, result.stderr)

        if result.error:
            failed_cells.add(cell.id)
            await self._handle_error(cell.id, run_id, result.error)
        else:
            await self.repo.set_cell_outputs(cell.id, outputs)
            await self.repo.set_cell_status(cell.id, "success", run_id)
            await self.event_bus.publish(
                SseEvent(
                    event="cell_output",
                    runId=run_id,
                    data={"cellId": cell.id, "outputs": outputs},
                )
            )
            await self.event_bus.publish(
                SseEvent(
                    event="cell_status",
                    runId=run_id,
                    data={"cellId": cell.id, "status": "success"},
                )
            )

    async def _execute_sql_cell(
        self, cell: Cell, notebook: Notebook, run_id: int, failed_cells: Set[str]
    ) -> None:
        """Execute a SQL cell with variable substitution."""
        settings = notebook.settings
        if not settings.postgres_dsn:
            failed_cells.add(cell.id)
            await self._handle_error(
                cell.id, run_id, "Postgres DSN is not configured."
            )
            return

        # Initialize pool if needed
        if not self.pool_manager.is_initialized:
            try:
                await self.pool_manager.initialize(settings.postgres_dsn)
            except Exception as exc:
                failed_cells.add(cell.id)
                await self._handle_error(
                    cell.id, run_id, f"Failed to initialize connection pool: {exc}"
                )
                return

        pool = self.pool_manager.get_pool()
        result = await execute_sql(pool, cell.code, self._python_globals)

        if result.error:
            failed_cells.add(cell.id)
            await self._handle_error(cell.id, run_id, result.error)
        else:
            # Format output with row count and truncation warning
            output_lines = [_safe_json(result.rows)]
            if result.truncated:
                output_lines.append(
                    f"Results truncated: showing {result.row_count} of many rows"
                )
            else:
                output_lines.append(f"✓ {result.row_count} row(s) returned")

            await self.repo.set_cell_outputs(cell.id, output_lines)
            await self.repo.set_cell_status(cell.id, "success", run_id)
            await self.event_bus.publish(
                SseEvent(
                    event="cell_output",
                    runId=run_id,
                    data={"cellId": cell.id, "outputs": output_lines},
                )
            )
            await self.event_bus.publish(
                SseEvent(
                    event="cell_status",
                    runId=run_id,
                    data={"cellId": cell.id, "status": "success"},
                )
            )

    def _get_dependencies(self, cell: Cell, graph: DependencyGraph) -> List[str]:
        """Get all upstream dependencies of a cell."""
        dependencies: List[str] = []
        for node_id, children in graph.adjacency.items():
            if cell.id in children:
                dependencies.append(node_id)
        return dependencies

    async def _handle_error(self, cell_id: str, run_id: int, message: str) -> None:
        await self.repo.set_cell_error(cell_id, message)
        await self.event_bus.publish(SseEvent(event="cell_error", runId=run_id, data={"cellId": cell_id, "error": message}))
        await self.event_bus.publish(SseEvent(event="cell_status", runId=run_id, data={"cellId": cell_id, "status": "error"}))

    def _analyze_cells(self, cells: List[Cell]) -> Dict[str, Cell]:
        analyzed: Dict[str, Cell] = {}
        for cell in cells:
            if cell.type == "python":
                result = py_analysis.extract_defs_refs(cell.code)
            else:
                result = sql_analysis.extract_defs_refs(cell.code)
            analyzed[cell.id] = cell.model_copy(update={"defs": result.defs, "refs": result.refs})
        return analyzed

    async def _persist_analysis(self, analyzed: Dict[str, Cell]) -> None:
        for cell_id, updated in analyzed.items():
            await self.repo.set_cell_defs_refs(cell_id, updated.defs, updated.refs)

    def _find_cell(self, cells: List[Cell], cell_id: str) -> Cell:
        for cell in cells:
            if cell.id == cell_id:
                return cell
        raise KeyError(f"Cell {cell_id} not found")


def _compact_outputs(stdout: str, stderr: str) -> list[str]:
    outputs: list[str] = []
    if stdout.strip():
        outputs.append(stdout.strip())
    if stderr.strip():
        outputs.append(stderr.strip())
    return outputs


def _safe_json(data: object) -> str:
    try:
        return json.dumps(data, default=str)
    except Exception:
        return str(data)


