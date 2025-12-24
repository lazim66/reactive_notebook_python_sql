from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .domain.models import Cell, CellCreateRequest, CellUpdateRequest, Notebook, NotebookSettingsUpdate, RunRequest
from .events.bus import EventBus
from .events.models import SseEvent
from .repo.in_memory import InMemoryNotebookRepository
from .runtime.pool_manager import PoolManager
from .runtime.scheduler import Scheduler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifecycle (startup/shutdown)."""
    # Startup
    yield
    # Shutdown: close connection pool
    if pool_manager.is_initialized:
        await pool_manager.close()


app = FastAPI(title="Reactive Notebook", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize global components
repo = InMemoryNotebookRepository()
event_bus = EventBus()
pool_manager = PoolManager()
scheduler = Scheduler(repo, event_bus, pool_manager)


@app.get("/api/notebook", response_model=Notebook)
async def get_notebook() -> Notebook:
    return await repo.get_notebook()


@app.patch("/api/notebook/settings", response_model=Notebook)
async def update_settings(update: NotebookSettingsUpdate) -> Notebook:
    await repo.update_settings(update)
    notebook = await repo.get_notebook()
    await event_bus.publish(SseEvent(event="notebook_state", data=notebook.model_dump(mode='json', by_alias=True)))
    return notebook


@app.post("/api/notebook/cells", response_model=Cell)
async def add_cell(request: CellCreateRequest) -> Cell:
    cell = await repo.add_cell(request)
    await repo.reorder_cells()
    notebook = await repo.get_notebook()
    await event_bus.publish(SseEvent(event="notebook_state", data=notebook.model_dump(mode='json', by_alias=True)))
    return cell


@app.patch("/api/notebook/cells/{cell_id}", response_model=Cell)
async def update_cell(cell_id: str, request: CellUpdateRequest) -> Cell:
    try:
        cell = await repo.update_cell(cell_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    notebook = await repo.get_notebook()
    await event_bus.publish(SseEvent(event="notebook_state", data=notebook.model_dump(mode='json', by_alias=True)))
    return cell


@app.delete("/api/notebook/cells/{cell_id}")
async def delete_cell(cell_id: str) -> dict:
    """Delete a cell and trigger reactive re-execution of affected cells."""
    # Get the cell before deletion to find its dependents
    try:
        cells = await repo.list_cells()
        cell_to_delete = next((c for c in cells if c.id == cell_id), None)
        if not cell_to_delete:
            raise HTTPException(status_code=404, detail=f"Cell {cell_id} not found")

        # Find cells that depend on this cell's definitions
        from .graph.dag import build_graph

        graph = build_graph(cells)
        affected_cells = graph.adjacency.get(cell_id, set())
        print(f"[DEBUG] Deleting cell {cell_id}")
        print(f"[DEBUG] Cell has defs: {cell_to_delete.defs}, refs: {cell_to_delete.refs}")
        print(f"[DEBUG] Graph adjacency: {graph.adjacency}")
        print(f"[DEBUG] Affected cells: {affected_cells}")

        # Clear Python globals defined by this cell before deletion
        if cell_to_delete.type == "python":
            for var_name in cell_to_delete.defs:
                scheduler._python_globals.pop(var_name, None)
                print(f"[DEBUG] Cleared variable '{var_name}' from Python globals")

        # Delete the cell
        print(f"[DEBUG] About to delete cell from repo")
        await repo.delete_cell(cell_id)
        print(f"[DEBUG] Cell deleted from repo")

        # Notify UI of state change
        print(f"[DEBUG] Getting notebook state")
        notebook = await repo.get_notebook()
        print(f"[DEBUG] Publishing notebook_state event")
        await event_bus.publish(
            SseEvent(event="notebook_state", data=notebook.model_dump(mode='json', by_alias=True))
        )
        print(f"[DEBUG] Event published")

        # Trigger re-execution of affected downstream cells
        # Run them in the background so delete endpoint returns quickly
        if affected_cells:
            print(f"[DEBUG] Creating background task to re-run {len(affected_cells)} cells")
            task = asyncio.create_task(_rerun_affected_cells(list(affected_cells)))
            print(f"[DEBUG] Background task created: {task}")

        return {"ok": True, "affected_cells": len(affected_cells)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


async def _rerun_affected_cells(cell_ids: list[str]) -> None:
    """Re-run affected cells after a deletion."""
    print(f"[DEBUG] _rerun_affected_cells called with {len(cell_ids)} cells: {cell_ids}")
    for cell_id in cell_ids:
        try:
            print(f"[DEBUG] Re-running affected cell: {cell_id}")
            await scheduler.run_cell(cell_id)
        except Exception as exc:
            # Log but don't fail - this is a background task
            print(f"[ERROR] Failed to re-run cell {cell_id}: {exc}")
            import traceback
            traceback.print_exc()


@app.post("/api/notebook/run")
async def run_cell(request: RunRequest) -> dict:
    try:
        run_id = await scheduler.run_cell(request.cell_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"runId": run_id}


@app.get("/api/notebook/events")
async def stream_events(request: Request) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        notebook = await repo.get_notebook()
        yield _format_sse(SseEvent(event="notebook_state", data=notebook.model_dump(mode='json', by_alias=True)))
        async for event in event_bus.stream():
            if await request.is_disconnected():
                break
            yield _format_sse(event)
    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _format_sse(event: SseEvent) -> str:
    data = json.dumps(event.data)
    event_name = event.event
    lines = [f"event: {event_name}", f"data: {data}"]
    if event.run_id is not None:
        lines.insert(1, f"id: {event.run_id}")
    return "\n".join(lines) + "\n\n"


@app.get("/healthz")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/api/notebook/test-connection")
async def test_connection() -> dict:
    """Test the PostgreSQL connection with the configured DSN."""
    notebook = await repo.get_notebook()
    dsn = notebook.settings.postgres_dsn

    if not dsn:
        return {"status": "error", "message": "No DSN configured"}

    try:
        # Try to create a pool and make a simple query
        test_pool = await asyncpg.create_pool(
            dsn,
            min_size=1,
            max_size=1,
            timeout=5.0,
        )
        if test_pool is None:
            return {"status": "error", "message": "Failed to create connection pool"}

        async with test_pool.acquire() as conn:
            # Simple query to test connection
            result = await conn.fetchval("SELECT 1")
            if result != 1:
                await test_pool.close()
                return {"status": "error", "message": "Connection test query failed"}

        await test_pool.close()
        return {"status": "success", "message": "Connected successfully"}

    except asyncpg.InvalidCatalogNameError:
        return {"status": "error", "message": "Database does not exist"}
    except asyncpg.InvalidPasswordError:
        return {"status": "error", "message": "Invalid password"}
    except asyncpg.PostgresConnectionError as exc:
        return {"status": "error", "message": f"Connection failed: {exc}"}
    except Exception as exc:
        return {"status": "error", "message": f"Unexpected error: {exc}"}


