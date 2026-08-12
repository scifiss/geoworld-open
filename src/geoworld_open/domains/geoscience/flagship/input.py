"""Explicit authoring and immutable input contracts for the flagship demonstration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from geoworld_open.domains.geoscience.structural import (
    CompiledStructuralInput,
    compile_structural_input,
)
from geoworld_open.specs import GeoSpec


class FrozenFlagshipModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        allow_inf_nan=False,
        validate_default=True,
    )


class ReservoirRegionInput(FrozenFlagshipModel):
    id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=1)
    formation_id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    intersecting_fault_id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")


class WellInput(FrozenFlagshipModel):
    id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=1)
    x_m: float
    top_depth_m: float = Field(ge=0)
    bottom_depth_m: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_trajectory(self) -> "WellInput":
        if self.bottom_depth_m <= self.top_depth_m:
            raise ValueError("well bottom_depth_m must exceed top_depth_m")
        return self


class BaselineInput(FrozenFlagshipModel):
    pressure_reference_pa: float = Field(gt=0)
    pressure_reference_depth_m: float = Field(ge=0)
    reference_density_kg_m3: float = Field(gt=0)
    gravity_m_s2: float = Field(gt=0)
    temperature_reference_deg_c: float
    temperature_reference_depth_m: float = Field(ge=0)
    geothermal_gradient_deg_c_per_m: float = Field(ge=0)


class PerturbationInput(FrozenFlagshipModel):
    maximum_delta_pressure_pa: float = Field(gt=0)
    center_x_m: float
    center_depth_m: float = Field(ge=0)
    sigma_x_m: float = Field(gt=0)
    sigma_depth_m: float = Field(gt=0)
    model_time_days: float = Field(gt=0)


class ObservationInput(FrozenFlagshipModel):
    sample_depths_m: tuple[float, ...] = Field(min_length=1)
    sampling_method: Literal["nearest_cell"]
    noise_sigma_pa: float = Field(ge=0)
    noise_seed: int = Field(ge=0, le=2**63 - 1)
    noise_namespace: Literal["flagship_well_pressure_observation"]


class FlagshipOutputInput(FrozenFlagshipModel):
    save_diagnostic_figure: bool


class FlagshipSpec(BaseModel):
    """One bounded flagship scenario containing structural and monitoring inputs."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    flagship_schema_version: Literal["1.0"]
    structural: GeoSpec
    reservoir_region: ReservoirRegionInput
    well: WellInput
    baseline: BaselineInput
    perturbation: PerturbationInput
    observation: ObservationInput
    outputs: FlagshipOutputInput
    assumptions: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_explicit_references(self) -> "FlagshipSpec":
        grid = self.structural.grid
        x_min = grid.x_origin_m
        x_max = x_min + grid.width_m
        depth_min = grid.depth_origin_m
        depth_max = depth_min + grid.thickness_m
        if not x_min <= self.well.x_m < x_max:
            raise ValueError("well x_m must lie inside the structural grid")
        if not depth_min <= self.well.top_depth_m < self.well.bottom_depth_m <= depth_max:
            raise ValueError("well trajectory must lie inside the structural depth interval")
        if not x_min <= self.perturbation.center_x_m < x_max:
            raise ValueError("perturbation center_x_m must lie inside the structural grid")
        if not depth_min <= self.perturbation.center_depth_m < depth_max:
            raise ValueError("perturbation center_depth_m must lie inside the structural grid")
        if any(
            not self.well.top_depth_m <= depth <= self.well.bottom_depth_m
            for depth in self.observation.sample_depths_m
        ):
            raise ValueError("observation depths must lie on the authored well trajectory")

        formations = {item.id: item for item in self.structural.layers}
        formation = formations.get(self.reservoir_region.formation_id)
        if formation is None:
            raise ValueError("ReservoirRegion references an unknown Formation")
        if not formation.is_reservoir:
            raise ValueError("ReservoirRegion Formation must have explicit reservoir role")
        fault_ids = {
            item.id for item in self.structural.structures if item.kind == "fault"
        }
        if self.reservoir_region.intersecting_fault_id not in fault_ids:
            raise ValueError("ReservoirRegion references an unknown Fault")
        return self


class CompiledFlagshipInput(FrozenFlagshipModel):
    """Complete content-bound authority for the flagship workflow."""

    flagship_schema_version: Literal["1.0"]
    compiled_schema_version: Literal["1.0"] = "1.0"
    structural: CompiledStructuralInput
    reservoir_region: ReservoirRegionInput
    well: WellInput
    baseline: BaselineInput
    perturbation: PerturbationInput
    observation: ObservationInput
    outputs: FlagshipOutputInput
    assumptions: tuple[str, ...]


def compile_flagship_input(spec: FlagshipSpec) -> CompiledFlagshipInput:
    """Compile the scenario exactly once into immutable execution authority."""
    return CompiledFlagshipInput(
        flagship_schema_version=spec.flagship_schema_version,
        structural=compile_structural_input(spec.structural),
        reservoir_region=spec.reservoir_region,
        well=spec.well,
        baseline=spec.baseline,
        perturbation=spec.perturbation,
        observation=spec.observation,
        outputs=spec.outputs,
        assumptions=spec.assumptions,
    )


def canonical_flagship_input_bytes(value: CompiledFlagshipInput) -> bytes:
    return json.dumps(
        value.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def flagship_input_sha256(value: CompiledFlagshipInput) -> str:
    return hashlib.sha256(canonical_flagship_input_bytes(value)).hexdigest()


def load_flagship_spec(path: str | Path) -> FlagshipSpec:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return FlagshipSpec.model_validate(payload)
