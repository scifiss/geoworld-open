"""Portable contracts for a conversational scientific experiment draft.

These models describe user intent and deterministic validation state. They do
not authorize numerical execution, select private planner policy, or add a
World Kernel concept.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from .execution import ExecutionContract


ExperimentStatus = Literal[
    "ready",
    "clarification_required",
    "unsupported",
    "prepare_only",
]


class ModelSelection(ExecutionContract):
    dataset: Literal["marmousi1"] = "marmousi1"
    x_start_m: float = Field(default=0.0, ge=0.0, le=17_000.0)
    x_stop_m: float = Field(default=2396.0, gt=0.0, le=17_000.0)
    z_start_m: float = Field(default=0.0, ge=0.0, le=3500.0)
    z_stop_m: float = Field(default=996.0, gt=0.0, le=3500.0)

    @model_validator(mode="after")
    def ordered_bounds(self):
        if self.x_start_m >= self.x_stop_m or self.z_start_m >= self.z_stop_m:
            raise ValueError("Model bounds must have increasing metre coordinates")
        return self


class AcquisitionRequest(ExecutionContract):
    shots: int = Field(default=20, ge=1, le=300)
    receivers: int = Field(default=100, ge=2, le=600)
    layout: Literal["evenly_spaced"] = "evenly_spaced"
    source_depth_m: float = Field(default=8.0, ge=0.0, le=3500.0)
    receiver_depth_m: float = Field(default=8.0, ge=0.0, le=3500.0)
    source_frequency_hz: float = Field(default=25.0, gt=0.0, le=100.0)
    time_samples: int = Field(default=300, ge=2, le=10_000)
    sample_interval_s: float = Field(default=0.004, gt=0.0, le=1.0)


class InversionRequest(ExecutionContract):
    method: Literal["simple_sgd_fwi"] = "simple_sgd_fwi"
    updates: int = Field(default=250, ge=1, le=250)


class RequestedOutputs(ExecutionContract):
    initial_velocity: bool = True
    recovered_velocity: bool = True
    velocity_update: bool = True
    objective_history: bool = True
    observed_shot_gather: bool = False
    predicted_shot_gather: bool = False
    residual: bool = False
    report: bool = True


class ScientificExperimentDraft(ExecutionContract):
    operation: Literal["acoustic_fwi"] = "acoustic_fwi"
    model: ModelSelection = Field(default_factory=ModelSelection)
    acquisition: AcquisitionRequest = Field(default_factory=AcquisitionRequest)
    inversion: InversionRequest = Field(default_factory=InversionRequest)
    requested_outputs: RequestedOutputs = Field(default_factory=RequestedOutputs)
    execution_intent: Literal["prepare", "run"] = "prepare"
    status: ExperimentStatus = "prepare_only"
    issues: list[str] = Field(default_factory=list, max_length=20)
    revision: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def status_matches_execution_intent(self):
        if self.status == "ready" and self.execution_intent != "run":
            raise ValueError("A ready experiment must contain explicit run intent")
        if self.status == "prepare_only" and self.execution_intent != "prepare":
            raise ValueError("A prepare-only experiment cannot contain run intent")
        if self.status in {"ready", "prepare_only"} and self.issues:
            raise ValueError("A validated experiment cannot retain blocking issues")
        return self


class ConversationTurn(ExecutionContract):
    user_text: str = Field(min_length=1, max_length=8000)
    assistant_summary: str = Field(min_length=1, max_length=1000)
    status: ExperimentStatus
    patched_fields: list[str] = Field(default_factory=list, max_length=30)


class ConversationState(ExecutionContract):
    conversation_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    visible_history: list[ConversationTurn] = Field(default_factory=list, max_length=200)
    recent_planner_context: list[ConversationTurn] = Field(default_factory=list, max_length=6)
    active_experiment: ScientificExperimentDraft | None = None
    status: ExperimentStatus
    issues: list[str] = Field(default_factory=list, max_length=20)


class ExperimentConversationRequest(ExecutionContract):
    prompt: str = Field(min_length=1, max_length=8000)
    conversation_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    project_id: str | None = Field(default=None, min_length=1, max_length=128)


class ExperimentConversationResponse(ExecutionContract):
    state: ConversationState
    llm: dict[str, Any] | None = None
