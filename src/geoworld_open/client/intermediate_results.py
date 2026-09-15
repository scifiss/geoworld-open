"""PUBLIC_SDK_INFRA: bounded display snapshots, distinct from restart checkpoints.

Resolution uses counts/stage boundaries only; no hardware or scientific policy.
"""
import math
from typing import Literal

from pydantic import Field, model_validator

from .execution import ExecutionContract


class IntermediateResultPolicy(ExecutionContract):
    mode: Literal['auto', 'final', 'interval', 'schedule'] = 'auto'
    interval: int | None = Field(default=None, ge=1)
    schedule: list[int] = Field(default_factory=list, max_length=10)

    @model_validator(mode='after')
    def coherent(self):
        if (self.mode == 'interval') != (self.interval is not None):
            raise ValueError('Supply an interval only in interval mode')
        if (self.mode == 'schedule') != bool(self.schedule):
            raise ValueError('Supply a nonempty schedule only in schedule mode')
        if any(n < 1 for n in self.schedule) or self.schedule != sorted(set(self.schedule)):
            raise ValueError('Snapshot schedule must be positive, unique and ordered')
        return self

    def resolve(self, total: int, *, stage_boundaries: tuple[int, ...] = ()) -> list[int]:
        if isinstance(total, bool) or not isinstance(total, int) or total < 1:
            raise ValueError('Total work must be a positive integer')
        if stage_boundaries and (tuple(sorted(set(stage_boundaries))) != stage_boundaries
                                 or min(stage_boundaries) < 1 or max(stage_boundaries) > total):
            raise ValueError('Invalid scientific stage boundaries')
        if self.mode == 'schedule':
            if self.schedule[-1] > total:
                raise ValueError('Snapshot lies beyond final work unit')
            result = sorted(set(self.schedule + [total]))
        elif self.mode == 'interval':
            # Reject excessive output before materialising a potentially huge list.
            if math.ceil(total / self.interval) > 10:
                raise ValueError('At most ten display snapshots are permitted')
            result = sorted(set(range(self.interval, total + 1, self.interval)) | {total})
        elif self.mode == 'final' or (total <= 20 and not stage_boundaries):
            result = [total]
        elif stage_boundaries:
            result = sorted(set(stage_boundaries) | {total})
        else:
            target = total / 5
            magnitude = 10 ** math.floor(math.log10(target))
            interval = next(int(multiplier * magnitude) for multiplier in (1, 2, 5, 10)
                            if multiplier * magnitude >= target)
            result = sorted(set(range(interval, total + 1, interval)) | {total})
        if len(result) > 10:
            raise ValueError('At most ten display snapshots are permitted')
        return result
