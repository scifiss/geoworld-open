"""Public contracts for scientific capabilities and their validity domains."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable

import numpy as np
import xarray as xr
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from geoworld_open.standard.version import STANDARD_VERSION
from geoworld_open.world.models import Identifier, NonEmptyStr


class ContractModel(BaseModel):
    """Strict immutable base for versioned public contracts."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        allow_inf_nan=False,
        validate_default=True,
    )


class CapabilityKind(str, Enum):
    PHYSICS = "physics"
    GEOMETRY = "geometry"
    OBSERVATION = "observation"
    TRANSFORM = "transform"
    RENDER = "render"


class DTypeKind(str, Enum):
    FLOAT = "float"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    STRING = "string"


class VariableSpec(ContractModel):
    """One named, unit-bearing capability input or output."""

    name: Identifier
    unit: NonEmptyStr
    dimensions: tuple[Identifier, ...] = ()
    dtype_kind: DTypeKind | None = None
    description: NonEmptyStr | None = None
    required: bool = True

    @model_validator(mode="after")
    def validate_dimensions(self) -> "VariableSpec":
        if len(set(self.dimensions)) != len(self.dimensions):
            raise ValueError("variable dimensions must be unique")
        return self


class NumericBound(ContractModel):
    """Documented finite applicability bound for one variable."""

    variable: Identifier
    unit: NonEmptyStr
    minimum: float | None = None
    maximum: float | None = None

    @model_validator(mode="after")
    def validate_range(self) -> "NumericBound":
        if self.minimum is None and self.maximum is None:
            raise ValueError("a numeric bound requires minimum or maximum")
        if self.minimum is not None and self.maximum is not None and self.maximum < self.minimum:
            raise ValueError("numeric bound maximum must not be below minimum")
        return self


class ValidityDomain(ContractModel):
    """Explicit applicability statement; it is not an automatic calibration claim."""

    description: NonEmptyStr
    bounds: tuple[NumericBound, ...] = ()
    constraints: tuple[NonEmptyStr, ...] = ()
    excluded_uses: tuple[NonEmptyStr, ...] = ()

    @model_validator(mode="after")
    def validate_bounds(self) -> "ValidityDomain":
        variables = [item.variable for item in self.bounds]
        if len(variables) != len(set(variables)):
            raise ValueError("validity-domain bounds must name unique variables")
        return self


class CapabilitySpec(ContractModel):
    """Citeable declaration of a GeoWorld-compatible scientific capability."""

    schema_version: str = STANDARD_VERSION
    capability_id: Identifier
    version: Identifier
    kind: CapabilityKind
    title: NonEmptyStr
    law_name: NonEmptyStr | None = None
    inputs: tuple[VariableSpec, ...] = ()
    outputs: tuple[VariableSpec, ...] = Field(min_length=1)
    validity_domain: ValidityDomain
    assumptions: tuple[NonEmptyStr, ...] = ()
    references: tuple[NonEmptyStr, ...] = ()
    deterministic: bool = True

    @model_validator(mode="after")
    def validate_variables(self) -> "CapabilitySpec":
        input_names = [item.name for item in self.inputs]
        output_names = [item.name for item in self.outputs]
        if len(input_names) != len(set(input_names)):
            raise ValueError("capability input names must be unique")
        if len(output_names) != len(set(output_names)):
            raise ValueError("capability output names must be unique")
        return self


@dataclass(frozen=True)
class CapabilityContext:
    """Execution context passed to public or third-party capability plugins."""

    seed: int = 0
    parameters: dict[str, JsonValue] = field(default_factory=dict)

    def rng(self) -> np.random.Generator:
        return np.random.default_rng(self.seed)


@dataclass(frozen=True)
class CapabilityRunResult:
    """Numerical output and JSON-safe diagnostics from one capability call."""

    dataset: xr.Dataset
    diagnostics: dict[str, JsonValue] = field(default_factory=dict)


@runtime_checkable
class PhysicsCapability(Protocol):
    """Public plugin interface; implementations own their numerical method."""

    spec: CapabilitySpec

    def execute(self, dataset: xr.Dataset, context: CapabilityContext) -> CapabilityRunResult:
        """Return a new dataset without mutating the caller's dataset."""
        ...


def numpy_dtype_kind(dtype: Any) -> DTypeKind | None:
    """Map NumPy dtype families to the public contract vocabulary."""

    kind = np.dtype(dtype).kind
    if kind in "fc":
        return DTypeKind.FLOAT
    if kind in "iu":
        return DTypeKind.INTEGER
    if kind == "b":
        return DTypeKind.BOOLEAN
    if kind in "SUO":
        return DTypeKind.STRING
    return None
