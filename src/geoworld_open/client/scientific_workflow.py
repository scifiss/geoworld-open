"""PUBLIC_STANDARD: portable bounded goals and protected workflow receipts.

These objects describe intent and presentation, never calibration or authorization.
"""
from typing import Literal
from pydantic import Field, model_validator
from geoworld_open.client.reference_experiment import ReferenceContract


class ScientificGoalAction(ReferenceContract):
    kind: Literal["scientific_goal"] = "scientific_goal"
    objective: Literal["geological_realization", "baseline_avo", "fluid_avo", "revisualize", "unsupported"] = Field(
        description="Preserve the entire compound goal: controlled fluid change plus AVO is fluid_avo, even when it also requests geology.")
    requested_outputs: list[Literal["geological_realization", "paired_fluid_states", "avo_response", "visualization"]] = Field(default_factory=list, max_length=4)
    source: Literal["available_constraints", "existing_model"] = "available_constraints"
    spatial_scope: Literal["2d", "3d"] = "2d"
    realization_count: int = Field(default=1, ge=1, le=4)
    saturations: tuple[float, ...] | None = Field(default=None, min_length=2, max_length=5, strict=False)
    seed: int | None = Field(default=None, ge=0, le=2**31-1)
    prepare_only: bool = False
    clarification: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def valid_saturations(self):
        products = set(self.requested_outputs)
        if len(products) != len(self.requested_outputs):
            raise ValueError("Requested scientific products must be unique")
        if products:
            derived = ("fluid_avo" if "paired_fluid_states" in products else
                       "baseline_avo" if "avo_response" in products else
                       "geological_realization" if "geological_realization" in products else "revisualize")
            if self.objective != derived:
                raise ValueError("Scientific objective must preserve all requested products")
        if self.saturations is not None and (
            self.saturations[0] != 0 or any(not 0 <= s <= 1 for s in self.saturations)
            or any(b <= a for a, b in zip(self.saturations, self.saturations[1:]))
        ):
            raise ValueError("Saturation fractions must increase from a zero-change control")
        return self


class ScientificExperimentContext(ReferenceContract):
    preparation_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    goal: ScientificGoalAction
    completed_job_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")


class ScientificWorkflowPreview(ReferenceContract):
    request: str = ""
    preparation_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    goal: ScientificGoalAction
    execution_allowed: bool = False
    automatic_execution: bool = False
    workflow: list[str] = Field(default_factory=list)
    message: str
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    plan_sha256: str | None = None
    input_sha256: str | None = None
    estimated_seconds: tuple[float, float] = Field(default=(0, 0), strict=False)


class ScientificWorkflowResult(ReferenceContract):
    preparation_id: str
    objective: str
    workflow: list[str]
    realization_count: int
    saturation_count: int
    metrics: list[dict] = Field(default_factory=list)
    figure_artifact: str
    model_artifact: str
    evidence_artifact: str
    manifest_artifact: str
    limitations: list[str]
