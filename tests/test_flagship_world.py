import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from geoworld_open.domains.geoscience.flagship import (
    FlagshipSpec,
    bootstrap_flagship_semantics,
    compile_flagship_input,
    canonical_flagship_input_bytes,
    flagship_input_sha256,
    load_flagship_spec,
    run_flagship_world,
)
from geoworld_open.domains.geoscience.flagship.integration import (
    BASELINE_STATE_ID,
    FLAGSHIP_INPUT_REPRESENTATION_ID,
    PERTURBED_STATE_ID,
    STRUCTURAL_STATE_ID,
    BaselineTransition,
)
from geoworld_open.domains.geoscience.structural import run_compiled_structural_world
from geoworld_open.world import Observation, SubjectKind, WorldState, apply_transition


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "scenarios" / "flagship_faulted_reservoir.yaml"


def _spec() -> FlagshipSpec:
    return load_flagship_spec(EXAMPLE)


def _result():
    return run_flagship_world(_spec())


def _changed_spec(path: tuple[str, ...], value) -> FlagshipSpec:
    payload = _spec().model_dump(mode="python")
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return FlagshipSpec.model_validate(payload)


def test_flagship_authoring_rejects_implicit_or_invalid_semantics() -> None:
    with pytest.raises(ValidationError, match="explicit reservoir role"):
        _changed_spec(("reservoir_region", "formation_id"), "upper_shale")
    with pytest.raises(ValidationError, match="unknown Fault"):
        _changed_spec(("reservoir_region", "intersecting_fault_id"), "missing_fault")


def test_exact_flagship_input_is_canonical_complete_and_world_bound() -> None:
    compiled = compile_flagship_input(_spec())
    result = _result()
    representation = next(
        item
        for item in result.world.representations
        if item.representation_id == FLAGSHIP_INPUT_REPRESENTATION_ID
    )
    assert representation.content_sha256 == flagship_input_sha256(compiled)
    assert representation.content_sha256 == hashlib.sha256(
        canonical_flagship_input_bytes(compiled)
    ).hexdigest()
    payload = json.loads(canonical_flagship_input_bytes(compiled))
    assert payload["structural"]["formations"][1]["porosity_fraction"] == 0.24
    assert payload["reservoir_region"]["formation_id"] == "reservoir_sand"
    assert payload["well"]["x_m"] == 700.0
    assert payload["baseline"]["pressure_reference_pa"] == 101325.0
    assert payload["perturbation"]["maximum_delta_pressure_pa"] == 2000000.0
    assert payload["observation"]["noise_seed"] == 20260812


def test_reservoir_region_and_well_are_entities_distinct_from_arrays() -> None:
    result = _result()
    entities = {item.entity_id: item for item in result.world.entities}
    assert entities["reservoir-region:r1"].entity_type == "geoscience:reservoir_region"
    assert entities["well:w1"].entity_type == "geoscience:well"

    reservoir_binding = next(
        item
        for item in result.world.field_bindings
        if item.binding_id == "binding:reservoir_selection:structural-final"
    )
    trajectory = next(
        item
        for item in result.world.representations
        if item.representation_id == "representation:flagship-well-trajectory"
    )
    assert reservoir_binding.subject.kind == SubjectKind.SUPPORT
    assert reservoir_binding.subject.subject_id != "reservoir-region:r1"
    assert len(trajectory.subjects) == 1
    assert trajectory.subjects[0].kind == SubjectKind.ENTITY
    assert trajectory.subjects[0].subject_id == "well:w1"


def test_flagship_relations_use_persistent_semantic_ids() -> None:
    result = _result()
    triples = {
        (item.source_entity_id, item.relation_type, item.target_entity_id)
        for item in result.world.relations
    }
    assert ("reservoir-region:r1", "geoscience:part_of", "formation:reservoir_sand") in triples
    assert ("well:w1", "geoscience:penetrates", "reservoir-region:r1") in triples
    assert ("well:w1", "geoscience:penetrates", "formation:reservoir_sand") in triples
    assert ("fault:fault_f1", "geoscience:intersects", "reservoir-region:r1") in triples
    assert ("fault:fault_f1", "geoscience:intersects", "formation:reservoir_sand") in triples


def test_state_lineage_is_immutable_and_entities_persist() -> None:
    result = _result()
    assert result.baseline_world.state(BASELINE_STATE_ID).parent_state_id == STRUCTURAL_STATE_ID
    assert result.world.state(PERTURBED_STATE_ID).parent_state_id == BASELINE_STATE_ID
    assert result.world.state(BASELINE_STATE_ID) == result.baseline_world.state(BASELINE_STATE_ID)
    assert BASELINE_STATE_ID not in {item.state_id for item in result.enriched_world.states}
    assert PERTURBED_STATE_ID not in {item.state_id for item in result.baseline_world.states}
    expected_entities = tuple(item.entity_id for item in result.enriched_world.entities)
    assert tuple(item.entity_id for item in result.world.entities) == expected_entities
    assert result.world.state(BASELINE_STATE_ID).valid_from.relative_value == 0.0
    assert result.world.state(PERTURBED_STATE_ID).valid_from.relative_value == 30.0


def test_baseline_pressure_and_temperature_obey_explicit_equations() -> None:
    result = _result()
    config = result.flagship_input.baseline
    depth = result.baseline_dataset.coords["depth"].values
    reservoir = result.structural_dataset["reservoir_selection"].values
    expected_pressure = config.pressure_reference_pa + (
        config.reference_density_kg_m3
        * config.gravity_m_s2
        * (depth - config.pressure_reference_depth_m)
    )
    expected_pressure = np.broadcast_to(
        expected_pressure[:, None], reservoir.shape
    ).astype(float, copy=True)
    expected_pressure[~reservoir] = np.nan
    expected_temperature = config.temperature_reference_deg_c + (
        config.geothermal_gradient_deg_c_per_m
        * (depth - config.temperature_reference_depth_m)
    )
    np.testing.assert_allclose(
        result.baseline_dataset["pressure"], expected_pressure, equal_nan=True
    )
    np.testing.assert_allclose(
        result.baseline_dataset["temperature"],
        np.broadcast_to(expected_temperature[:, None], reservoir.shape),
    )


def test_pressure_perturbation_obeys_equation_and_reservoir_mask() -> None:
    result = _result()
    config = result.flagship_input.perturbation
    x = result.perturbed_dataset.coords["x"].values
    depth = result.perturbed_dataset.coords["depth"].values
    xx, zz = np.meshgrid(x, depth)
    reservoir = result.structural_dataset["reservoir_selection"].values
    expected = config.maximum_delta_pressure_pa * np.exp(
        -0.5
        * (
            ((xx - config.center_x_m) / config.sigma_x_m) ** 2
            + ((zz - config.center_depth_m) / config.sigma_depth_m) ** 2
        )
    )
    expected = np.where(reservoir, expected, 0.0)
    np.testing.assert_allclose(result.perturbed_dataset["pressure_perturbation"], expected)
    assert np.all(result.perturbed_dataset["pressure_perturbation"].values[~reservoir] == 0.0)
    np.testing.assert_allclose(
        result.perturbed_dataset["pressure"],
        result.baseline_dataset["pressure"] + expected,
        equal_nan=True,
    )
    np.testing.assert_array_equal(
        result.perturbed_dataset["temperature"],
        result.baseline_dataset["temperature"],
    )
    perturbed_bindings = {
        item.field_definition_id
        for item in result.world.field_bindings
        if item.world_state_id == PERTURBED_STATE_ID
    }
    assert perturbed_bindings == {
        "field:pressure",
        "field:pressure_perturbation",
        "field:temperature",
    }


def test_observation_is_evidence_with_correct_sampling_and_lineage() -> None:
    result = _result()
    observation = result.observation
    assert isinstance(observation, Observation)
    assert not isinstance(observation, WorldState)
    assert observation.status.value == "synthetic"
    assert {(item.kind, item.subject_id) for item in observation.subjects} == {
        (SubjectKind.ENTITY, "well:w1"),
        (SubjectKind.FIELD_BINDING, "binding:pressure:flagship-perturbed"),
        (SubjectKind.WORLD_STATE, PERTURBED_STATE_ID),
    }
    x = result.perturbed_dataset.coords["x"].values
    depth = result.perturbed_dataset.coords["depth"].values
    x_index = int(np.argmin(np.abs(x - result.flagship_input.well.x_m)))
    for row in result.observation_rows:
        depth_index = int(np.argmin(np.abs(depth - row.sample_depth_m)))
        assert row.true_model_pressure_pa == pytest.approx(
            float(result.perturbed_dataset["pressure"].values[depth_index, x_index])
        )

    provenance = {item.provenance_id: item for item in result.world.provenance}
    observation_provenance = provenance["provenance:flagship-pressure-observation"]
    assert any(
        item.kind == SubjectKind.REPRESENTATION
        and item.subject_id == FLAGSHIP_INPUT_REPRESENTATION_ID
        for item in observation_provenance.inputs
    )
    assert "provenance:flagship-pressure-perturbation" in (
        observation_provenance.parent_provenance_ids
    )
    evidence = next(
        item for item in result.world.representations if item.ref == observation.representation
    )
    assert evidence.derived_from == (
        result.perturbed_bundle.representation.ref,
        next(
            item.ref
            for item in result.world.representations
            if item.representation_id == "representation:flagship-well-trajectory"
        ),
    )
    with pytest.raises(ValidationError):
        evidence.version = "v2"


def test_flagship_run_is_deterministic_and_noise_seed_changes_noise_only() -> None:
    first = _result()
    second = _result()
    assert first.world.model_dump_json() == second.world.model_dump_json()
    assert first.observation_bytes == second.observation_bytes
    changed = run_flagship_world(
        _changed_spec(("observation", "noise_seed"), 20260813)
    )
    np.testing.assert_array_equal(
        first.perturbed_dataset["pressure"], changed.perturbed_dataset["pressure"]
    )
    assert [item.true_model_pressure_pa for item in first.observation_rows] == [
        item.true_model_pressure_pa for item in changed.observation_rows
    ]
    assert [item.observed_pressure_pa for item in first.observation_rows] != [
        item.observed_pressure_pa for item in changed.observation_rows
    ]


@pytest.mark.parametrize(
    ("path", "value"),
    (
        (("well", "x_m"), 710.0),
        (("baseline", "pressure_reference_pa"), 120000.0),
        (("perturbation", "maximum_delta_pressure_pa"), 1500000.0),
        (("observation", "noise_sigma_pa"), 50000.0),
    ),
)
def test_post_bootstrap_changed_flagship_input_is_rejected(path, value) -> None:
    original = compile_flagship_input(_spec())
    structural_result = run_compiled_structural_world(original.structural)
    world, _ = bootstrap_flagship_semantics(structural_result, original)
    changed = compile_flagship_input(_changed_spec(path, value))
    before = world.model_dump_json()
    transition = BaselineTransition(changed, structural_result.stratigraphy_bundle)
    with pytest.raises(ValueError, match="does not match"):
        apply_transition(world, STRUCTURAL_STATE_ID, transition)
    assert transition.bundle is None
    assert world.model_dump_json() == before
    assert len(world.states) == 2
    assert len(world.field_bindings) == 10
    assert len(world.representations) == 5
    assert flagship_input_sha256(original) != flagship_input_sha256(changed)
