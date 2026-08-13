"""Small public registry for GeoWorld-compatible capability plugins."""

from __future__ import annotations

import xarray as xr

from geoworld_open.standard import CapabilityContext, CapabilityRunResult, CapabilitySpec, PhysicsCapability


class CapabilityRegistrationError(ValueError):
    """Raised when a plugin cannot be registered unambiguously."""


class CapabilityRegistry:
    """In-process plugin registry keyed by stable capability ID and version."""

    def __init__(self) -> None:
        self._capabilities: dict[tuple[str, str], PhysicsCapability] = {}

    def register(self, capability: PhysicsCapability) -> None:
        if not isinstance(capability, PhysicsCapability):
            raise CapabilityRegistrationError("capability must implement PhysicsCapability")
        spec = CapabilitySpec.model_validate(capability.spec)
        key = (spec.capability_id, spec.version)
        if key in self._capabilities:
            raise CapabilityRegistrationError(f"duplicate capability registration: {key!r}")
        self._capabilities[key] = capability

    def get(self, capability_id: str, version: str) -> PhysicsCapability:
        try:
            return self._capabilities[(capability_id, version)]
        except KeyError as exc:
            raise KeyError(f"capability unavailable: {(capability_id, version)!r}") from exc

    def specs(self) -> tuple[CapabilitySpec, ...]:
        return tuple(
            CapabilitySpec.model_validate(item.spec)
            for _, item in sorted(self._capabilities.items())
        )

    def execute(
        self,
        capability_id: str,
        version: str,
        dataset: xr.Dataset,
        *,
        context: CapabilityContext | None = None,
    ) -> CapabilityRunResult:
        capability = self.get(capability_id, version)
        result = capability.execute(dataset, context or CapabilityContext())
        if not isinstance(result, CapabilityRunResult):
            raise TypeError("capability returned a non-standard result")
        return result
