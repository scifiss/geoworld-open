"""PUBLIC_STANDARD: a bounded interpretation, not an executable agent plan."""
from typing import Annotated, Any, Literal
from geoworld_open.client.semantic_action import SemanticAction
from geoworld_open.client.scientific_workflow import ScientificExperimentContext, ScientificWorkflowPreview

from pydantic import Field, field_validator, model_validator
import json
from geoworld_open.client.seismic import SeismicViewRequest
from geoworld_open.client.reference_experiment import ReferenceContract


ContextAction = Literal["patch_build", "prepare_build", "run_prepared_build",
    "seismic_metadata", "seismic_view_command", "continue_specialized_workflow",
    "new_task", "general_question", "clarification_required", "scientific_goal"]


class StudioBuildContext(ReferenceContract):
    # The existing preview/job APIs validate this versioned GeoSpec payload.
    geospec: dict[str, Any]
    turns: list[Annotated[str, Field(min_length=1, max_length=8000)]] = Field(default_factory=list, max_length=20)
    valid: bool = False
    confirmation_required: bool = False
    degraded: bool = False
    interpretation_mode: str | None = Field(default=None, max_length=100)

    @field_validator("geospec")
    @classmethod
    def bounded_spec(cls, value):
        if len(json.dumps(value, allow_nan=False)) > 100_000:
            raise ValueError("Build context exceeds the bounded specification size")
        return value


class StudioTaskContext(ReferenceContract):
    """Session working state; never authorization, chat memory or scientific truth."""
    pending_semantic_action: SemanticAction | None = None
    active_task: Literal["none", "build", "seismic", "specialized", "scientific"] = "none"
    scientific: ScientificExperimentContext | None = None
    build: StudioBuildContext | None = None
    active_seismic_dataset_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{24}$")
    seismic_conversation_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    seismic_view: SeismicViewRequest | None = None
    specialized_route: Literal["marmousi_model", "deepwave_reference", "model_rtm",
        "model_forward", "bounded_fwi", "configurable_marmousi_fwi", "las_quicklook"] | None = None
    last_action: ContextAction | None = None
    unresolved_clarification: str | None = Field(default=None, max_length=2000)
    execution_allowed: bool = False

    @model_validator(mode="after")
    def consistent_referents(self):
        if self.seismic_view and self.seismic_view.dataset_id != self.active_seismic_dataset_id:
            raise ValueError("Current view must belong to the active dataset")
        if self.execution_allowed and (not self.build or not self.build.valid or self.unresolved_clarification):
            raise ValueError("Execution eligibility requires a valid prepared build without unresolved clarification")
        return self


class StudioRequest(ReferenceContract):
    prompt: str = Field(min_length=1, max_length=8000)
    project_id: str | None = Field(default=None, min_length=1, max_length=128)
    context: StudioTaskContext | None = None
    has_pending_build: bool = False
    active_seismic_dataset_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{24}$")


class StudioIntent(ReferenceContract):
    operation: Literal["question", "build", "preview", "rtm", "forward", "fwi", "las", "seismic", "unsupported", "scientific"]
    dataset: Literal["marmousi1", "marmousi2", "synthetic"] | None = None
    prepare_only: bool = False
    context_action: Literal["patch_build", "prepare_build", "continue_specialized_workflow", "new_task", "general_question"] | None = None
    issues: list[str] = Field(default_factory=list, max_length=20)


class EvidenceAssessmentReceipt(ReferenceContract):
    """PUBLIC_STANDARD: completed owner-scoped assessment, not a simulation."""
    record_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_job_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    objective: str = Field(min_length=1, max_length=100)
    answer: str = Field(min_length=1, max_length=8000)
    conclusion: str = Field(min_length=1, max_length=2000)
    evidence_count: int = Field(ge=0, le=64)
    gaps: list[str] = Field(default_factory=list, max_length=64)


class StudioDecision(ReferenceContract):
    interpretation: StudioIntent
    route: Literal["ask_question", "build_model", "marmousi_model", "deepwave_reference", "model_rtm", "model_forward", "bounded_fwi", "configurable_marmousi_fwi", "las_quicklook", "seismic_explorer", "blocked", "scientific_workflow"]
    scientific: ScientificWorkflowPreview | None = None
    evidence_assessment: EvidenceAssessmentReceipt | None = None
    message: str
    llm: dict[str, Any] | None = None
    build_spec: dict[str, Any] | None = None
    semantic_action: SemanticAction | None = None
    continues_build: bool = False
    action: ContextAction | None = None
    command: str | None = Field(default=None, max_length=8000)
