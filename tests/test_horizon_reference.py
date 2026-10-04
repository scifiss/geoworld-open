"""Quantitative tests of the transparent synthetic-only horizon baseline."""
from time import perf_counter

import numpy as np
import pytest
from pydantic import ValidationError

from geoworld_open.benchmarks.horizon import DT_S, array_digest, evaluate, generate_benchmark
from geoworld_open.client.horizon import HorizonTrackRequest
from geoworld_open.reference.horizon import track_section


def request(**patch):
    return HorizonTrackRequest(**{
        "dataset_id": "a" * 24, "view_kind": "inline", "section_number": 1212,
        "seed_trace": 16, "seed_time_s": .408, "window_start_s": .30,
        "window_stop_s": .50, **patch,
    })


@pytest.mark.parametrize("kind,number,seed", [("inline", 1212, 16), ("crossline", 316, 8)])
def test_clean_tracking_accuracy_smoothness_and_repeatability(kind, number, seed):
    benchmark = generate_benchmark()
    section, truth, _ = benchmark.section(kind, number)
    req = request(view_kind=kind, section_number=number, seed_trace=seed, seed_time_s=float(truth[seed]))
    result = track_section(section, DT_S, req)
    assert result["status"] == "complete"
    assert result == track_section(section, DT_S, req)
    assert evaluate(result["picked_time_s"], truth)["rmse_ms"] == 0
    assert np.max(np.abs(np.diff(result["picked_time_s"]))) <= req.max_jump_samples * DT_S + 1e-9
    assert all(req.window_start_s <= value <= req.window_stop_s for value in result["picked_time_s"])
    assert all(value is None for value in result["failure_reasons"])


def test_fault_stops_at_jump_and_does_not_interpolate_or_recover():
    section, truth, _ = generate_benchmark("fault").section("inline", 1212)
    result = track_section(section, DT_S, request())
    assert result["status"] == "partial"
    assert result["picked_time_s"][:32] == truth[:32].tolist()
    assert result["picked_time_s"][32:] == [None] * 32
    assert result["failure_reasons"][32] == "jump_limit_or_weak_waveform"
    assert evaluate(result["picked_time_s"], truth)["failure_rate"] == .5
    # Starting on the other side also stops at the discontinuity, walking left.
    other = track_section(section, DT_S, request(seed_trace=48, seed_time_s=float(truth[48])))
    assert other["picked_time_s"][:32] == [None] * 32
    assert other["picked_time_s"][32:] == truth[32:].tolist()


@pytest.mark.parametrize("case", ["noisy", "stress"])
def test_noise_returns_honest_failures_and_similarity_confidence(case):
    benchmark = generate_benchmark(case)
    section, truth, _ = benchmark.section("inline", 1212)
    result = track_section(section, DT_S, request())
    metrics = evaluate(result["picked_time_s"], truth)
    assert result["status"] in {"partial", "failed"}
    assert metrics["coverage"] < 1
    assert metrics["failure_rate"] >= 1 - metrics["coverage"] - 1e-9
    assert all(0 <= score <= 1 for score in result["confidence"])
    assert all(score == 0 and reason for pick, score, reason in zip(
        result["picked_time_s"], result["confidence"], result["failure_reasons"],
    ) if pick is None)
    assert result == track_section(section, DT_S, request())


def test_generator_is_fixed_seed_and_source_samples_are_never_modified():
    first, second = generate_benchmark("noisy"), generate_benchmark("noisy")
    assert first.parameters == second.parameters
    np.testing.assert_array_equal(first.cube, second.cube)
    np.testing.assert_array_equal(first.truth_s, second.truth_s)
    section, truth, _ = first.section("inline", 1212)
    digest = array_digest(first.cube)
    truth_copy = truth.copy()
    track_section(section, DT_S, request())
    assert array_digest(first.cube) == digest
    np.testing.assert_array_equal(truth, truth_copy)
    # The reference also does not mutate a caller's writable source.
    writable = section.copy()
    expected = writable.copy()
    track_section(writable, DT_S, request())
    np.testing.assert_array_equal(writable, expected)


@pytest.mark.parametrize("patch", [
    {"seed_trace": 99}, {"seed_time_s": .32},
    {"window_start_s": .001, "window_stop_s": .45},
    {"window_start_s": .405, "window_stop_s": .409},
])
def test_bad_seed_or_window_rejected(patch):
    section, _, _ = generate_benchmark().section("inline", 1212)
    with pytest.raises(ValueError):
        track_section(section, DT_S, request(**patch))


@pytest.mark.parametrize("patch", [
    {"window_stop_s": 5}, {"window_stop_s": .1}, {"seed_trace": -1},
    {"seed_time_s": float("nan")}, {"max_jump_samples": 9}, {"view_kind": "subvolume"},
])
def test_invalid_contract_rejected(patch):
    with pytest.raises(ValidationError):
        request(**patch)


def test_runtime_is_bounded_by_input_and_jump_policy():
    # Largest supported section, broadest legal sample window and jump search.
    samples = np.arange(512)
    wavelet = np.exp(-((samples - 100) / 3) ** 2)
    section = np.tile(wavelet[:, None], (1, 256)).astype(np.float32)
    start = perf_counter()
    result = track_section(section, DT_S, request(
        seed_trace=128, seed_time_s=.4, window_start_s=.2, window_stop_s=.712,
        max_jump_samples=8,
    ))
    assert result["status"] == "complete"
    assert perf_counter() - start < 2.0
    for invalid in (np.zeros((513, 2)), np.zeros((128, 257)), np.full((128, 2), np.nan)):
        with pytest.raises(ValueError, match="finite section"):
            track_section(invalid, DT_S, request())


def test_evaluation_counts_missing_and_wrong_picks_separately_from_mae():
    metrics = evaluate([.4, .42, None], [.4, .4, .4])
    assert metrics["mae_ms"] == pytest.approx(10)
    assert metrics["rmse_ms"] == pytest.approx(np.sqrt(200))
    assert metrics["failure_rate"] == pytest.approx(2 / 3)
    assert metrics["coverage"] == pytest.approx(2 / 3)
    assert evaluate([None, None], [.4, .4])["mae_ms"] is None


def test_wrong_selected_event_is_not_silently_corrected_using_truth():
    section, truth, _ = generate_benchmark().section("inline", 1212)
    result = track_section(section, DT_S, request(
        seed_time_s=.576, window_start_s=.50, window_stop_s=.70,
    ))
    assert result["status"] == "complete"
    metrics = evaluate(result["picked_time_s"], truth)
    assert metrics["mae_ms"] == pytest.approx(168.)
    assert metrics["failure_rate"] == 1.
