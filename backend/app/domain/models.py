from __future__ import annotations

from typing import Literal, Optional, Set

from pydantic import BaseModel, ConfigDict, Field


CellType = Literal["python", "sql"]
CellStatus = Literal["idle", "running", "success", "error"]


class NotebookSettings(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    postgres_dsn: Optional[str] = Field(default=None, alias="postgresDsn")


class Cell(BaseModel):
    id: str
    type: CellType
    code: str
    order: int
    status: CellStatus = "idle"
    outputs: list[str] = Field(default_factory=list)
    error: Optional[str] = None
    defs: Set[str] = Field(default_factory=set)
    refs: Set[str] = Field(default_factory=set)


class Notebook(BaseModel):
    settings: NotebookSettings
    cells: list[Cell]


class NotebookSettingsUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    postgres_dsn: Optional[str] = Field(default=None, alias="postgresDsn")


class CellCreateRequest(BaseModel):
    type: CellType = "python"
    code: str = ""


class CellUpdateRequest(BaseModel):
    type: Optional[CellType] = None
    code: Optional[str] = None


class RunRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    cell_id: str = Field(alias="cellId")


