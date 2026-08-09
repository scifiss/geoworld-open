"""Public GeoSpec schema for the bounded synthetic workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GridSpec(StrictModel):
    nx: int = Field(ge=16, le=1000)
    nz: int = Field(ge=16, le=1000)
    dx_m: float = Field(gt=0)
    dz_m: float = Field(gt=0)


class LayerSpec(StrictModel):
    name: str = Field(min_length=1)
    lithology: str = Field(min_length=1)
    thickness_m: float = Field(gt=0)
    porosity: float = Field(ge=0, le=0.6)
    saturation: float = Field(ge=0, le=1)
    vp_m_s: float = Field(gt=0)
    vs_m_s: float = Field(gt=0)
    density_kg_m3: float = Field(gt=500, lt=5000)

    @model_validator(mode="after")
    def validate_elastic_order(self) -> "LayerSpec":
        if self.vp_m_s <= self.vs_m_s:
            raise ValueError("vp_m_s must be greater than vs_m_s")
        return self


class FoldSpec(StrictModel):
    amplitude_m: float = Field(gt=0)
    wavelength_m: float = Field(gt=0)
    phase_deg: float = 0.0


class FaultSpec(StrictModel):
    x_position_m: float = Field(ge=0)
    reference_depth_m: float = Field(ge=0)
    dip_degrees: float = Field(gt=1, lt=89)
    throw_m: float = Field(gt=0)
    downthrown_side: Literal["left", "right"]


class CO2ChangeSpec(StrictModel):
    target_layer: str
    center_x_m: float = Field(ge=0)
    center_z_m: float = Field(ge=0)
    radius_x_m: float = Field(gt=0)
    radius_z_m: float = Field(gt=0)
    saturation: float = Field(gt=0, le=1)
    vp_multiplier: float = Field(gt=0, le=1)
    vs_multiplier: float = Field(gt=0, le=1.2)
    density_multiplier: float = Field(gt=0, le=1)


class AngleBandSpec(StrictModel):
    name: str = Field(min_length=1)
    min_deg: float = Field(ge=0, lt=90)
    max_deg: float = Field(gt=0, lt=90)

    @model_validator(mode="after")
    def validate_band(self) -> "AngleBandSpec":
        if self.max_deg < self.min_deg:
            raise ValueError("max_deg must be greater than or equal to min_deg")
        return self


class GeophysicsSpec(StrictModel):
    wavelet_frequency_hz: float = Field(gt=0)
    sample_interval_s: float = Field(gt=0)
    wavelet_duration_s: float = Field(gt=0)
    angles_deg: list[float] = Field(min_length=1)
    angle_bands: list[AngleBandSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_angles(self) -> "GeophysicsSpec":
        if any(angle < 0 or angle >= 90 for angle in self.angles_deg):
            raise ValueError("angles_deg values must be in [0, 90)")
        if len(set(self.angles_deg)) != len(self.angles_deg):
            raise ValueError("angles_deg values must be unique")
        for band in self.angle_bands:
            if not any(band.min_deg <= a <= band.max_deg for a in self.angles_deg):
                raise ValueError(f"angle band {band.name!r} contains no configured angle")
        return self


class ScenarioSpec(StrictModel):
    schema_version: Literal["1.0"]
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    seed: int
    grid: GridSpec
    layers: list[LayerSpec] = Field(min_length=1)
    fold: FoldSpec | None = None
    fault: FaultSpec | None = None
    co2_change: CO2ChangeSpec | None = None
    geophysics: GeophysicsSpec
    assumptions: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_geometry(self) -> "ScenarioSpec":
        depth_m = self.grid.nz * self.grid.dz_m
        width_m = self.grid.nx * self.grid.dx_m
        layer_depth = sum(layer.thickness_m for layer in self.layers)
        if abs(layer_depth - depth_m) > self.grid.dz_m * 0.01:
            raise ValueError(
                f"layer thicknesses total {layer_depth:g} m but grid depth is {depth_m:g} m"
            )
        names = [layer.name for layer in self.layers]
        if len(names) != len(set(names)):
            raise ValueError("layer names must be unique")
        if self.fault and self.fault.x_position_m >= width_m:
            raise ValueError("fault x_position_m must be inside the grid")
        if self.fault and self.fault.reference_depth_m >= depth_m:
            raise ValueError("fault reference_depth_m must be inside the grid")
        if self.co2_change:
            if self.co2_change.target_layer not in names:
                raise ValueError("co2_change target_layer must name an existing layer")
            if self.co2_change.center_x_m >= width_m:
                raise ValueError("co2_change center_x_m must be inside the grid")
            if self.co2_change.center_z_m >= depth_m:
                raise ValueError("co2_change center_z_m must be inside the grid")
        return self


def load_scenario(path: str | Path) -> ScenarioSpec:
    """Load and validate a public GeoSpec YAML file."""
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return ScenarioSpec.model_validate(payload)

