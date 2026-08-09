"""Example plugin implementing the public operator contract."""

from __future__ import annotations

from typing import Any

import numpy as np

from .base import OperatorMetadata


class MockScaleOperator:
    metadata = OperatorMetadata(
        name="mock_scale",
        version="1.0",
        description="Public example plugin that scales one named array.",
    )

    def __init__(self, source: str, output: str, factor: float) -> None:
        self.source = source
        self.output = output
        self.factor = factor

    def run(self, arrays: dict[str, np.ndarray], context: dict[str, Any]) -> dict[str, np.ndarray]:
        del context
        return {self.output: np.asarray(arrays[self.source]) * self.factor}

