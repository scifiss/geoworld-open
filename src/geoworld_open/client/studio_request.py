"""PUBLIC_STANDARD: a bounded interpretation, not an executable agent plan."""
from typing import Any, Literal

from pydantic import Field
from geoworld_open.client.reference_experiment import ReferenceContract


class StudioRequest(ReferenceContract):
    prompt: str = Field(min_length=1, max_length=8000)
    project_id: str | None = Field(default=None, min_length=1, max_length=128)


class StudioIntent(ReferenceContract):
    operation: Literal["question", "build", "preview", "rtm", "forward", "fwi", "las", "unsupported"]
    dataset: Literal["marmousi1", "marmousi2", "synthetic"] | None = None
    prepare_only: bool = False
    issues: list[str] = Field(default_factory=list, max_length=20)


class StudioDecision(ReferenceContract):
    interpretation: StudioIntent
    route: Literal["ask_question", "build_model", "marmousi_model", "deepwave_reference", "model_rtm", "las_quicklook", "blocked"]
    message: str
    llm: dict[str, Any] | None = None
