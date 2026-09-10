"""Comparator unit fixtures only, explicitly not full Marmousi reproductions."""
import json

import numpy as np
import pytest

from geoworld_open.reference.deepwave_marmousi import compare


@pytest.fixture
def pair(tmp_path, monkeypatch):
    # Bypass the full-case verifier only to isolate comparator behavior. Real
    # entry points verify shape, source pins, checksums and settings first.
    monkeypatch.setattr(compare, "checked_report", lambda *_: {"forward_data_sha256": "test-fixture"})
    names = ["true_velocity.npy", "migration_velocity.npy", "source_locations.npy", "receiver_locations.npy",
             "source_amplitudes.npy", "direct_arrival_mask.npy", "masked_data.npy", "raw_rtm_image.npy", "accumulated_gradient.npy"]
    directories = [tmp_path / "standalone-unit-fixture", tmp_path / "candidate-unit-fixture"]
    for directory in directories:
        directory.mkdir()
        (directory / "settings.json").write_text(json.dumps({"unit_test_only": True}))
        for name in names:
            np.save(directory / name, np.ones((3, 2), dtype="float32"))
    return directories


def test_raw_array_comparison_matches(pair):
    report = compare.compare_runs(*pair)
    assert report["passed"] and report["settings_equal"] and report["forward_data_equal"]
    assert all(a["max_abs_error"] == 0 for a in report["arrays"].values())


@pytest.mark.parametrize("name", ["raw_rtm_image.npy", "accumulated_gradient.npy", "masked_data.npy", "source_locations.npy"])
def test_raw_or_geometry_difference_fails(pair, name):
    array = np.load(pair[1] / name)
    array[0, 0] += .01
    np.save(pair[1] / name, array)
    report = compare.compare_runs(*pair)
    assert not report["passed"] and not report["arrays"][name]["passed"]


def test_nan_and_configuration_difference_fail(pair):
    array = np.load(pair[1] / "raw_rtm_image.npy")
    array[0, 0] = np.nan
    np.save(pair[1] / "raw_rtm_image.npy", array)
    (pair[1] / "settings.json").write_text(json.dumps({"unit_test_only": True, "n_epochs": 2}))
    report = compare.compare_runs(*pair)
    assert not report["passed"] and not report["settings_equal"]


def test_self_comparison_and_weakened_tolerance_are_rejected(pair):
    with pytest.raises(ValueError, match="own independent"):
        compare.compare_runs(pair[0], pair[0])
    with pytest.raises(ValueError, match="frozen"):
        compare.compare_runs(*pair, rtol=.1)
