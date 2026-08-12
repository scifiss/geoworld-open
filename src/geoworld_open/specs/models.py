"""Strict authoring contract for the public structural World workflow."""

from __future__ import annotations

from math import isclose
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class MetadataSpec(StrictModel):
    name: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    description: str = Field(min_length=1)


class GridSpec(StrictModel):
    nx: int = Field(ge=16, le=2000)
    ndepth: int = Field(ge=16, le=2000)
    dx_m: float = Field(gt=0)
    ddepth_m: float = Field(gt=0)
    x_origin_m: float = 0.0
    depth_origin_m: float = Field(default=0.0, ge=0)

    @property
    def width_m(self) -> float:
        return self.nx * self.dx_m

    @property
    def thickness_m(self) -> float:
        return self.ndepth * self.ddepth_m


class FormationSpec(StrictModel):
    id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1)
    facies_id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    thickness_m: float = Field(gt=0)
    porosity_fraction: float = Field(ge=0, le=0.7)
    is_reservoir: bool


class FaciesSpec(StrictModel):
    id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    code: int = Field(ge=1, le=32767)
    label: str = Field(min_length=1)


class FoldSpec(StrictModel):
    kind: Literal["fold"]
    id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    amplitude_m: float = Field(gt=0)
    wavelength_m: float = Field(gt=0)
    phase_deg: float = 0.0
    x_origin_m: float = 0.0


class FaultSpec(StrictModel):
    kind: Literal["fault"]
    id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    x_position_m: float
    reference_depth_m: float = Field(ge=0)
    dip_deg: float = Field(gt=1, lt=89)
    dip_direction: Literal["negative_x", "positive_x"]
    throw_m: float = Field(gt=0)
    displacement: Literal["normal", "reverse"]
    displaced_side: Literal["negative_x", "positive_x"]


StructureSpec = Annotated[FoldSpec | FaultSpec, Field(discriminator="kind")]


class StructuralMethodSpec(StrictModel):
    method_id: Literal["analytic_source_depth_v1"]
    operation_order: Literal["listed"]
    boundary_behavior: Literal["clip_to_grid"]


class OutputSpec(StrictModel):
    save_arrays: bool = True
    save_dataset_metadata: bool = True
    save_diagnostic_figure: bool = True


class GeoSpec(StrictModel):
    """Versioned authoring input; compilation creates a semantic World and plan."""

    schema_version: Literal["2.0"]
    metadata: MetadataSpec
    seed: int = Field(ge=0, le=2**63 - 1)
    grid: GridSpec
    facies: list[FaciesSpec] = Field(min_length=1)
    layers: list[FormationSpec] = Field(min_length=1)
    structures: list[StructureSpec] = Field(default_factory=list)
    structural_method: StructuralMethodSpec
    outputs: OutputSpec
    assumptions: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_scientific_structure(self) -> "GeoSpec":
        layer_ids = [layer.id for layer in self.layers]
        if len(layer_ids) != len(set(layer_ids)):
            raise ValueError("layer IDs must be unique")
        structure_ids = [structure.id for structure in self.structures]
        if len(structure_ids) != len(set(structure_ids)):
            raise ValueError("structure IDs must be unique")
        facies_ids = [facies.id for facies in self.facies]
        if len(facies_ids) != len(set(facies_ids)):
            raise ValueError("facies IDs must be unique")
        facies_codes = [facies.code for facies in self.facies]
        if len(facies_codes) != len(set(facies_codes)):
            raise ValueError("facies codes must be unique")
        missing_facies = sorted({layer.facies_id for layer in self.layers} - set(facies_ids))
        if missing_facies:
            raise ValueError(f"layers reference unknown facies IDs: {missing_facies}")

        layer_total = sum(layer.thickness_m for layer in self.layers)
        if not isclose(layer_total, self.grid.thickness_m, rel_tol=0, abs_tol=1e-6):
            raise ValueError(
                f"layer thicknesses total {layer_total:g} m but grid thickness is "
                f"{self.grid.thickness_m:g} m"
            )

        x_min = self.grid.x_origin_m
        x_max = x_min + self.grid.width_m
        depth_min = self.grid.depth_origin_m
        depth_max = depth_min + self.grid.thickness_m
        for structure in self.structures:
            if isinstance(structure, FaultSpec):
                if not x_min <= structure.x_position_m < x_max:
                    raise ValueError(f"fault {structure.id!r} x_position_m is outside the grid")
                if not depth_min <= structure.reference_depth_m < depth_max:
                    raise ValueError(
                        f"fault {structure.id!r} reference_depth_m is outside the grid"
                    )
                if structure.throw_m >= self.grid.thickness_m:
                    raise ValueError(f"fault {structure.id!r} throw_m must be less than grid depth")
            elif structure.amplitude_m >= self.grid.thickness_m:
                raise ValueError(f"fold {structure.id!r} amplitude_m must be less than grid depth")
            elif structure.wavelength_m < 2.0 * self.grid.dx_m:
                raise ValueError(
                    f"fold {structure.id!r} wavelength_m must span at least two x samples"
                )
        return self


def load_geospec(path: str | Path) -> GeoSpec:
    """Load and strictly validate one structural GeoSpec YAML document."""
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return GeoSpec.model_validate(payload)
