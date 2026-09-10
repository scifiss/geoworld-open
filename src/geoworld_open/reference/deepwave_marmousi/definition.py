"""PUBLIC_REFERENCE: versioned, human-auditable upstream experiment definition."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

REFERENCE_ID = "deepwave-marmousi1-rtm-v0.0.26-r1"
DEFINITION = {
    "reference_id": REFERENCE_ID,
    "upstream_commit": "7dbaeda5fdfbff2a6d579dcc9f7f18488c5e6084",
    "deepwave_version": "0.0.26",
    "dataset": {"name": "Marmousi 1", "shape_xz": [2301, 751], "dx_m": 4., "dtype": "little-endian float32",
                "vp_sha256": "f4302792e84bb7ddbdc9d4d0f963b9df32d9f648960084884127e186119b99dd", "use_density": False},
    "source_hashes": {
        "forward": "3c74e0a2b52b09360f6226c83d6a0e745d2ac7d41eb920d3ecaa1b276b10ad2d",
        "rtm": "ebbdc144ac7df2e00b1213dd7011550cd63d92b9520907bd4ac8f66acce5f9cd"},
    "acquisition": {"shots": 115, "sources_per_shot": 1, "first_source_x_m": 40., "source_spacing_m": 80.,
                    "source_depth_m": 8., "receivers_per_shot": 384, "first_receiver_x_m": 0.,
                    "receiver_spacing_m": 24., "receiver_depth_m": 8., "coordinate_order": ["x", "depth"]},
    "wavelet": {"type": "Deepwave Ricker", "source_frequency_hz": 25., "peak_time_s": .06, "nt": 750, "dt_s": .004},
    "forward": {"dx_m": 4., "accuracy": 8, "shots_in_single_call": 115},
    "migration": {"formula": "1 / gaussian_filter(1 / vp, 40), then [::2, ::2]", "shape_xz": [1151, 376],
                  "smoothing_variable": "slowness", "sigma_original_cells": 40, "sigma_m": 160., "dx_m": 8.},
    "rtm": {"propagator": "scalar_born", "accuracy": 4, "accuracy_source": "Deepwave 0.0.26 default, omitted upstream",
            "mask": "Cosine-tapered direct-arrival mute", "flat_len": 100, "taper_len": 200, "direct_velocity_m_s": 1700.,
            "background_subtraction": False, "n_batch": 46, "shots_per_batch": 3, "nonempty_batches": 39,
            "n_epochs": 1, "optimizer": "SGD", "learning_rate": 1e9, "initial_scatter": 0.,
            "loss": "Per-batch mean MSE(prediction * mask, observed * mask)",
            "gradient_behavior": "zero once, backward per nonempty batch, one optimizer step"},
    "shared_propagation": {"pml_width": 20, "pml_freq_hz": 25., "max_vel": None, "survey_pad": None,
                           "model_gradient_sampling_interval": 1, "freq_taper_frac": 0., "time_pad_frac": 0.,
                           "time_taper": False, "storage_mode": "device", "storage_compression": False,
                           "other_defaults": "Pinned Deepwave 0.0.26; complete signatures recorded at execution"},
    "plotting": {"cmap": "gray", "clip_quantiles": [.05, .95], "cosmetic_optimization": False},
    "limitations": ["2D constant-density acoustic benchmark, not density recovery or elastic AVO",
                    "Migration velocity is smoothed synthetic truth, not FWI", "One-update RTM, not converged LSRTM"],
}


def reference_definition() -> dict:
    return deepcopy(DEFINITION)


def configuration_hash(configuration: dict) -> str:
    return hashlib.sha256(json.dumps(configuration, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
