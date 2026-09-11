"""PUBLIC_SDK_INFRA: human-readable measured progress and honest ETA scope."""
from __future__ import annotations

import time


def duration(seconds):
    minutes, seconds = divmod(max(0, int(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m {seconds:02d}s"


def progress_labels(detail, *, now=None, running=True):
    age = max(0., (time.time() if now is None else now) - detail.updated_unix_s) if running else 0.
    fraction = detail.completed / detail.total
    label = f"RTM batches: {detail.completed}/{detail.total} ({fraction:.0%})"
    elapsed = "Elapsed: " + duration(detail.elapsed_s + age)
    if detail.completed == detail.total:
        explanation = "Batches complete; final update, artifacts and validation still need to finish."
    elif detail.eta_s is None:
        explanation = ("ETA will be estimated after two completed batches." if detail.completed < 2
                       else "ETA is being recalculated; the next completed batch will update it.")
    elif detail.eta_s > age:
        explanation = "Approx. " + duration(detail.eta_s - age) + " for remaining batches; saving/validation is additional."
    else:
        explanation = "Taking longer than the last estimate; ETA updates when the next batch finishes."
    return fraction, label, elapsed + " · " + explanation
