import json

import numpy as np
import pytest
import xarray as xr
from pydantic import ValidationError

from geoworld_open.reference import AcousticImpedanceReference
from geoworld_open.sdk import CapabilityRegistry, canonical_json_bytes, model_sha256
from geoworld_open.standard import CapabilitySpec, VariableSpec


def _input_dataset() -> xr.Dataset:
    return xr.Dataset(
        {
            "vp_m_s": (("z", "x"), np.full((2, 3), 2500.0), {"units": "m/s"}),
            "density_kg_m3": (
                ("z", "x"),
                np.full((2, 3), 2200.0),
                {"units": "kg/m^3"},
            ),
        }
    )


def test_capability_contract_and_registry_are_executable() -> None:
    capability = AcousticImpedanceReference()
    spec = CapabilitySpec.model_validate(capability.spec.model_dump())
    registry = CapabilityRegistry()
    registry.register(capability)
    result = registry.execute(spec.capability_id, spec.version, _input_dataset())
    np.testing.assert_allclose(result.dataset["acoustic_impedance"], 5_500_000.0)
    assert result.dataset["acoustic_impedance"].attrs["units"] == "kg/(m^2*s)"
    assert registry.specs() == (spec,)


def test_capability_contract_rejects_duplicate_variables() -> None:
    payload = AcousticImpedanceReference.spec.model_dump(mode="python")
    payload["outputs"] = (
        VariableSpec(name="duplicate", unit="1"),
        VariableSpec(name="duplicate", unit="1"),
    )
    with pytest.raises(ValidationError, match="output names must be unique"):
        CapabilitySpec.model_validate(payload)


def test_contract_serialization_is_canonical_and_hashable() -> None:
    spec = AcousticImpedanceReference.spec
    encoded = canonical_json_bytes(spec)
    assert encoded == canonical_json_bytes(CapabilitySpec.model_validate_json(encoded))
    assert json.loads(encoded)["capability_id"] == "reference.acoustic_impedance"
    assert len(model_sha256(spec)) == 64
