"""Typed, public-specific scientific operator contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np
import xarray as xr

from geoworld_open.specs.models import GeoSpecV2


@dataclass(frozen=True)
class VariableContract:
    name: str
    dims: tuple[str, ...]
    units: str
    dtype_kind: str | None = None


@dataclass(frozen=True)
class OperatorMetadataV2:
    id: str
    version: str
    method_id: str
    requires: tuple[VariableContract, ...] = ()
    produces: tuple[VariableContract, ...] = ()
    dependencies: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    references: tuple[str, ...] = ()
    deterministic: bool = True
    permits_overwrite: tuple[str, ...] = ()


@dataclass(frozen=True)
class OperatorExecutionContext:
    spec: GeoSpecV2
    software_version: str
    operator_id: str
    rng: np.random.Generator
    seed_lineage: dict[str, Any]


@dataclass
class OperatorResult:
    dataset: xr.Dataset
    diagnostics: dict[str, Any] = field(default_factory=dict)


class ScientificOperatorV2(Protocol):
    metadata: OperatorMetadataV2

    def execute(
        self,
        dataset: xr.Dataset,
        context: OperatorExecutionContext,
    ) -> OperatorResult:
        """Return new scientific variables and diagnostics without hidden mutation."""
