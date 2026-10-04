"""PUBLIC_BENCHMARK: small deterministic GeoWorld post-stack horizon cube.

Ricker wavelets are sampled at known integer horizon times, with a separated
secondary reflector and optional Gaussian noise or a 48 ms discontinuity.
This is an uncalibrated reference fixture, not a wave-equation simulation.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import numpy as np

VERSION = "geoworld-horizon-synthetic-v0"
SEED = 20261003
CASES = {"clean": 0., "noisy": .15, "fault": .05, "stress": .65}
DT_S = .004


def array_digest(array: np.ndarray) -> str:
    digest = hashlib.sha256()
    digest.update(str(array.shape).encode())
    digest.update(array.dtype.str.encode())
    digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


@dataclass(frozen=True)
class HorizonBenchmark:
    cube: np.ndarray  # inline, crossline, time
    truth_s: np.ndarray  # inline, crossline
    parameters: dict

    def section(self, kind: str, number: int):
        if kind == "inline" and 1200 <= number < 1224:
            return self.cube[number - 1200].T, self.truth_s[number - 1200], np.arange(300, 364)
        if kind == "crossline" and 300 <= number < 364:
            return self.cube[:, number - 300].T, self.truth_s[:, number - 300], np.arange(1200, 1224)
        raise ValueError("Select an existing synthetic inline (1200–1223) or crossline (300–363)")


def generate_benchmark(case: str = "clean") -> HorizonBenchmark:
    if case not in CASES:
        raise ValueError("Unknown synthetic horizon benchmark case")
    y, x = np.indices((24, 64))
    samples = np.rint(94 + 5 * np.sin(x / 12) + .25 * y).astype(int)
    if case == "fault":
        samples = samples + (x >= 32) * 12
    t = np.arange(256) * DT_S

    def ricker(centers):
        a = (np.pi * 30 * (t - centers[..., None])) ** 2
        return (1 - 2 * a) * np.exp(-a)

    cube = ricker(samples * DT_S) + .6 * ricker((samples + 42) * DT_S)
    cube += np.random.default_rng(SEED).normal(0, CASES[case], cube.shape)
    cube = cube.astype(np.float32)
    truth = samples * DT_S
    cube.setflags(write=False)
    truth.setflags(write=False)
    return HorizonBenchmark(cube, truth, {
        "generator": VERSION, "case": case, "random_seed": SEED,
        "shape": [24, 64, 256], "sample_interval_s": DT_S,
        "ricker_frequency_hz": 30., "noise_std": CASES[case],
        "fault_throw_ms": 48. if case == "fault" else 0.,
        "secondary_reflector_offset_ms": 168., "source_sha256": array_digest(cube),
    })


def evaluate(picks_s, truth_s, tolerance_ms: float = 8.) -> dict:
    """MAE/RMSE cover returned picks; failure includes absent or inaccurate picks."""
    truth = np.asarray(truth_s, dtype=float)
    picks = np.array([np.nan if value is None else value for value in picks_s])
    if truth.shape != picks.shape or not truth.size or not np.isfinite(truth).all():
        raise ValueError("Evaluation needs one finite synthetic truth time per trace")
    valid = np.isfinite(picks)
    errors = (picks[valid] - truth[valid]) * 1000
    failures = ~valid
    failures[valid] = np.abs(errors) > tolerance_ms + 1e-9
    return {
        "mae_ms": float(np.abs(errors).mean()) if errors.size else None,
        "rmse_ms": float(np.sqrt(np.mean(errors ** 2))) if errors.size else None,
        "failure_rate": float(failures.mean()), "coverage": float(valid.mean()),
        "picked_traces": int(valid.sum()), "total_traces": int(truth.size),
        "failure_tolerance_ms": tolerance_ms,
    }


def save_evaluation_figure(section, truth_s, result, path: Path) -> None:
    """One exportable figure, with missing picks explicitly visible in errors."""
    from matplotlib.figure import Figure

    values = np.asarray(section)
    horizontal = np.asarray(result.horizontal_coordinates)
    picks = np.array([np.nan if value is None else value for value in result.picked_time_s])
    figure = Figure(figsize=(11, 7), layout="constrained")
    top, bottom = figure.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    limit = np.percentile(np.abs(values), 99) or 1.
    top.imshow(values, aspect="auto", cmap="gray", vmin=-limit, vmax=limit,
               extent=[horizontal[0] - .5, horizontal[-1] + .5,
                       (values.shape[0] - .5) * DT_S, -.5 * DT_S])
    top.plot(horizontal, truth_s, color="cyan", lw=2, label="Synthetic truth")
    top.plot(horizontal, picks, color="orangered", lw=1.5, marker=".", label="Seeded pick")
    seed = result.request.seed_trace
    top.plot(horizontal[seed], result.request.seed_time_s, "y*", ms=13, label="User seed")
    top.axhspan(result.request.window_start_s, result.request.window_stop_s, alpha=.1, color="yellow")
    top.set_ylabel("Two-way time (s)")
    top.legend(loc="lower left")
    top.set_title(f"Synthetic horizon V0 · {result.provenance['benchmark']['case']} · {result.status}")
    bottom.axhline(0, color="gray", lw=1)
    bottom.plot(horizontal, (picks - truth_s) * 1000, ".-", color="orangered", label="Pick error")
    missing = ~np.isfinite(picks)
    bottom.plot(horizontal[missing], np.zeros(missing.sum()), "kx", label="No pick")
    bottom.set_ylabel("Error (ms)")
    bottom.set_xlabel("Crossline" if result.request.view_kind == "inline" else "Inline")
    bottom.legend(loc="upper right")
    metrics = result.metrics
    figure.suptitle(f"MAE {metrics['mae_ms']:.2f} ms · RMSE {metrics['rmse_ms']:.2f} ms · "
                    f"failure {metrics['failure_rate']:.1%} (missing or >8 ms)")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=150)


def main() -> None:
    """Run with python -m geoworld_open.benchmarks.horizon [output-directory]."""
    import sys
    from time import perf_counter
    from geoworld_open.client.horizon import HorizonTrackRequest
    from geoworld_open.reference.horizon import ALGORITHM_VERSION, track_section, tracking_parameters

    output = Path(sys.argv[1] if len(sys.argv) > 1 else "runs/horizon-v0")
    output.mkdir(parents=True, exist_ok=True)
    report = {}
    for case in CASES:
        benchmark = generate_benchmark(case)
        section, truth, horizontal = benchmark.section("inline", 1212)
        request = HorizonTrackRequest(
            dataset_id=hashlib.sha256((VERSION + case).encode()).hexdigest()[:24],
            view_kind="inline", section_number=1212, seed_trace=16,
            seed_time_s=float(truth[16]), window_start_s=.30, window_stop_s=.50,
        )
        start = perf_counter()
        tracked = track_section(section, DT_S, request)
        # Evaluation is deliberately separate from the tracker, which never sees truth.
        from geoworld_open.client.horizon import HorizonTrackResult
        result = HorizonTrackResult(
            request=request, **tracked, horizontal_coordinates=horizontal.tolist(),
            truth_time_s=truth.tolist(),
            errors_ms=[None if value is None else (value - actual) * 1000
                       for value, actual in zip(tracked["picked_time_s"], truth)],
            metrics=evaluate(tracked["picked_time_s"], truth),
            provenance={"benchmark": benchmark.parameters, "algorithm": ALGORITHM_VERSION,
                        "parameters": tracking_parameters(), "section_sha256": array_digest(section),
                        "truth_used_for_tracking": False,
                        "source_unchanged": True, "derived_result": True},
        )
        report[case] = {"metrics": result.metrics, "runtime_s": perf_counter() - start,
                        "parameters": benchmark.parameters}
        (output / f"{case}.json").write_text(result.model_dump_json(indent=2) + "\n")
        if case == "fault":
            save_evaluation_figure(section, truth, result, output / "evaluation.png")
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
