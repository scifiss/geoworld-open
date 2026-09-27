"""Pure presentation semantics for configurable FWI."""
from types import SimpleNamespace

import numpy as np
import pytest

from geoworld_open.client.configurable_fwi import ConfigurableFWIResult
from geoworld_open.client.marmousi_forward import RecordingTimeAdequacy
from geoworld_open.client.scientific_experiment import RequestedOutputs
from geoworld_open.studio_configurable_fwi import (
    gather_figure,
    human_output_summary,
    metric_percent_change,
    recommendation_line,
    recording_status_line,
)
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


def test_configurable_fwi_uses_human_facing_output_summary():
    outputs = RequestedOutputs(
        observed_shot_gather=True,
        predicted_shot_gather=True,
        residual=True,
    )
    summary = human_output_summary(outputs)
    assert summary == "Velocity models · Seismic gathers · Objective history"
    assert "initial_velocity" not in summary
    assert "observed_shot_gather" not in summary


def test_configurable_fwi_compact_recording_and_resource_lines():
    adequacy = RecordingTimeAdequacy(
        recording_time_s=2.3, estimated_required_time_s=2.216, margin_s=.084,
        adequacy="sufficient", origin="geoworld_default", maximum_offset_m=2400,
        minimum_vp_mps=1500, rationale="deterministic fixture",
    )
    plan = SimpleNamespace(
        resolved_device="cuda",
        scientific_mode="modified_experiment",
        estimate=SimpleNamespace(runtime_seconds=(240, 1140)),
    )
    forward_plan = SimpleNamespace(estimate=SimpleNamespace(runtime_seconds=(18, 270)))
    preview = SimpleNamespace(
        execution_plan=plan,
        forward=SimpleNamespace(execution_plan=forward_plan),
    )
    assert recording_status_line(adequacy) == "Recording time sufficient · 2.30 s"
    assert recommendation_line(preview) == "CUDA · estimated 4.3–23.5 min · modified experiment"
