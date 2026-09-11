"""Portable HTTP contracts only; numerical implementation stays behind the API."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RTMContract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class AcousticAcquisition(RTMContract):
    coordinate_order: Literal["z,x"] = "z,x"
    distance_unit: Literal["m"] = "m"
    velocity_unit: Literal["m/s"] = "m/s"
    time_unit: Literal["s"] = "s"
    shots: int = Field(default=1, ge=1, le=4)
    source_depth_index: int = Field(default=2, ge=1, le=126)
    receiver_depth_index: int = Field(default=2, ge=1, le=126)
    receiver_stride: int = Field(default=2, ge=1, le=8)
    source_indices_zx: list[tuple[int, int]] | None = Field(default=None, max_length=4)
    receiver_indices_zx: list[tuple[int, int]] | None = Field(default=None, max_length=192)
    frequency_hz: float = Field(default=10.0, ge=5.0, le=15.0)
    dt_s: float = Field(default=0.001, ge=0.0005, le=0.002)
    nt: int = Field(default=1200, ge=400, le=1800)

    @model_validator(mode="after")
    def validate_locations(self):
        if self.source_indices_zx is not None and len(self.source_indices_zx) != self.shots:
            raise ValueError("Provide exactly one source location for each shot.")
        for points in (self.source_indices_zx, self.receiver_indices_zx):
            if points is not None and (not points or len(points) != len(set(points))):
                raise ValueError("Locations must be nonempty and unique.")
        return self


class AdjointImaging(RTMContract):
    method: Literal["born_adjoint"] = "born_adjoint"
    migration_model: Literal["smoothed_synthetic_truth"] = "smoothed_synthetic_truth"
    smoothing_sigma_cells: float = Field(default=6.0, ge=3.0, le=15.0)
    accuracy: Literal[8] = 8
    pml_width: Literal[20] = 20
    device: Literal["cpu"] = "cpu"
    timeout_s: int = Field(default=180, ge=10, le=240)


class RTMExperiment(RTMContract):
    schema_version: Literal["1.0"] = "1.0"
    # Existing GeoSpec payload, not a competing geological model schema.
    geospec: dict[str, Any]
    acquisition: AcousticAcquisition = Field(default_factory=AcousticAcquisition)
    imaging: AdjointImaging = Field(default_factory=AdjointImaging)


class RTMModelPreview(RTMContract):
    """Bounded reviewed model state; the acoustic solver consumes only Vp."""
    shape_zx: list[int] = Field(min_length=2, max_length=2)
    x_m: list[float]
    z_m: list[float]
    vp_zx: list[list[float]]
    vs_zx: list[list[float]]
    density_zx: list[list[float]]
    units: dict[str, str]
    ranges: dict[str, list[float]]
    vp_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    property_source: Literal["derived_from_lithology_and_porosity"] = "derived_from_lithology_and_porosity"
    solver_fields: list[Literal["vp"]] = Field(default_factory=lambda: ["vp"])

    @model_validator(mode="after")
    def validate_grid(self):
        nz, nx = self.shape_zx
        if nz < 2 or nx < 2 or len(self.x_m) != nx or len(self.z_m) != nz:
            raise ValueError("Model preview coordinates must match shape_zx.")
        for field in ("vp", "vs", "density"):
            values = getattr(self, field + "_zx")
            if len(values) != nz or any(len(row) != nx for row in values):
                raise ValueError(field + " preview must match shape_zx.")
            if field not in self.units or field not in self.ranges or len(self.ranges[field]) != 2:
                raise ValueError(field + " units and range are required.")
        if self.solver_fields != ["vp"]:
            raise ValueError("This acoustic workflow can approve only Vp for the solver.")
        return self


class RTMPreviewRequest(RTMContract):
    prompt: str | None = Field(default=None, min_length=1, max_length=8000)
    experiment: RTMExperiment | None = None

    @model_validator(mode="after")
    def exactly_one(self):
        if (self.prompt is None) == (self.experiment is None):
            raise ValueError("Provide a prompt or a structured experiment, not both.")
        return self


class RTMPreview(RTMContract):
    experiment: RTMExperiment
    interpretation_mode: Literal["llm_rtm_interpretation", "structured_input"]
    assumptions: list[str]
    llm: dict[str, Any] | None = None
    preparation_id: str | None = None
    model_preview: RTMModelPreview | None = None


class RTMResult(RTMContract):
    method: Literal["born_adjoint"] = "born_adjoint"
    state_id: str
    observation_id: str
    acquisition_id: str
    experiment_hash: str
    runtime_seconds: float = Field(ge=0)
    peak_memory_mib: float = Field(gt=0)
    artifacts: list[str]
    diagnostics: dict[str, Any]
