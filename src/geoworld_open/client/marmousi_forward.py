"""Portable contracts for configurable Marmousi 1 acoustic forward modelling.

These schemas define inputs and reproducibility evidence only. Dataset loading,
coordinate planning, resource policy, and Deepwave execution remain protected
backend capabilities and are never delegated to an LLM.
"""
from __future__ import annotations

import math
from typing import Annotated, Any, Literal

from pydantic import Field, model_validator

from .execution import ExecutionPlan, ExecutionPreference
from .marmousi import MarmousiPreview, ModelCrop
from .reference_experiment import ReferenceContract


MARMOUSI1_SPACING_M = 4.0
MARMOUSI1_X_STOP_M = 9200.0
MARMOUSI1_Z_STOP_M = 3000.0


class MarmousiAcquisitionRequest(ReferenceContract):
    """User-facing acquisition intent; the backend resolves all coordinates."""

    number_of_shots: int = Field(default=20, ge=1, le=64)
    receivers_per_shot: int = Field(default=100, ge=2, le=600)
    source_depth_m: float = Field(default=8.0, ge=0.0, le=MARMOUSI1_Z_STOP_M)
    receiver_depth_m: float = Field(default=8.0, ge=0.0, le=MARMOUSI1_Z_STOP_M)
    spacing_policy: Literal["uniform_surface"] = "uniform_surface"


class MarmousiForwardSettings(ReferenceContract):
    """One bounded, resolved acoustic setting set used by preview and solvers."""

    source_frequency_hz: Literal[25.0] = 25.0
    sample_interval_s: Literal[0.004] = 0.004
    time_samples: Literal[300] = 300
    ricker_peak_time_s: Literal[0.06] = 0.06
    accuracy: Literal[8] = 8
    pml_width: Literal[20] = 20
    precision: Literal["float32"] = "float32"
    solver: Literal["deepwave_scalar_0.0.26"] = "deepwave_scalar_0.0.26"
    origins: dict[str, Literal["user_request", "geoworld_validated_default"]] = Field(
        default_factory=lambda: {name: "geoworld_validated_default" for name in (
            "source_frequency_hz", "sample_interval_s", "time_samples", "ricker_peak_time_s",
            "accuracy", "pml_width", "precision", "solver",
        )}
    )

    @model_validator(mode="after")
    def origins_cover_resolved_values(self):
        expected = set(type(self).model_fields) - {"origins"}
        if set(self.origins) != expected:
            raise ValueError("Every resolved acoustic setting needs exactly one origin")
        return self



class MarmousiForwardExperiment(ReferenceContract):
    dataset: Literal["marmousi1"] = "marmousi1"
    crop: ModelCrop
    acquisition: MarmousiAcquisitionRequest = Field(default_factory=MarmousiAcquisitionRequest)
    settings: MarmousiForwardSettings = Field(default_factory=MarmousiForwardSettings)

    @model_validator(mode="after")
    def bounded_to_marmousi1_grid(self):
        if self.crop.x_stop_m > MARMOUSI1_X_STOP_M or self.crop.z_stop_m > MARMOUSI1_Z_STOP_M:
            raise ValueError("Crop extends beyond the Marmousi 1 benchmark extent")
        for name in ("source_depth_m", "receiver_depth_m"):
            depth = getattr(self.acquisition, name)
            if not self.crop.z_start_m <= depth <= self.crop.z_stop_m:
                raise ValueError(f"{name} must lie inside the requested crop")
        start = math.ceil(self.crop.x_start_m / MARMOUSI1_SPACING_M)
        stop = math.floor(self.crop.x_stop_m / MARMOUSI1_SPACING_M)
        available_x = stop - start + 1
        if available_x < 2:
            raise ValueError("Crop must contain at least two original Marmousi 1 x samples")
        if self.acquisition.number_of_shots > available_x:
            raise ValueError("Shot count exceeds unique grid locations in the crop")
        if self.acquisition.receivers_per_shot > available_x:
            raise ValueError("Receiver count exceeds unique grid locations in the crop")
        return self


_GridPointZX = Annotated[list[int], Field(min_length=2, max_length=2)]
_MetricPointXZ = Annotated[list[float], Field(min_length=2, max_length=2)]


class ResolvedMarmousiAcquisition(ReferenceContract):
    coordinate_order_indices: Literal["z,x"] = "z,x"
    coordinate_order_metres: Literal["x,z"] = "x,z"
    spacing_policy: Literal["uniform_surface"] = "uniform_surface"
    source_indices_zx: list[_GridPointZX] = Field(min_length=1, max_length=64)
    receiver_indices_zx: list[_GridPointZX] = Field(min_length=2, max_length=600)
    source_coordinates_xz_m: list[_MetricPointXZ] = Field(min_length=1, max_length=64)
    receiver_coordinates_xz_m: list[_MetricPointXZ] = Field(min_length=2, max_length=600)
    requested_source_depth_m: float
    requested_receiver_depth_m: float
    resolved_source_depth_m: float
    resolved_receiver_depth_m: float
    geometry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def coordinates_are_unique_and_aligned(self):
        if len(self.source_indices_zx) != len(self.source_coordinates_xz_m):
            raise ValueError("Source indices and metre coordinates must align")
        if len(self.receiver_indices_zx) != len(self.receiver_coordinates_xz_m):
            raise ValueError("Receiver indices and metre coordinates must align")
        if len({tuple(point) for point in self.source_indices_zx}) != len(self.source_indices_zx):
            raise ValueError("Resolved source locations must be unique")
        if len({tuple(point) for point in self.receiver_indices_zx}) != len(self.receiver_indices_zx):
            raise ValueError("Resolved receiver locations must be unique")
        return self


class MarmousiForwardPreviewRequest(ReferenceContract):
    experiment: MarmousiForwardExperiment
    project_id: str | None = Field(default=None, min_length=1, max_length=128)
    preference: ExecutionPreference = Field(default_factory=ExecutionPreference)


class MarmousiForwardPreview(ReferenceContract):
    experiment: MarmousiForwardExperiment
    classification: Literal["configurable_marmousi1_forward"] = "configurable_marmousi1_forward"
    model_preview: MarmousiPreview
    resolved_acquisition: ResolvedMarmousiAcquisition
    crop_vp_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    geometry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    experiment_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    settings_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_plan: ExecutionPlan
    preparation_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    solver_executed: Literal[False] = False
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def geometry_identity_matches(self):
        if self.geometry_sha256 != self.resolved_acquisition.geometry_sha256:
            raise ValueError("Preview geometry hashes do not match")
        return self


class MarmousiForwardResult(ReferenceContract):
    classification: Literal["configurable_marmousi1_forward"] = "configurable_marmousi1_forward"
    experiment_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    crop_vp_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    geometry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    wavelet_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_shots_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    settings_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    settings: MarmousiForwardSettings
    runtime_seconds: float = Field(ge=0.0)
    peak_memory_mib: float = Field(gt=0.0)
    artifacts: list[str]
    diagnostics: dict[str, Any]

    @model_validator(mode="after")
    def previewed_crop_is_solver_input(self):
        if self.crop_vp_sha256 != self.model_input_sha256:
            raise ValueError("Solver model input differs from the previewed crop")
        return self
