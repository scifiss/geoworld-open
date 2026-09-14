"""PUBLIC_STANDARD: small reference selections, not model-generated coordinates.

This is a capability request, not an additional World Kernel concept.
"""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .execution import ExecutionPlan

REFERENCE_ID = "deepwave-marmousi1-rtm-v0.0.26-r1"


class ReferenceContract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)


class ReferenceChange(ReferenceContract):
    parameter: Literal["source_frequency_hz", "shots"]
    value: float = Field(gt=0)
    user_text: str = Field(min_length=1, max_length=500)


class ReferenceSelection(ReferenceContract):
    reference_id: Literal["deepwave-marmousi1-rtm-v0.0.26-r1"] = REFERENCE_ID
    action: Literal["prepare", "run"] = "prepare"
    require_unchanged: bool = False
    requested_changes: list[ReferenceChange] = Field(default_factory=list, max_length=10)
    requested_outputs: list[str] = Field(default_factory=list, max_length=10)
    unsupported_requests: list[str] = Field(default_factory=list, max_length=10)
    unresolved_conflicts: list[str] = Field(default_factory=list, max_length=10)


class ReferencePreviewRequest(ReferenceContract):
    prompt: str | None = Field(default=None, min_length=1, max_length=8000)
    selection: ReferenceSelection | None = None
    project_id: str | None = Field(default=None, min_length=1, max_length=128)
    device: Literal["auto", "cpu", "cuda"] = "auto"

    @model_validator(mode="after")
    def exactly_one(self):
        if (self.prompt is None) == (self.selection is None):
            raise ValueError("Supply natural language or a structured selection, never both.")
        return self


class ReferencePreview(ReferenceContract):
    selection: ReferenceSelection
    classification: Literal["unchanged_reference", "modified_reference", "unsupported", "inconsistent"]
    prepare_only: bool
    requested_values: dict[str, Any]
    inherited_reference_values: dict[str, Any]
    proposed_modifications: list[ReferenceChange]
    unresolved_conflicts: list[str]
    suggestions: list[str]
    resolved_configuration: dict[str, Any]
    configuration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", description="Hash of the inherited pinned baseline. Proposed modifications remain unresolved and non-runnable.")
    runnable: bool = False
    interpretation_mode: Literal["llm_reference_selection", "structured_input"]
    llm: dict[str, Any] | None = None
    preparation_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    device: Literal["cpu", "cuda"] = "cpu"
    execution_plan: ExecutionPlan | None = None
    model_preview: dict[str, Any] | None = None


class ReferenceResult(ReferenceContract):
    reference_id: Literal["deepwave-marmousi1-rtm-v0.0.26-r1"] = REFERENCE_ID
    classification: Literal["unchanged_reference"] = "unchanged_reference"
    numerical_executor: Literal["Deepwave 0.0.26; deterministic pinned upstream programs"] = "Deepwave 0.0.26; deterministic pinned upstream programs"
    configuration_sha256: str
    runtime_seconds: float = Field(ge=0)
    comparison: dict[str, Any]
    reports: list[str]
    interpretation_mode: str
    llm: dict[str, Any] | None = None
    device: Literal["cpu", "cuda"] = "cpu"


class ReferenceCompute(ReferenceContract):
    execution_location: Literal["backend"] = "backend"
    cuda_usable: bool = False
    gpu_name: str | None = None
    free_gpu_gib: float | None = None
    required_free_gpu_gib: float = 8.0
    reference_gpu_allowed: bool = False
    explanation: str
