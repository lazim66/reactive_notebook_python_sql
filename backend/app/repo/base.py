from __future__ import annotations

import abc
from typing import Protocol

from ..domain.models import Cell, CellCreateRequest, CellStatus, CellUpdateRequest, Notebook, NotebookSettings, NotebookSettingsUpdate


class NotebookRepository(Protocol):
    @abc.abstractmethod
    async def get_notebook(self) -> Notebook:
        ...

    @abc.abstractmethod
    async def update_settings(self, update: NotebookSettingsUpdate) -> NotebookSettings:
        ...

    @abc.abstractmethod
    async def add_cell(self, request: CellCreateRequest) -> Cell:
        ...

    @abc.abstractmethod
    async def update_cell(self, cell_id: str, request: CellUpdateRequest) -> Cell:
        ...

    @abc.abstractmethod
    async def delete_cell(self, cell_id: str) -> None:
        ...

    @abc.abstractmethod
    async def set_cell_status(self, cell_id: str, status: CellStatus, run_id: int) -> Cell:
        ...

    @abc.abstractmethod
    async def set_cell_outputs(self, cell_id: str, outputs: list[str]) -> Cell:
        ...

    @abc.abstractmethod
    async def set_cell_error(self, cell_id: str, error: str) -> Cell:
        ...

    @abc.abstractmethod
    async def set_cell_defs_refs(self, cell_id: str, defs: set[str], refs: set[str]) -> Cell:
        ...

    @abc.abstractmethod
    async def list_cells(self) -> list[Cell]:
        ...

    @abc.abstractmethod
    async def reorder_cells(self) -> None:
        ...


