"""Minimal public operator contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np


@dataclass(frozen=True)
class OperatorMetadata:
    name: str
    version: str
    description: str


class ScientificOperator(Protocol):
    metadata: OperatorMetadata

    def run(self, arrays: dict[str, np.ndarray], context: dict[str, Any]) -> dict[str, np.ndarray]:
        """Return arrays contributed by this deterministic operator."""

