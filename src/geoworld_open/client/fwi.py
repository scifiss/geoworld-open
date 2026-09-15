"""Bounded reference selection; never accepts arbitrary solver arrays or code."""
from typing import Any, Literal
from pydantic import Field, model_validator
from .execution import ExecutionContract, ExecutionPlan, ExecutionPreference
from .intermediate_results import IntermediateResultPolicy

FWI_REFERENCE_ID = 'deepwave-marmousi1-simple-fwi-bounded-10-v0.0.26-r1'
FWI_SIMPLE_250_ID = 'deepwave-marmousi1-simple-fwi-250-memory-adapted-v0.0.26-r1'
FWI_PROGRESSIVE_ID = 'deepwave-marmousi1-progressive-fwi-memory-adapted-v0.0.26-r1'
FWIReferenceId = Literal[
    'deepwave-marmousi1-simple-fwi-bounded-10-v0.0.26-r1',
    'deepwave-marmousi1-simple-fwi-250-memory-adapted-v0.0.26-r1',
    'deepwave-marmousi1-progressive-fwi-memory-adapted-v0.0.26-r1',
]
FWI_UPDATE_TOTALS = {FWI_REFERENCE_ID:10, FWI_SIMPLE_250_ID:250, FWI_PROGRESSIVE_ID:10}
FWI_LABELS = {
    FWI_REFERENCE_ID:'Bounded ten-update simple FWI — Phase 1A reference',
    FWI_SIMPLE_250_ID:'Deepwave simple FWI — 250-update memory-adapted reproduction',
    FWI_PROGRESSIVE_ID:'Deepwave constrained frequency-progressive FWI — memory-adapted reproduction',
}


class FWISelection(ExecutionContract):
    reference_id: FWIReferenceId = FWI_REFERENCE_ID
    action: Literal['prepare', 'run'] = 'prepare'
    requested_changes: list[str] = Field(default_factory=list, max_length=20)
    conflicts: list[str] = Field(default_factory=list, max_length=20)


class FWIPreviewRequest(ExecutionContract):
    prompt: str | None = Field(default=None, min_length=1, max_length=8000)
    selection: FWISelection | None = None
    preference: ExecutionPreference = Field(default_factory=ExecutionPreference)
    intermediate_results: IntermediateResultPolicy = Field(default_factory=IntermediateResultPolicy)

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
    intermediate_results: IntermediateResultPolicy = Field(default_factory=IntermediateResultPolicy)
    snapshot_schedule: list[int] = Field(default_factory=list, max_length=10)


class FWIResult(ExecutionContract):
    reference_id: FWIReferenceId = FWI_REFERENCE_ID
    scientific_mode: Literal['modified_experiment'] = 'modified_experiment'
    iterations: int = Field(ge=1, le=250)
    initial_objective: float = Field(ge=0)
    final_objective: float = Field(ge=0)
    loss_history: list[float]
    runtime_seconds: float = Field(ge=0)
    reports: list[str]
    snapshot_schedule: list[int] = Field(default_factory=list, max_length=10)
    snapshots: list[dict[str, Any]] = Field(default_factory=list, max_length=10)
    initial_velocity_rmse: float | None = Field(default=None, ge=0)
    final_velocity_rmse: float | None = Field(default=None, ge=0)
    closure_evaluations: int = Field(default=0, ge=0)

    @model_validator(mode='after')
    def reference_update_bound(self):
        if self.iterations > FWI_UPDATE_TOTALS[self.reference_id]:
            raise ValueError('Iterations exceed this versioned FWI experiment')
        if any(n < 1 or n > FWI_UPDATE_TOTALS[self.reference_id] for n in self.snapshot_schedule):
            raise ValueError('Snapshot exceeds this versioned FWI experiment')
        return self
