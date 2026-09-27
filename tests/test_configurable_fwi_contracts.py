"""Portable configurable FWI contract and bounded snapshot checks."""
import pytest
from pydantic import ValidationError

from geoworld_open.client.configurable_fwi import ConfigurableFWIPreview, ConfigurableFWIResult
from geoworld_open.client.intermediate_results import IntermediateResultPolicy
from geoworld_open.client.marmousi_forward import MarmousiForwardPreview, MarmousiForwardResult, MarmousiForwardSettings
from geoworld_open.client.scientific_experiment import ScientificExperimentDraft
from test_marmousi_forward_contracts import experiment, model_preview, resolved_acquisition, plan


def _forward_preview():
    return MarmousiForwardPreview(
        experiment=experiment(), model_preview=model_preview(),
        resolved_acquisition=resolved_acquisition(),
        crop_vp_sha256="a" * 64, geometry_sha256="b" * 64,
        experiment_sha256="d" * 64, settings_sha256="c" * 64,
        execution_plan=plan(), preparation_id="e" * 32,
    )


def test_settings_have_bounded_values_and_origin_for_every_value():
    settings = MarmousiForwardSettings()
    assert (settings.source_frequency_hz, settings.time_samples,
            settings.sample_interval_s, settings.ricker_peak_time_s) == (25, 300, .004, .06)
    assert set(settings.origins) == set(type(settings).model_fields) - {"origins"}
    with pytest.raises(ValidationError):
        MarmousiForwardSettings(source_frequency_hz=10)
    assert MarmousiForwardSettings(time_samples=575).time_samples == 575
    with pytest.raises(ValidationError):
        MarmousiForwardSettings(time_samples=99)
    with pytest.raises(ValidationError):
        MarmousiForwardSettings(origins={"source_frequency_hz": "user_request"})


def test_50_update_snapshot_schedule_and_preview_guard():
    draft = ScientificExperimentDraft(status="ready", execution_intent="run",
                                      inversion={"updates": 50})
    schedule = IntermediateResultPolicy().resolve(50)
    assert schedule == [10, 20, 30, 40, 50]
    preview = ConfigurableFWIPreview(
        experiment=draft, forward=_forward_preview(), execution_plan=plan(),
        snapshot_schedule=schedule, preparation_id="f" * 32, runnable=True,
    )
    assert preview.solver_executed is False
    with pytest.raises(ValidationError):
        ConfigurableFWIPreview.model_validate({**preview.model_dump(),
                                              "snapshot_schedule": [10, 20]})
    with pytest.raises(ValidationError):
        ConfigurableFWIPreview.model_validate({**preview.model_dump(),
                                              "experiment": ScientificExperimentDraft().model_dump()})


def test_result_rejects_forward_input_identity_change():
    forward = MarmousiForwardResult(
        experiment_sha256="d" * 64, crop_vp_sha256="a" * 64,
        model_input_sha256="a" * 64, geometry_sha256="b" * 64,
        wavelet_sha256="e" * 64, observed_shots_sha256="f" * 64,
        settings_sha256="c" * 64, settings=MarmousiForwardSettings(),
        runtime_seconds=1, peak_memory_mib=1, artifacts=[], diagnostics={},
    )
    payload = dict(
        forward=forward, crop_vp_sha256="a" * 64, geometry_sha256="b" * 64,
        observed_shots_sha256="f" * 64, settings_sha256="c" * 64,
        predicted_shots_sha256="1" * 64, residual_shots_sha256="2" * 64,
        initial_vp_sha256="3" * 64, recovered_vp_sha256="4" * 64,
        completed_updates=1, objective_history=[1.0], snapshot_schedule=[1],
        forward_runtime_seconds=1, fwi_runtime_seconds=1, peak_ram_mib=1, peak_vram_mib=0,
    )
    ConfigurableFWIResult(**payload)
    with pytest.raises(ValidationError):
        ConfigurableFWIResult(**{**payload, "observed_shots_sha256": "9" * 64})
