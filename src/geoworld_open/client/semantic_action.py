"""PUBLIC_STANDARD: bounded semantic actions; they grant no execution permission."""
from typing import Annotated, Literal
from pydantic import Field
from geoworld_open.client.reference_experiment import ReferenceContract

LithologyName = Literal["shale", "sand", "sandstone", "carbonate", "limestone", "salt"]

class RequestedLayer(ReferenceContract):
    lithology: LithologyName
    porosity: float | None = Field(default=None, ge=.01, le=.40)
    porosity_policy: Literal["low", "medium", "high"] | None = None
    thickness_m: float | None = Field(default=None, gt=0, le=20000)

class NewBuild(ReferenceContract):
    kind: Literal["new_build"] = "new_build"
    layers: list[RequestedLayer] = Field(min_length=1, max_length=20)
    prepare_only: bool = False
    co2_host_index: int | None = Field(default=None, ge=0, le=19)
    fault_scope: Literal["none", "through_going", "layer_restricted"] = "none"
    fault_dip_degrees: float | None = Field(default=None, ge=5, le=89)
    fault_throw_m: float | None = Field(default=None, ge=-5000, le=5000)

class LayerEdit(ReferenceContract):
    operation: Literal["porosity", "thickness", "thicker", "add_below", "remove_co2"]
    layer_index: int | None = Field(default=None, ge=0, le=19)
    value: float | None = Field(default=None, gt=0, le=20000)
    layer: RequestedLayer | None = None

class PatchBuild(ReferenceContract):
    kind: Literal["patch_build"] = "patch_build"
    edits: list[LayerEdit] = Field(min_length=1, max_length=10)
    prepare_only: bool = False

class RunPreparedBuild(ReferenceContract):
    kind: Literal["run_prepared_build"] = "run_prepared_build"

class PrepareBuild(ReferenceContract):
    kind: Literal["prepare_build"] = "prepare_build"

class SeismicMetadataQuestion(ReferenceContract):
    kind: Literal["seismic_metadata"] = "seismic_metadata"

class SeismicViewCommand(ReferenceContract):
    kind: Literal["seismic_view_command"] = "seismic_view_command"
    command: str = Field(min_length=1, max_length=8000)

class GeneralQuestion(ReferenceContract):
    kind: Literal["general_question"] = "general_question"

class ClarificationRequired(ReferenceContract):
    kind: Literal["clarification_required"] = "clarification_required"
    question: str = Field(min_length=1, max_length=1000)

class NewTask(ReferenceContract):
    kind: Literal["new_task"] = "new_task"
    # Specialized capability admission stays in the existing protected router.
    operation: Literal["preview", "rtm", "forward", "fwi", "las", "seismic", "unsupported"]
    dataset: Literal["marmousi1", "marmousi2", "synthetic"] | None = None
    prepare_only: bool = False
    issues: list[str] = Field(default_factory=list, max_length=20)

SemanticAction = Annotated[NewBuild | PatchBuild | RunPreparedBuild | PrepareBuild |
    SeismicMetadataQuestion | SeismicViewCommand | GeneralQuestion | ClarificationRequired | NewTask,
    Field(discriminator="kind")]
