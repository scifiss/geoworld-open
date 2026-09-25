"""Pure presentation semantics for configurable FWI."""
import numpy as np
import pytest

from geoworld_open.client.configurable_fwi import ConfigurableFWIResult
from geoworld_open.client.marmousi_forward import RecordingTimeAdequacy
from geoworld_open.studio_configurable_fwi import gather_figure, metric_percent_change
from geoworld_open.studio_fwi_snapshots import snapshot_caption


@pytest.mark.parametrize("step,expected", [
    (10, "Intermediate FWI result after 10/50 optimizer updates; not the final result."),
    (40, "Intermediate FWI result after 40/50 optimizer updates; not the final result."),
    (50, "Final FWI result after 50/50 optimizer updates."),
])
def test_snapshot_caption_distinguishes_final(step, expected):
    assert snapshot_caption(step, 50) == expected


def test_gather_uses_physical_axes_and_metric_is_deterministic():
    figure = gather_figure(
        np.zeros((3, 4)), receiver_x_m=np.array([1000., 1004., 1008.]),
        time_s=np.array([0., .004, .008, .012]), limit=1., title="Observed",
    )
    assert list(figure.data[0].x) == [1000., 1004., 1008.]
    assert list(figure.data[0].y) == [0., .004, .008, .012]
    assert figure.layout.xaxis.title.text == "Receiver x (m)"
    assert figure.layout.yaxis.title.text == "Time (s)"
    assert metric_percent_change(10., 7.5) == 25.


def test_recording_adequacy_contract_and_truth_identity_guard():
    value = RecordingTimeAdequacy(
        recording_time_s=2.3, estimated_required_time_s=2.24, margin_s=.06,
        adequacy="sufficient", origin="geoworld_default", maximum_offset_m=2400,
        minimum_vp_mps=1500, rationale="deterministic fixture",
    )
    assert value.adequacy == "sufficient"
    assert ConfigurableFWIResult.model_fields["true_vp_sha256"].is_required() is False
