"""PUBLIC_STANDARD: bounded benchmark exploration, not a new World Kernel."""
from __future__ import annotations

from typing import Literal
from pydantic import Field, model_validator
from geoworld_open.client.reference_experiment import ReferenceContract


class ModelCrop(ReferenceContract):
    x_start_m: float = Field(ge=0)
    x_stop_m: float = Field(gt=0)
    z_start_m: float = Field(ge=0)
    z_stop_m: float = Field(gt=0)

    @model_validator(mode="after")
    def ordered(self):
        if self.x_start_m >= self.x_stop_m or self.z_start_m >= self.z_stop_m:
            raise ValueError("X and Z stop must be greater than start.")
        return self


class PropertyOverrides(ReferenceContract):
    # Explicit spatially uniform assumptions over the crop, never inferred rock physics.
    vp_m_s: float | None = Field(default=None, ge=500, le=10000)
    vs_m_s: float | None = Field(default=None, ge=0, le=6000)
    density_kg_m3: float | None = Field(default=None, ge=500, le=5000)
    porosity_fraction: float | None = Field(default=None, ge=0, le=1)


class MarmousiSelection(ReferenceContract):
    dataset: Literal["marmousi1", "marmousi2"]
    crop: ModelCrop | None = None
    overrides: PropertyOverrides = Field(default_factory=PropertyOverrides)
    display_property: Literal["vp", "vs", "density", "porosity"] = "vp"


class MarmousiPreviewRequest(ReferenceContract):
    selection: MarmousiSelection
    project_id: str | None = Field(default=None, min_length=1, max_length=128)


class MarmousiInterpretRequest(ReferenceContract):
    prompt: str = Field(min_length=1, max_length=8000)
    project_id: str | None = Field(default=None, min_length=1, max_length=128)


class MarmousiInterpretation(ReferenceContract):
    selection: MarmousiSelection | None = None
    unresolved: list[str] = Field(default_factory=list, max_length=20)
    llm: dict | None = None


class MarmousiPreview(ReferenceContract):
    selection: MarmousiSelection
    classification: Literal["benchmark_model_preview", "modified_benchmark_model"]
    configuration_sha256: str
    dataset_extent: ModelCrop
    resolved_crop: ModelCrop
    shape_xz: list[int]
    spacing_m: float
    fields: list[str]
    unit: str
    x_m: list[float]
    z_m: list[float]
    values_zx: list[list[float]]
    provenance: dict
    warnings: list[str]
