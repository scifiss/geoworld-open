"""PUBLIC_STANDARD: user-seeded, synthetic-only horizon reference V0."""
from typing import Literal

from pydantic import Field, model_validator

from .execution import ExecutionContract


class HorizonTrackRequest(ExecutionContract):
    dataset_id: str = Field(pattern=r"^[0-9a-f]{24}$")
    view_kind: Literal["inline", "crossline"]
    section_number: int
    seed_trace: int = Field(ge=0, le=255)
    seed_time_s: float = Field(ge=0)
    window_start_s: float = Field(ge=0)
    window_stop_s: float = Field(gt=0)
    max_jump_samples: int = Field(default=2, ge=1, le=8)

    @model_validator(mode="after")
    def bounded_window(self):
        if not self.window_start_s <= self.seed_time_s <= self.window_stop_s:
            raise ValueError("Starting time must lie within the selected time window")
        if not 0 < self.window_stop_s - self.window_start_s <= .512:
            raise ValueError("Select an ordered time window no wider than 0.512 seconds")
        return self


class HorizonTrackResult(ExecutionContract):
    request: HorizonTrackRequest
    status: Literal["complete", "partial", "failed"]
    horizontal_coordinates: list[float] = Field(max_length=256)
    picked_time_s: list[float | None] = Field(max_length=256)
    confidence: list[float] = Field(max_length=256)
    failure_reasons: list[str | None] = Field(max_length=256)
    truth_time_s: list[float] = Field(max_length=256)
    errors_ms: list[float | None] = Field(max_length=256)
    metrics: dict[str, float | int | None]
    provenance: dict
    limitations: str = (
        "Synthetic post-stack reference only; user-selected event and window. "
        "Confidence is a waveform similarity score, not a probability. "
        "No automatic interpretation, fault crossing, denoising, or field validation."
    )
