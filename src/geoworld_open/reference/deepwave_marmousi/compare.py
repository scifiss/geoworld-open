"""PUBLIC_BENCHMARK: compare independently executed reference runs, never PNGs."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path

from .runner import REFERENCE_COMMIT, VP_SHA256, sha256


def checked_report(directory: Path, kind: str) -> dict:
    import numpy as np
    report = json.loads((directory / "reference_run.json").read_text())
    if (report.get("status"), report.get("kind"), report.get("classification"), report.get("reference_commit")) != (
        "succeeded", kind, "unchanged_reference", REFERENCE_COMMIT
    ) or report["dataset"]["sha256"] != VP_SHA256:
        raise ValueError("A successful unchanged pinned reference is required.")
    from .runner import SOURCE_HASHES
    if report["source_sha256"] != SOURCE_HASHES[kind]:
        raise ValueError("Unpinned upstream source.")
    if report.get("versions", {}).get("deepwave") != "0.0.26":
        raise ValueError("Unpinned Deepwave version.")
    required = {"settings.json", "true_velocity.npy", "source_locations.npy", "receiver_locations.npy", "source_amplitudes.npy", "marmousi_data.bin"}
    if kind == "rtm":
        required |= {"migration_velocity.npy", "direct_arrival_mask.npy", "masked_data.npy", "raw_rtm_image.npy", "marmousi_scatter.bin", "accumulated_gradient.npy"}
    if not required <= report.get("artifacts", {}).keys():
        raise ValueError("Required reference artifacts are missing.")
    for name in required:
        record = report["artifacts"][name]
        path = directory / name
        if path.stat().st_size != record["bytes"] or sha256(path) != record["sha256"]:
            raise ValueError("Reference artifact checksum mismatch: " + name)
    shapes = {"true_velocity.npy": (2301, 751), "source_locations.npy": (115, 1, 2),
              "receiver_locations.npy": (115, 384, 2), "source_amplitudes.npy": (115, 1, 750)}
    if kind == "rtm":
        shapes.update({"migration_velocity.npy": (1151, 376), "direct_arrival_mask.npy": (115, 384, 750),
                       "masked_data.npy": (115, 384, 750), "raw_rtm_image.npy": (1151, 376), "accumulated_gradient.npy": (1151, 376)})
    for name, shape in shapes.items():
        array = np.load(directory / name, mmap_mode="r", allow_pickle=False)
        dtype = np.dtype("int64" if name in {"source_locations.npy", "receiver_locations.npy"} else "float32")
        if array.shape != shape or array.dtype != dtype or not all(np.isfinite(part).all() for part in array):
            raise ValueError("Reference array shape/dtype/finiteness mismatch: " + name)
    if (directory / "marmousi_data.bin").stat().st_size != 115 * 384 * 750 * 4:
        raise ValueError("Reference forward data size mismatch.")
    truth = np.load(directory / "true_velocity.npy", mmap_mode="r", allow_pickle=False)
    if hashlib.sha256(truth.tobytes(order="C")).hexdigest() != VP_SHA256:
        raise ValueError("Saved true velocity differs from the pinned Marmousi 1 model or axis ordering.")
    settings = json.loads((directory / "settings.json").read_text())
    expected = {"dx": 4. if kind == "forward" else 8., "freq": 25, "nt": 750, "dt": .004,
                "n_shots": 115, "n_sources_per_shot": 1, "n_receivers_per_shot": 384,
                "peak_time": .06, "numerical_accuracy": 8 if kind == "forward" else 4, "pml_freq": 25}
    if kind == "rtm":
        expected.update(smoothing_sigma_original_cells=40, n_batch=46, shots_per_batch=3, nonempty_batches=39,
                        n_epochs=1, learning_rate=1e9, mask_flat_len=100, mask_taper_len=200, mask_direct_velocity_m_s=1700)
    if any(settings.get(key) != value for key, value in expected.items()):
        raise ValueError("Recorded settings differ from the pinned reference definition.")
    depth = 2 if kind == "forward" else 1
    sources = np.load(directory / "source_locations.npy", allow_pickle=False)
    receivers = np.load(directory / "receiver_locations.npy", mmap_mode="r", allow_pickle=False)
    source_x = 10 + np.arange(115) * 20 if kind == "forward" else 5 + np.arange(115) * 10
    receiver_x = np.arange(384) * (6 if kind == "forward" else 3)
    if not (np.array_equal(sources[:, 0, 0], source_x) and np.all(sources[..., 1] == depth)
            and np.all(receivers[..., 0] == receiver_x) and np.all(receivers[..., 1] == depth)):
        raise ValueError("Acquisition does not equal the official geometry.")
    data = np.memmap(directory / "marmousi_data.bin", dtype="<f4", mode="r", shape=(115, 384, 750))
    if not all(np.isfinite(shot).all() for shot in data):
        raise ValueError("Reference forward data contains non-finite values.")
    if kind == "rtm":
        raw = directory / "marmousi_scatter.bin"
        if raw.stat().st_size != 1151 * 376 * 4:
            raise ValueError("Raw RTM binary size mismatch.")
        image = np.load(directory / "raw_rtm_image.npy", mmap_mode="r", allow_pickle=False)
        binary = np.memmap(raw, dtype="<f4", mode="r", shape=(1151, 376))
        if not np.array_equal(image, binary):
            raise ValueError("Raw RTM binary and NPY image disagree.")
        gradient = np.load(directory / "accumulated_gradient.npy", mmap_mode="r", allow_pickle=False)
        if not np.allclose(image, -1e9 * gradient, rtol=1e-5, atol=1e-7):
            raise ValueError("RTM image does not equal the official one-update SGD result.")
    return report


def compare_runs(reference: Path, candidate: Path, *, rtol=1e-5, atol=1e-7) -> dict:
    import numpy as np
    if reference.resolve() == candidate.resolve():
        raise ValueError("A run cannot be its own independent comparison candidate.")
    if not (np.isfinite(rtol) and np.isfinite(atol) and 0 <= rtol <= 1e-5 and 0 <= atol <= 1e-7):
        raise ValueError("Acceptance tolerances cannot exceed the frozen rtol=1e-5, atol=1e-7.")
    left, right = checked_report(reference, "rtm"), checked_report(candidate, "rtm")
    settings_left = json.loads((reference / "settings.json").read_text())
    settings_right = json.loads((candidate / "settings.json").read_text())
    result = {"settings_equal": settings_left == settings_right, "rtol": rtol, "atol": atol,
              "comparison_target": "raw numerical arrays, not display images",
              "forward_data_equal": left["forward_data_sha256"] == right["forward_data_sha256"],
              "arrays": {}}
    exact = ["true_velocity.npy", "migration_velocity.npy", "source_locations.npy", "receiver_locations.npy", "source_amplitudes.npy", "direct_arrival_mask.npy"]
    for name in exact + ["masked_data.npy", "raw_rtm_image.npy", "accumulated_gradient.npy"]:
        a = np.load(reference / name, mmap_mode="r", allow_pickle=False)
        b = np.load(candidate / name, mmap_mode="r", allow_pickle=False)
        same_shape = a.shape == b.shape and a.dtype == b.dtype
        passed, max_abs = same_shape, 0.
        # Slice along x/shot to avoid duplicating full data/history arrays.
        if same_shape:
            for av, bv in zip(a, b):
                finite = bool(np.isfinite(av).all() and np.isfinite(bv).all())
                passed = passed and finite and bool(np.array_equal(av, bv) if name in exact else np.allclose(av, bv, rtol=rtol, atol=atol))
                max_abs = max(max_abs, float(np.max(np.abs(av.astype("float64") - bv))))
        result["arrays"][name] = {"passed": passed, "require_exact": name in exact, "same_shape_dtype": same_shape, "max_abs_error": max_abs}
    result["passed"] = result["settings_equal"] and result["forward_data_equal"] and all(v["passed"] for v in result["arrays"].values())
    return result
