"""Immutable, canonical structural input compiled once from authoring GeoSpec."""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from geoworld_open.specs import FaultSpec, FoldSpec, GeoSpec


class FrozenInputModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        allow_inf_nan=False,
        validate_default=True,
    )


class CompiledGrid(FrozenInputModel):
    nx: int
    ndepth: int
    dx_m: float
    ddepth_m: float
    x_origin_m: float
    depth_origin_m: float

    @property
    def width_m(self) -> float:
        return self.nx * self.dx_m

    @property
    def thickness_m(self) -> float:
        return self.ndepth * self.ddepth_m


class CompiledFacies(FrozenInputModel):
    id: str
    code: int
    label: str


class CompiledFormation(FrozenInputModel):
    id: str
    name: str
    facies_id: str
    thickness_m: float
    porosity_fraction: float
    is_reservoir: bool
    order: int


class CompiledFold(FrozenInputModel):
    kind: Literal["fold"]
    id: str
    amplitude_m: float
    wavelength_m: float
    phase_deg: float
    x_origin_m: float
    order: int


class CompiledFault(FrozenInputModel):
    kind: Literal["fault"]
    id: str
    x_position_m: float
    reference_depth_m: float
    dip_deg: float
    dip_direction: Literal["negative_x", "positive_x"]
    throw_m: float
    displacement: Literal["normal", "reverse"]
    displaced_side: Literal["negative_x", "positive_x"]
    order: int


CompiledStructure = Annotated[
    CompiledFold | CompiledFault,
    Field(discriminator="kind"),
]


class CompiledOutputOptions(FrozenInputModel):
    save_arrays: bool
    save_dataset_metadata: bool
    save_diagnostic_figure: bool


class CompiledStructuralInput(FrozenInputModel):
    """Complete immutable domain input used after the GeoSpec boundary."""

    schema_version: Literal["2.0"]
    compiled_schema_version: Literal["1.0"] = "1.0"
    name: str
    description: str
    root_seed: int
    grid: CompiledGrid
    facies: tuple[CompiledFacies, ...]
    formations: tuple[CompiledFormation, ...]
    structures: tuple[CompiledStructure, ...]
    structural_method_id: Literal["analytic_source_depth_v1"]
    operation_order: Literal["listed"]
    boundary_behavior: Literal["clip_to_grid"]
    outputs: CompiledOutputOptions
    assumptions: tuple[str, ...]


def compile_structural_input(spec: GeoSpec) -> CompiledStructuralInput:
    """Consume a validated GeoSpec exactly once into a frozen domain input."""
    structures: list[CompiledFold | CompiledFault] = []
    for order, item in enumerate(spec.structures):
        payload = item.model_dump(mode="python")
        payload["order"] = order
        if isinstance(item, FaultSpec):
            structures.append(CompiledFault.model_validate(payload))
        else:
            assert isinstance(item, FoldSpec)
            structures.append(CompiledFold.model_validate(payload))

    return CompiledStructuralInput(
        schema_version=spec.schema_version,
        name=spec.metadata.name,
        description=spec.metadata.description,
        root_seed=spec.seed,
        grid=CompiledGrid.model_validate(spec.grid.model_dump(mode="python")),
        facies=tuple(
            CompiledFacies.model_validate(item.model_dump(mode="python"))
            for item in spec.facies
        ),
        formations=tuple(
            CompiledFormation(
                **item.model_dump(mode="python"),
                order=order,
            )
            for order, item in enumerate(spec.layers)
        ),
        structures=tuple(structures),
        structural_method_id=spec.structural_method.method_id,
        operation_order=spec.structural_method.operation_order,
        boundary_behavior=spec.structural_method.boundary_behavior,
        outputs=CompiledOutputOptions.model_validate(
            spec.outputs.model_dump(mode="python")
        ),
        assumptions=tuple(spec.assumptions),
    )


def canonical_structural_input_bytes(value: CompiledStructuralInput) -> bytes:
    """Return stable finite JSON bytes with no Python-specific serialization."""
    return json.dumps(
        value.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def structural_input_sha256(value: CompiledStructuralInput) -> str:
    return hashlib.sha256(canonical_structural_input_bytes(value)).hexdigest()
