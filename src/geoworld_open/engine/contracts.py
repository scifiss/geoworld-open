"""Transparent scientific capability contracts below World semantics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np
import xarray as xr


@dataclass(frozen=True)
class VariableContract:
    name: str
    dims: tuple[str, ...]
    units: str
    dtype_kind: str | None = None


@dataclass(frozen=True)
class CapabilityMetadata:
    capability_id: str
    version: str
    method_id: str
    requires: tuple[VariableContract, ...] = ()
    produces: tuple[VariableContract, ...] = ()
    dependencies: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    references: tuple[str, ...] = ()
    deterministic: bool = True


@dataclass(frozen=True)
class ExecutionContext:
    input_data: object
    capability_id: str
    rng: np.random.Generator
    seed_lineage: dict[str, Any]


@dataclass(frozen=True)
class CapabilityResult:
    dataset: xr.Dataset
    diagnostics: dict[str, Any] = field(default_factory=dict)


class ScientificCapability(Protocol):
    metadata: CapabilityMetadata

    def execute(self, dataset: xr.Dataset, context: ExecutionContext) -> CapabilityResult:
        """Return new numerical representations without mutating inputs."""
        ...
