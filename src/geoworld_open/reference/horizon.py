"""PUBLIC_REFERENCE: bounded seed-template tracking, with no access to truth.

Walk left and right from a user seed. On each trace search same-polarity local
extrema within the time window and maximum jump. Rank by normalized correlation
to the fixed seed waveform minus 0.03 per jumped sample. Stop each direction
at the first weak/ambiguous match; never interpolate across failures.
"""
import numpy as np

from geoworld_open.client.horizon import HorizonTrackRequest

MAX_SECTION_SAMPLES = 256 * 512
HALF_TEMPLATE = 5
MIN_CORRELATION = .80
MIN_AMPLITUDE_RATIO = .30
MIN_SCORE_MARGIN = .05
SMOOTHNESS_PENALTY = .03
ALGORITHM_VERSION = "seeded-waveform-v0"


def tracking_parameters() -> dict:
    return {"half_template_samples": HALF_TEMPLATE, "minimum_correlation": MIN_CORRELATION,
            "minimum_amplitude_ratio": MIN_AMPLITUDE_RATIO,
            "minimum_score_margin": MIN_SCORE_MARGIN, "smoothness_penalty": SMOOTHNESS_PENALTY}


def track_section(section, dt_s: float, request: HorizonTrackRequest) -> dict:
    values = np.asarray(section)
    if (values.ndim != 2 or values.shape[0] > 512 or values.shape[1] > 256
            or values.shape[1] < 2 or values.size > MAX_SECTION_SAMPLES
            or not np.isfinite(values).all()):
        raise ValueError("Tracking requires a finite section of at most 512 samples × 256 traces")
    if not np.isfinite(dt_s) or dt_s <= 0:
        raise ValueError("Sample interval must be finite and positive")
    lo = int(np.ceil(request.window_start_s / dt_s - 1e-9))
    hi = int(np.floor(request.window_stop_s / dt_s + 1e-9))
    seed = int(round(request.seed_time_s / dt_s))
    column = request.seed_trace
    if (column >= values.shape[1] or lo < HALF_TEMPLATE
            or hi >= values.shape[0] - HALF_TEMPLATE or hi - lo < 2
            or hi - lo > 128 or not lo <= seed <= hi):
        raise ValueError("Seed/window is outside the section or lacks waveform margins; maximum 129 window samples")
    polarity = 1 if values[seed, column] >= 0 else -1
    signed = polarity * values
    seed_amplitude = float(signed[seed, column])
    if (seed_amplitude <= 0 or seed_amplitude < .4 * np.max(np.abs(values[lo:hi + 1, column]))
            or signed[seed, column] <= signed[seed - 1, column]
            or signed[seed, column] < signed[seed + 1, column]):
        raise ValueError("Starting position must select a strong local waveform extremum")
    template = values[seed - HALF_TEMPLATE:seed + HALF_TEMPLATE + 1, column].astype(float)
    template = template - template.mean()
    norm = np.linalg.norm(template)
    if norm <= 1e-12:
        raise ValueError("Starting waveform has no usable variation")
    picks = [None] * values.shape[1]
    confidence = [0.] * values.shape[1]
    reasons = [None] * values.shape[1]
    picks[column] = seed * dt_s
    confidence[column] = 1.
    for direction in (-1, 1):
        previous = seed
        stopped = False
        for trace in range(column + direction, values.shape[1] if direction > 0 else -1, direction):
            if stopped:
                reasons[trace] = "not_reached_after_failure"
                continue
            matches = []
            for candidate in range(max(lo, previous - request.max_jump_samples),
                                   min(hi, previous + request.max_jump_samples) + 1):
                amplitude = float(signed[candidate, trace])
                if (amplitude <= signed[candidate - 1, trace]
                        or amplitude < signed[candidate + 1, trace]
                        or amplitude < MIN_AMPLITUDE_RATIO * seed_amplitude):
                    continue
                patch = values[candidate - HALF_TEMPLATE:candidate + HALF_TEMPLATE + 1, trace].astype(float)
                patch = patch - patch.mean()
                correlation = float(np.dot(template, patch) / max(norm * np.linalg.norm(patch), 1e-12))
                if correlation < MIN_CORRELATION:
                    continue
                score = correlation - SMOOTHNESS_PENALTY * abs(candidate - previous)
                matches.append((score, candidate, correlation, amplitude))
            matches.sort(key=lambda match: (-match[0], match[1]))
            if not matches or (len(matches) > 1 and matches[0][0] - matches[1][0] < MIN_SCORE_MARGIN):
                stopped = True
                reasons[trace] = "ambiguous_match" if matches else "jump_limit_or_weak_waveform"
                continue
            _, previous, correlation, amplitude = matches[0]
            picks[trace] = previous * dt_s
            confidence[trace] = float(np.clip(correlation * min(1., amplitude / seed_amplitude), 0, 1))
    count = sum(value is not None for value in picks)
    return {
        "status": "complete" if count == len(picks) else "failed" if count == 1 else "partial",
        "picked_time_s": picks, "confidence": confidence, "failure_reasons": reasons,
    }
