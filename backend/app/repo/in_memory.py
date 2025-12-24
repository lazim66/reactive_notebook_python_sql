from __future__ import annotations

import asyncio
import uuid
from typing import Dict

from ..domain.models import Cell, CellCreateRequest, CellStatus, CellUpdateRequest, Notebook, NotebookSettings, NotebookSettingsUpdate
from .base import NotebookRepository


class InMemoryNotebookRepository(NotebookRepository):
    """Single-notebook, in-memory repository for now"""

    def __init__(self) -> None:
        self._settings = NotebookSettings()
        self._cells: list[Cell] = []
        self._lock = asyncio.Lock()

    async def get_notebook(self) -> Notebook:
        async with self._lock:
            return Notebook(settings=self._settings, cells=[cell.model_copy(deep=True) for cell in self._cells])

    async def update_settings(self, update: NotebookSettingsUpdate) -> NotebookSettings:
        async with self._lock:
            data: Dict[str, str | None] = {}
            if update.postgres_dsn is not None:
                data["postgres_dsn"] = update.postgres_dsn
            self._settings = self._settings.model_copy(update=data)
            return self._settings

    async def add_cell(self, request: CellCreateRequest) -> Cell:
        async with self._lock:
            cell = Cell(
                id=str(uuid.uuid4()),
                type=request.type,
                code=request.code,
                order=len(self._cells),
            )
            self._cells.append(cell)
            return cell

    async def update_cell(self, cell_id: str, request: CellUpdateRequest) -> Cell:
        async with self._lock:
            cell = self._get_cell(cell_id)
            updated = cell.model_copy(
                update={
                    "type": request.type or cell.type,
                    "code": request.code if request.code is not None else cell.code,
                }
            )
            self._replace_cell(updated)
            return updated

    async def delete_cell(self, cell_id: str) -> None:
        async with self._lock:
            self._cells = [cell for cell in self._cells if cell.id != cell_id]
            # Reorder inline to avoid deadlock (reorder_cells also acquires lock)
            self._cells = [cell.model_copy(update={"order": idx}) for idx, cell in enumerate(sorted(self._cells, key=lambda c: c.order))]

    async def set_cell_status(self, cell_id: str, status: CellStatus, run_id: int) -> Cell:
        async with self._lock:
            cell = self._get_cell(cell_id)
            updated = cell.model_copy(update={"status": status, "error": None if status != "error" else cell.error})
            self._replace_cell(updated)
            return updated

    async def set_cell_outputs(self, cell_id: str, outputs: list[str]) -> Cell:
        async with self._lock:
            cell = self._get_cell(cell_id)
            updated = cell.model_copy(update={"outputs": outputs, "error": None})
            self._replace_cell(updated)
            return updated

    async def set_cell_error(self, cell_id: str, error: str) -> Cell:
        async with self._lock:
            cell = self._get_cell(cell_id)
            updated = cell.model_copy(update={"error": error, "status": "error"})
            self._replace_cell(updated)
            return updated

    async def set_cell_defs_refs(self, cell_id: str, defs: set[str], refs: set[str]) -> Cell:
        async with self._lock:
            cell = self._get_cell(cell_id)
            updated = cell.model_copy(update={"defs": defs, "refs": refs})
            self._replace_cell(updated)
            return updated

    async def list_cells(self) -> list[Cell]:
        async with self._lock:
            return [cell.model_copy(deep=True) for cell in self._cells]

    async def reorder_cells(self) -> None:
        async with self._lock:
            self._cells = [cell.model_copy(update={"order": idx}) for idx, cell in enumerate(sorted(self._cells, key=lambda c: c.order))]

    def _get_cell(self, cell_id: str) -> Cell:
        for cell in self._cells:
            if cell.id == cell_id:
                return cell
        raise KeyError(f"Cell {cell_id} not found")

    def _replace_cell(self, new_cell: Cell) -> None:
        self._cells = [new_cell if cell.id == new_cell.id else cell for cell in self._cells]


