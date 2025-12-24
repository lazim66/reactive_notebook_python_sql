from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


EventType = Literal["notebook_state", "run_started", "cell_status", "cell_output", "cell_error", "run_finished"]


class SseEvent(BaseModel):
    event: EventType
    data: Any
    run_id: Optional[int] = Field(default=None, alias="runId")

    class Config:
        populate_by_name = True


