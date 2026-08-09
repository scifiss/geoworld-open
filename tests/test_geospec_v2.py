import pytest
from pydantic import ValidationError

from geoworld_open.specs import GeoSpecV2


def _payload(spec):
    return spec.model_dump(mode="python")


def test_unknown_facies_reference_is_rejected(structural_v2_scenario) -> None:
    payload = _payload(structural_v2_scenario)
    payload["layers"][0]["facies_id"] = "missing"
    with pytest.raises(ValidationError, match="unknown facies IDs"):
        GeoSpecV2.model_validate(payload)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda value: value["layers"][1].update(id=value["layers"][0]["id"]), "layer IDs"),
        (lambda value: value["facies"][1].update(code=value["facies"][0]["code"]), "facies codes"),
        (
            lambda value: value["structures"][1].update(id=value["structures"][0]["id"]),
            "structure IDs",
        ),
    ],
)
def test_duplicate_ids_and_codes_are_rejected(structural_v2_scenario, mutate, message) -> None:
    payload = _payload(structural_v2_scenario)
    mutate(payload)
    with pytest.raises(ValidationError, match=message):
        GeoSpecV2.model_validate(payload)


def test_invalid_physical_range_is_rejected(structural_v2_scenario) -> None:
    payload = _payload(structural_v2_scenario)
    payload["layers"][0]["porosity_fraction"] = 1.1
    with pytest.raises(ValidationError, match="less than or equal to 0.7"):
        GeoSpecV2.model_validate(payload)


def test_layer_grid_inconsistency_is_rejected(structural_v2_scenario) -> None:
    payload = _payload(structural_v2_scenario)
    payload["layers"][0]["thickness_m"] += 1.0
    with pytest.raises(ValidationError, match="layer thicknesses total"):
        GeoSpecV2.model_validate(payload)


def test_invalid_fault_geometry_is_rejected(structural_v2_scenario) -> None:
    payload = _payload(structural_v2_scenario)
    payload["structures"][1]["x_position_m"] = 1.0e9
    with pytest.raises(ValidationError, match="outside the grid"):
        GeoSpecV2.model_validate(payload)


def test_extra_fields_are_forbidden(structural_v2_scenario) -> None:
    payload = _payload(structural_v2_scenario)
    payload["automatic_geology_inference"] = True
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        GeoSpecV2.model_validate(payload)
