"""Bounded reference selection; never accepts arbitrary solver arrays or code."""
from typing import Any, Literal
from pydantic import Field, model_validator
from .execution import ExecutionContract, ExecutionPlan, ExecutionPreference

FWI_REFERENCE_ID = 'deepwave-marmousi1-simple-fwi-bounded-10-v0.0.26-r1'


class FWISelection(ExecutionContract):
    reference_id: Literal['deepwave-marmousi1-simple-fwi-bounded-10-v0.0.26-r1'] = FWI_REFERENCE_ID
    action: Literal['prepare', 'run'] = 'prepare'
    requested_changes: list[str] = Field(default_factory=list, max_length=20)
    conflicts: list[str] = Field(default_factory=list, max_length=20)


class FWIPreviewRequest(ExecutionContract):
    prompt: str | None = Field(default=None, min_length=1, max_length=8000)
    selection: FWISelection | None = None
    preference: ExecutionPreference = Field(default_factory=ExecutionPreference)

    @model_validator(mode='after')
    def exclusive(self):
        if (self.prompt is None) == (self.selection is None):
            raise ValueError('Supply either natural language or a structured selection')
        return self


class FWIPreview(ExecutionContract):
    selection: FWISelection
    preparation_id: str
    runnable: bool
    settings: dict[str, Any]
    model_preview: dict[str, Any]
    execution_plan: ExecutionPlan
    llm: dict[str, Any] | None = None


class FWIResult(ExecutionContract):
    reference_id: Literal['deepwave-marmousi1-simple-fwi-bounded-10-v0.0.26-r1'] = FWI_REFERENCE_ID
    scientific_mode: Literal['modified_experiment'] = 'modified_experiment'
    iterations: int = Field(ge=1, le=10)
    initial_objective: float = Field(ge=0)
    final_objective: float = Field(ge=0)
    loss_history: list[float]
    runtime_seconds: float = Field(ge=0)
    reports: list[str]
