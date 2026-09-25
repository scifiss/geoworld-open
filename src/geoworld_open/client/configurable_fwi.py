"""Portable contracts for prepared Marmousi crop → forward → simple acoustic FWI.

The protected backend resolves geometry, plans resources, and runs Deepwave.
This is modified benchmark science, never an unchanged upstream reference.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from .execution import ExecutionPlan, ExecutionPreference
from .intermediate_results import IntermediateResultPolicy
from .marmousi_forward import MarmousiForwardPreview, MarmousiForwardResult
from .scientific_experiment import ScientificExperimentDraft
from .reference_experiment import ReferenceContract


class ConfigurableFWIPreviewRequest(ReferenceContract):
    experiment: ScientificExperimentDraft
    project_id: str | None = Field(default=None, min_length=1, max_length=128)
    preference: ExecutionPreference = Field(default_factory=ExecutionPreference)
    intermediate_results: IntermediateResultPolicy = Field(default_factory=IntermediateResultPolicy)


class ConfigurableFWIPreview(ReferenceContract):
    experiment: ScientificExperimentDraft
    forward: MarmousiForwardPreview
    execution_plan: ExecutionPlan
    snapshot_schedule: list[int]
    preparation_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    scientific_mode: Literal["modified_experiment"] = "modified_experiment"
    runnable: bool
    solver_executed: Literal[False] = False
    assumptions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def can_run_only_validated_experiment(self):
        if self.runnable and (self.experiment.status != "ready" or not self.execution_plan.feasible):
            raise ValueError("Only an explicit validated and feasible request is runnable")
        if self.snapshot_schedule != sorted(set(self.snapshot_schedule)):
            raise ValueError("Snapshot steps must be unique and ordered")
        if self.snapshot_schedule and self.snapshot_schedule[-1] != self.experiment.inversion.updates:
            raise ValueError("The last snapshot must be the final optimizer update")
        return self


class ConfigurableFWIResult(ReferenceContract):
    scientific_mode: Literal["modified_experiment"] = "modified_experiment"
    forward: MarmousiForwardResult
    crop_vp_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    geometry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_shots_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    settings_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    predicted_shots_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    residual_shots_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    initial_vp_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    recovered_vp_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    true_vp_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    initial_data_objective: float | None = Field(default=None, ge=0)
    final_data_objective: float | None = Field(default=None, ge=0)
    initial_velocity_rmse_mps: float | None = Field(default=None, ge=0)
    final_velocity_rmse_mps: float | None = Field(default=None, ge=0)
    completed_updates: int = Field(ge=1, le=250)
    objective_history: list[float]
    snapshot_schedule: list[int]
    forward_runtime_seconds: float = Field(ge=0)
    fwi_runtime_seconds: float = Field(ge=0)
    peak_ram_mib: float = Field(ge=0)
    peak_vram_mib: float = Field(ge=0)
    artifacts: list[str] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def forward_identity_is_unchanged(self):
        for name in ("crop_vp_sha256", "geometry_sha256", "observed_shots_sha256", "settings_sha256"):
            if getattr(self, name) != getattr(self.forward, name):
                raise ValueError(f"FWI input {name} differs from forward output")
        if self.completed_updates != len(self.objective_history):
            raise ValueError("Objective history does not cover every completed update")
        if self.true_vp_sha256 is not None and self.true_vp_sha256 != self.crop_vp_sha256:
            raise ValueError("Synthetic truth differs from the approved crop")
        return self
