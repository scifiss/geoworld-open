"""Stable, namespace-derived random generators and seed lineage."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import numpy as np


def _namespace_words(namespace: str) -> tuple[int, ...]:
    digest = hashlib.sha256(namespace.encode("utf-8")).digest()
    return tuple(int.from_bytes(digest[index : index + 4], "big") for index in range(0, 16, 4))


@dataclass(frozen=True)
class SeedManager:
    root_seed: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "_root", np.random.SeedSequence(self.root_seed))

    def seed_sequence(self, namespace: str, realization: int | None = None) -> np.random.SeedSequence:
        suffix = _namespace_words(namespace)
        if realization is not None:
            if realization < 0:
                raise ValueError("realization must be non-negative")
            suffix = (*suffix, realization)
        return np.random.SeedSequence(
            entropy=self._root.entropy,
            spawn_key=(*self._root.spawn_key, *suffix),
        )

    def generator(self, namespace: str, realization: int | None = None) -> np.random.Generator:
        return np.random.default_rng(self.seed_sequence(namespace, realization))

    def lineage(self, namespace: str, realization: int | None = None) -> dict[str, Any]:
        sequence = self.seed_sequence(namespace, realization)
        return {
            "root_entropy": int(self.root_seed),
            "namespace": namespace,
            "realization": realization,
            "spawn_key": [int(value) for value in sequence.spawn_key],
            "state_preview": [int(value) for value in sequence.generate_state(4)],
        }
