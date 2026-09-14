"""Portable execution evidence, above (and not part of) the World Kernel.

Budgets describe requested runtime limits, never exclusive OS allocations.
Discovery, reserve policy and scheduling belong to the backend, not this SDK.
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExecutionContract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ResourceSnapshot(ExecutionContract):
    timestamp: float = Field(ge=0)
    execution_location: Literal["local/backend"] = "local/backend"
    logical_cpus: int = Field(ge=1)
    available_cpu_budget: int = Field(ge=1)
    ram_available_bytes: int = Field(ge=0)
    gpu_available: bool = False
    gpu_type: str | None = None
    gpu_capability: str | None = None
    vram_free_bytes: int = Field(default=0, ge=0)
    vram_total_bytes: int = Field(default=0, ge=0)
    disk_free_bytes: int = Field(ge=0)


class ExecutionPreference(ExecutionContract):
    device: Literal["auto", "cpu", "cuda"] = "auto"
    priority: Literal["balanced"] = "balanced"
    locality: Literal["prefer_local"] = "prefer_local"
    max_cpu_threads: int | None = Field(default=None, ge=1, le=64)
    max_ram_bytes: int | None = Field(default=None, gt=0)
    max_vram_bytes: int | None = Field(default=None, gt=0)


class CapabilityResourceProfile(ExecutionContract):
    capability: str
    workload_identity: str
    ram_bytes: int = Field(gt=0)
    vram_bytes: int = Field(ge=0)
    disk_bytes: int = Field(default=0, ge=0)
    cpu_threads: int = Field(default=2, ge=1)
    batch_size: int | None = Field(default=None, ge=1)
    execution_mode: str
    scientific_mode: Literal["exact", "validated_approximation", "modified_experiment"] = "exact"
    cpu_seconds: tuple[float, float]
    cuda_seconds: tuple[float, float] | None = None
    evidence_sources: list[str]
    confidence: Literal["low", "medium", "high"] = "low"


class ExecutionEstimate(ExecutionContract):
    runtime_seconds: tuple[float, float]
    confidence: Literal["low", "medium", "high"]
    evidence_sources: list[str]
    assumptions: list[str]

    @model_validator(mode="after")
    def ordered_range(self):
        if not 0 <= self.runtime_seconds[0] <= self.runtime_seconds[1]:
            raise ValueError("Runtime estimate must be a nonnegative ordered range")
        return self


class ExecutionPlan(ExecutionContract):
    plan_id: str
    capability: str
    workload_identity: str
    preference: ExecutionPreference
    snapshot: ResourceSnapshot
    resolved_device: Literal["cpu", "cuda"]
    cpu_threads: int = Field(ge=1)
    estimated_ram_bytes: int = Field(ge=0)
    estimated_vram_bytes: int = Field(ge=0)
    estimated_disk_bytes: int = Field(default=0, ge=0)
    batch_size: int | None = Field(default=None, ge=1)
    execution_mode: str
    scientific_mode: Literal["exact", "validated_approximation", "modified_experiment"]
    estimate: ExecutionEstimate
    feasible: bool
    reasons: list[str]
    reserves: dict[str, int]
    usable_budgets: dict[str, int]
    allocation_guaranteed: Literal[False] = False


class ExecutionTelemetry(ExecutionContract):
    plan_id: str
    resolved_device: Literal["cpu", "cuda"]
    cpu_threads: int = Field(ge=1)
    gpu_type: str | None = None
    runtime_seconds: float = Field(ge=0)
    peak_ram_bytes: int = Field(ge=0)
    peak_vram_bytes: int = Field(ge=0)
    versions: dict[str, str | None]
    result_hashes: dict[str, str]
    completed_work_units: int = Field(ge=0)
    batch_size: int | None = None
