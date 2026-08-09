from geoworld_open.science import run_structural_workflow
from geoworld_open.specs import migrate_v1_to_v2
from geoworld_open.workflow import run_workflow


def test_v1_scenario_keeps_legacy_execution(layered_scenario) -> None:
    result = run_workflow(layered_scenario)
    assert result.scenario.schema_version == "1.0"
    assert "vp_m_s" in result.arrays
    assert "synthetic_seismic" in result.arrays


def test_v1_structural_migration_is_explicit(layered_scenario) -> None:
    migration = migrate_v1_to_v2(layered_scenario)
    result = run_structural_workflow(layered_scenario)
    assert migration.source_schema_version == "1.0"
    assert migration.compatibility_mode == "v1_structural_only"
    assert result.compatibility["mode"] == "v1_structural_only"
    assert result.spec.schema_version == "2.0"
    assert "vp_m_s" not in result.dataset
    assert "synthetic_seismic" not in result.dataset
    assert not result.dataset["reservoir_mask"].any()


def test_v1_co2_target_is_the_only_explicitly_migrated_reservoir(co2_scenario) -> None:
    migration = migrate_v1_to_v2(co2_scenario)
    reservoir_layers = [layer.id for layer in migration.spec.layers if layer.is_reservoir]
    assert reservoir_layers == ["layer_2_storage_sand"]
