"""PUBLIC_STANDARD: measured work progress, not a fabricated job percentage."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class JobProgress(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)
    phase: Literal["preparing", "born", "backward", "rtm_batches", "finalizing"]
    completed: int = Field(ge=0)
    total: int = Field(gt=0)
    unit: Literal["RTM batch"] = "RTM batch"
    elapsed_s: float = Field(ge=0)
    eta_s: float | None = Field(default=None, ge=0)
    # ETA describes the remaining batches, not export/comparison/database work.
    eta_scope: Literal["remaining_rtm_batches"] = "remaining_rtm_batches"
    updated_unix_s: float = Field(ge=0)

    @model_validator(mode="after")
    def bounded(self):
        if self.completed > self.total:
            raise ValueError("Completed work exceeds total work")
        if self.eta_s is not None and (self.completed < 2 or self.completed == self.total):
            raise ValueError("ETA requires at least two completed batches and unfinished work")
        return self
