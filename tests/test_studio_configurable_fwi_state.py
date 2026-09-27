from types import SimpleNamespace

from geoworld_open.client.scientific_experiment import ScientificExperimentDraft
from geoworld_open.studio_configurable_fwi import (
    experiment_submission_identity,
    submitted_experiment_is_active,
)


def _draft(updates=50):
    return ScientificExperimentDraft.model_validate({
        "model": {
            "x_start_m": 1000., "x_stop_m": 3400.,
            "z_start_m": 0., "z_stop_m": 1000.,
        },
        "acquisition": {"shots": 20, "receivers": 100},
        "inversion": {"updates": updates},
        "execution_intent": "run",
        "status": "ready",
    })


def _session(draft, status=None):
    return {
        "last_submitted_mode_hint": "configurable_marmousi_fwi",
        "last_submitted_prompt": "run it",
        "last_submitted_experiment_sha256": experiment_submission_identity(draft),
        "last_job_id": "a" * 32,
        "last_job": None if status is None else SimpleNamespace(status=status),
    }


def test_duplicate_guard_keys_on_typed_experiment_and_allows_failed_retry():
    original = _draft()
    assert submitted_experiment_is_active(_session(original), "run it", original)
    assert not submitted_experiment_is_active(_session(original), "run it", _draft(75))
    assert not submitted_experiment_is_active(
        _session(original, status="failed"), "run it", original,
    )
    assert submitted_experiment_is_active(
        _session(original, status="succeeded"), "run it", original,
    )
