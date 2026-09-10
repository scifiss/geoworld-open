"""Standalone, opt-in recorder for two unmodified upstream programs.

Run this file directly: it does not import GeoWorld, initialize a service, or
download data. Resource limits affect execution permission, not the experiment.
This is a benchmark recorder, not a job scheduler or a replacement orchestrator.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import inspect
import json
import os
from pathlib import Path
import platform
import resource
import runpy
import shutil
import signal
import sys
import time

REFERENCE_COMMIT = "7dbaeda5fdfbff2a6d579dcc9f7f18488c5e6084"
VP_SHA256 = "f4302792e84bb7ddbdc9d4d0f963b9df32d9f648960084884127e186119b99dd"
SOURCE_HASHES = {
    "forward": "3c74e0a2b52b09360f6226c83d6a0e745d2ac7d41eb920d3ecaa1b276b10ad2d",
    "rtm": "ebbdc144ac7df2e00b1213dd7011550cd63d92b9520907bd4ac8f66acce5f9cd",
}
REFERENCE_ID = "deepwave-marmousi1-rtm-v0.0.26-r1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value) -> None:
    with path.open("w") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def verify_vp(path: Path) -> dict:
    import numpy as np
    if path.stat().st_size != 2301 * 751 * 4:
        raise ValueError("Marmousi 1 vp must contain exactly 2301 × 751 float32 samples (6,912,204 bytes).")
    digest = sha256(path)
    if digest != VP_SHA256:
        raise ValueError("Marmousi 1 vp SHA-256 mismatch. Marmousi 2 and unverified data are not accepted.")
    if sys.byteorder != "little":
        raise ValueError("Upstream torch.from_file uses native float32; this binary requires little endian. Compatibility review required.")
    v = np.memmap(path, dtype="<f4", mode="r", shape=(2301, 751))
    if not np.isfinite(v).all() or float(v.min()) != 1500 or float(v.max()) != 5500:
        raise ValueError("Verified model range/finiteness check failed.")
    return {"dataset": "Marmousi 1", "sha256": digest, "bytes": path.stat().st_size,
            "samples": v.size, "dtype": "little-endian float32", "shape": [2301, 751],
            "axis_order": ["x", "depth"], "dx_m": 4., "velocity_range_m_s": [1500., 5500.],
            "geometry_authority": "Pinned upstream example; raw binary does not encode spacing or axes.",
            "identity_authority": "Local binary independently matches the GeoAzur public binary download; see audit."}


def verify_sources(kind: str) -> Path:
    name = "example_forward_model.py" if kind == "forward" else "example_rtm.py"
    source = Path(__file__).with_name(name)
    if sha256(source) != SOURCE_HASHES[kind]:
        raise ValueError("Pinned upstream source changed; this is not an unchanged reference reproduction.")
    return source


def verify_forward(directory: Path) -> Path:
    report = json.loads((directory / "reference_run.json").read_text())
    if (report.get("status"), report.get("kind"), report.get("classification"), report.get("reference_commit")) != (
        "succeeded", "forward", "unchanged_reference", REFERENCE_COMMIT
    ):
        raise ValueError("RTM requires a completed, unchanged pinned forward reference, not unrelated shot data.")
    path = directory / "marmousi_data.bin"
    if path.stat().st_size != 115 * 384 * 750 * 4:
        raise ValueError("Forward data has the wrong size.")
    if report["artifacts"]["marmousi_data.bin"]["sha256"] != sha256(path):
        raise ValueError("Forward shot data checksum mismatch.")
    if report["dataset"]["sha256"] != VP_SHA256:
        raise ValueError("Forward dataset identity mismatch.")
    if report.get("source_sha256") != SOURCE_HASHES["forward"] or report.get("versions", {}).get("deepwave") != "0.0.26":
        raise ValueError("Forward source/version does not match the pinned reference.")
    settings_file = directory / "settings.json"
    if report["artifacts"]["settings.json"]["sha256"] != sha256(settings_file):
        raise ValueError("Forward settings checksum mismatch.")
    settings = json.loads(settings_file.read_text())
    expected = {"dx": 4., "n_shots": 115, "n_receivers_per_shot": 384, "freq": 25, "nt": 750, "dt": .004, "numerical_accuracy": 8,
                "d_source": 20, "first_source": 10, "source_depth": 2, "d_receiver": 6, "first_receiver": 0, "receiver_depth": 2}
    if any(settings.get(key) != value for key, value in expected.items()):
        raise ValueError("Forward settings do not match the pinned acquisition/numerics.")
    return path


def run(kind: str, vp: Path, output: Path, forward: Path | None = None) -> dict:
    """Execute in a dedicated process: upstream programs use relative filenames."""
    source = verify_sources(kind)
    dataset = verify_vp(vp)
    if importlib.metadata.version("deepwave") != "0.0.26":
        raise ValueError("Reference defaults are pinned to Deepwave 0.0.26; compatibility review required.")
    observed = verify_forward(forward) if kind == "rtm" and forward is not None else None
    if kind == "rtm" and observed is None:
        raise ValueError("RTM requires --forward pointing to the recorded standalone forward run.")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(source, output / "upstream_example.py")
    shutil.copyfile(Path(__file__), output / "recorder_snapshot.py")
    shutil.copyfile(Path(__file__).with_name("LICENSE.txt"), output / "upstream_LICENSE.txt")
    shutil.copyfile(vp, output / "marmousi_vp.bin")
    if observed:
        shutil.copyfile(observed, output / "marmousi_data.bin")
    os.environ["MPLBACKEND"] = "Agg"
    import matplotlib.pyplot as plt
    import numpy as np
    import torch
    import deepwave

    report = {
        "status": "running", "kind": kind, "reference_id": REFERENCE_ID,
        "classification": "unchanged_reference", "reference_commit": REFERENCE_COMMIT,
        "source_sha256": SOURCE_HASHES[kind], "recorder_sha256": sha256(Path(__file__)),
        "dataset": dataset, "versions": {name: importlib.metadata.version(name)
            for name in ["deepwave", "torch", "numpy", "scipy", "matplotlib"]},
        "python": platform.python_version(), "platform": platform.platform(),
        "device": "cuda" if torch.cuda.is_available() else "cpu", "threads": torch.get_num_threads(),
        "numerical_modifications": [], "recording_changes": ["Noninteractive Agg plotting backend", "Additional raw arrays and metadata after upstream program completes"],
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if observed:
        report["forward_report_sha256"] = sha256(forward / "reference_run.json")
        report["forward_data_sha256"] = sha256(observed)
    write_json(output / "reference_run.json", report)
    previous = Path.cwd()
    started = time.monotonic()
    try:
        os.chdir(output)
        print(json.dumps({"stage": "Executing unchanged upstream " + kind, "output": str(output)}), flush=True)
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
        namespace = runpy.run_path(str(source), run_name="__main__")
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        report["upstream_wall_seconds"] = time.monotonic() - started
        plt.close("all")

        def save(name, tensor):
            arr = tensor.detach().cpu().numpy()
            if not np.isfinite(arr).all():
                raise ValueError("Non-finite upstream artifact: " + name)
            np.save(output / name, arr, allow_pickle=False)
        save("true_velocity.npy", namespace["v"])
        save("source_locations.npy", namespace["source_locations"])
        save("receiver_locations.npy", namespace["receiver_locations"])
        save("source_amplitudes.npy", namespace["source_amplitudes"])
        if kind == "forward":
            data = namespace["receiver_amplitudes"]
            save("representative_shot.npy", data[57])
        else:
            save("migration_velocity.npy", namespace["v_mig"])
            save("representative_shot.npy", namespace["observed_data"][0])
            save("direct_arrival_mask.npy", namespace["mask"])
            save("masked_data.npy", namespace["observed_scatter_masked"])
            save("raw_rtm_image.npy", namespace["scatter"])
            save("accumulated_gradient.npy", namespace["scatter"].grad)
            # A plotting derivative only: preserve exact raw scatter separately.
            scatter = namespace["scatter"].detach().cpu().numpy()
            vmin, vmax = float(namespace["vmin"]), float(namespace["vmax"])
            np.save(output / "plotting_image.npy", np.clip(scatter.T, vmin, vmax), allow_pickle=False)
            report["plotting"] = {"axis_order": ["depth", "x"], "cmap": "gray", "clip_quantiles": [.05, .95], "vmin": vmin, "vmax": vmax}
            report["epoch_loss"] = float(namespace["epoch_loss"])

        data = np.memmap(output / "marmousi_data.bin", dtype="<f4", mode="r", shape=(115, 384, 750))
        if not all(np.isfinite(shot).all() for shot in data):
            raise ValueError("Non-finite full forward shot data.")
        report["raw_data_shape"] = [115, 384, 750]
        report["raw_data_dtype"] = "little-endian float32"

        # Additional physical-coordinate view; upstream plots remain unchanged.
        models = [("True Marmousi 1 velocity + acquisition", namespace["v"], 4.)]
        if kind == "rtm":
            models.append(("Migration velocity: smoothed slowness, not inversion", namespace["v_mig"], 8.))
        figure, axes = plt.subplots(1, len(models), figsize=(12, 4), squeeze=False, constrained_layout=True)
        acquisition_dx = float(namespace["dx"])
        sources = namespace["source_locations"].cpu().numpy()[:, 0] * acquisition_dx
        receivers = namespace["receiver_locations"].cpu().numpy()[0] * acquisition_dx
        for axis, (title, model, spacing) in zip(axes[0], models):
            array = model.detach().cpu().numpy()
            extent = [-spacing / 2, (array.shape[0] - .5) * spacing, (array.shape[1] - .5) * spacing, -spacing / 2]
            picture = axis.imshow(array.T, extent=extent, aspect="equal", vmin=1500, vmax=5500, cmap="viridis")
            axis.scatter(receivers[:, 0], receivers[:, 1], s=2, c="white", label="Receivers")
            axis.scatter(sources[:, 0], sources[:, 1], s=9, c="red", marker="*", label="Sources")
            axis.set(title=title, xlabel="x (m)", ylabel="Depth (m)")
            axis.legend(fontsize=7, loc="lower right")
        figure.colorbar(picture, ax=list(axes[0]), label="Vp (m/s)", shrink=.7)
        figure.savefig(output / "velocity_acquisition.png", dpi=140)
        plt.close(figure)

        settings = {key: namespace[key] for key in ["dx", "n_shots", "n_sources_per_shot", "d_source", "first_source", "source_depth",
                    "n_receivers_per_shot", "d_receiver", "first_receiver", "receiver_depth", "freq", "nt", "dt", "peak_time"]}
        settings["array_axis_order"] = ["x", "depth"]
        settings["receiver_data_axis_order"] = ["shot", "receiver", "time"]
        settings["numerical_accuracy"] = 8 if kind == "forward" else 4
        settings["pml_freq"] = namespace["freq"]
        settings["upstream_default_arguments"] = {key: str(param.default) for key, param in inspect.signature(
            deepwave.scalar if kind == "forward" else deepwave.scalar_born).parameters.items() if param.default is not inspect.Parameter.empty}
        velocity = namespace["v"] if kind == "forward" else namespace["v_mig"]
        settings["effective_max_velocity_m_s"] = float(velocity.max())
        internal_dt, ratio = deepwave.common.cfl_condition_n([settings["dx"]] * 2, settings["dt"], float(velocity.max()))
        settings.update(internal_dt_s=internal_dt, internal_step_ratio=ratio, internal_nt=settings["nt"] * ratio)
        if kind == "rtm":
            settings["optimizer_defaults"] = namespace["optimiser"].defaults
            settings["loss_reduction"] = namespace["loss_fn"].reduction
            settings.update(migration_model="1 / gaussian_filter(1 / vp, 40), then [::2, ::2]",
                smoothing_sigma_original_cells=40, smoothing_sigma_m=160, mask_flat_len=100, mask_taper_len=200,
                mask_direct_velocity_m_s=1700, mask="upstream cosine taper; NO background subtraction", n_batch=46,
                shots_per_batch=3, nonempty_batches=39, n_epochs=1, optimizer="SGD", learning_rate=1e9,
                loss="Per-batch mean MSE; backward accumulation; ONE optimizer step")
        write_json(output / "settings.json", settings)
        report["settings_sha256"] = sha256(output / "settings.json")
        if sha256(output / "marmousi_vp.bin") != VP_SHA256 or sha256(vp) != VP_SHA256:
            raise ValueError("Input model changed during execution.")
        if observed and sha256(output / "marmousi_data.bin") != report["forward_data_sha256"]:
            raise ValueError("Observed data changed during execution.")
        report["status"] = "succeeded"
    except BaseException as exc:
        report["status"] = "failed"
        report["error_type"] = type(exc).__name__
        report["error"] = str(exc)[:2000]
        raise
    finally:
        os.chdir(previous)
        report["total_wall_seconds"] = time.monotonic() - started
        report["process_peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        report["cuda_peak_allocated_bytes"] = torch.cuda.max_memory_allocated() if torch.cuda.is_available() else None
        report["artifacts"] = {p.name: {"bytes": p.stat().st_size, "sha256": sha256(p)}
            for p in sorted(output.iterdir()) if p.is_file() and p.name != "reference_run.json"}
        write_json(output / "reference_run.json", report)
    print(json.dumps({"stage": "Completed unchanged upstream " + kind, "seconds": report["total_wall_seconds"]}), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["forward", "rtm"])
    parser.add_argument("--vp", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--forward", type=Path)
    parser.add_argument("--wall-seconds", type=int, required=True)
    parser.add_argument("--memory-gib", type=int, required=True)
    args = parser.parse_args()
    if not 60 <= args.wall_seconds <= 7200 or not 4 <= args.memory_gib <= 24:
        parser.error("Review resources first: wall limit must be 60..7200 s and address-space limit 4..24 GiB.")
    resource.setrlimit(resource.RLIMIT_AS, (args.memory_gib * 1024**3,) * 2)
    def timeout(_signum, _frame):
        raise TimeoutError("Reference wall-clock budget exceeded; no reduced replacement was run.")
    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(args.wall_seconds)
    run(args.kind, args.vp.resolve(), args.output, args.forward.resolve() if args.forward else None)


if __name__ == "__main__":
    main()
