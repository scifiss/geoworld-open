"""Small contract/pinning tests: no full scientific run in routine CI."""
import hashlib
import json

import pytest
from pydantic import ValidationError

from geoworld_open.client.reference_experiment import ReferenceSelection, ReferencePreviewRequest
from geoworld_open.reference.deepwave_marmousi.definition import reference_definition, configuration_hash
from geoworld_open.reference.deepwave_marmousi.runner import SOURCE_HASHES, verify_sources, verify_vp, verify_forward


@pytest.mark.parametrize("kind", ["forward", "rtm"])
def test_pinned_upstream_source_identity(kind):
    assert hashlib.sha256(verify_sources(kind).read_bytes()).hexdigest() == SOURCE_HASHES[kind]


def test_exact_reference_settings_and_detached_definition():
    definition = reference_definition()
    assert definition["dataset"]["shape_xz"] == [2301, 751]
    assert definition["migration"]["shape_xz"] == [1151, 376]
    assert definition["migration"]["smoothing_variable"] == "slowness"
    assert definition["rtm"]["accuracy"] == 4
    assert definition["forward"]["accuracy"] == 8
    assert definition["rtm"]["background_subtraction"] is False
    assert definition["rtm"]["n_epochs"] == 1
    assert definition["rtm"]["nonempty_batches"] == 39
    assert definition["rtm"]["learning_rate"] == 1e9
    before = configuration_hash(definition)
    definition["acquisition"]["shots"] = 10
    assert configuration_hash(definition) != before
    assert reference_definition()["acquisition"]["shots"] == 115


@pytest.mark.parametrize("bad", [{"coordinates": [[1, 2]]}, {"reference_id": "marmousi2"}, {"action": "execute_code"},
                                  {"requested_changes": [{"parameter": "shots", "value": True, "user_text": "true"}]},
                                  {"requested_changes": [{"parameter": "shots", "value": "10", "user_text": "10"}]},
                                  {"requested_changes": [{"parameter": "shots", "value": float("nan"), "user_text": "nan"}]}])
def test_selection_rejects_unknown_identity_coordinates_and_nonfinite(bad):
    with pytest.raises(ValidationError):
        ReferenceSelection.model_validate(bad)


def test_preview_does_not_mix_user_prompt_with_structured_input():
    with pytest.raises(ValidationError):
        ReferencePreviewRequest(prompt="run", selection=ReferenceSelection())
    with pytest.raises(ValidationError):
        ReferencePreviewRequest()


def test_dataset_preflight_refuses_wrong_size_and_identity(tmp_path):
    pytest.importorskip("numpy")
    path = tmp_path / "vp.bin"
    path.write_bytes(b"HTML download page")
    with pytest.raises(ValueError, match="exactly"):
        verify_vp(path)
    with path.open("wb") as stream:
        stream.truncate(2301 * 751 * 4)
    with pytest.raises(ValueError, match="SHA-256"):
        verify_vp(path)


def test_rtm_requires_successful_reference_not_probe(tmp_path):
    (tmp_path / "reference_run.json").write_text(json.dumps({"status": "succeeded", "kind": "forward", "classification": "reduced_reference_adaptation"}))
    with pytest.raises(ValueError, match="completed, unchanged"):
        verify_forward(tmp_path)
