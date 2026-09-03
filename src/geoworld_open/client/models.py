"""Portable public models for the official GeoWorld HTTP API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class UserProfile(BaseModel):
    id: int
    email: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile


class ArtifactInfo(BaseModel):
    name: str
    kind: Literal["image", "json", "csv", "yaml", "text", "file"] = "file"
    media_type: str = "application/octet-stream"
    size_bytes: int | None = None


class UploadedLASFile(BaseModel):
    """Portable representation of one LAS file submitted to the protected service."""

    filename: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1)
    size_bytes: int | None = Field(default=None, ge=0)


class LASQuicklookSettings(BaseModel):
    """Public request controls for the protected measured-depth quicklook workflow."""

    selected_wells: list[str] = Field(default_factory=list)
    selected_curves: list[str] = Field(default_factory=list)
    depth_range_mode: Literal["union", "intersection", "custom"] = "intersection"
    custom_depth_min: float | None = None
    custom_depth_max: float | None = None
    target_depth_unit: Literal["m", "ft"] | None = None
    resample_enabled: bool = False
    resample_interval: float | None = Field(default=None, gt=0)
    resample_gap_multiplier: float = Field(default=3.0, gt=0)
    log_resistivity: bool = False

    @field_validator("selected_wells", "selected_curves")
    @classmethod
    def validate_unique_strings(cls, values: list[str]) -> list[str]:
        cleaned = [str(value).strip() for value in values if str(value).strip()]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("selection lists must not contain duplicates")
        return cleaned


class JobCreateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    mode_hint: str | None = None
    geospec: dict[str, Any] | None = None
    csv_name: str | None = None
    csv_content: str | None = None
    las_files: list[UploadedLASFile] = Field(default_factory=list)
    las_quicklook: LASQuicklookSettings | None = None
    interpretation_mode: str | None = None
    interpretation_degraded: bool = False
    degraded_fallback_confirmed: bool = False


class JobCreateResponse(BaseModel):
    job_id: str
    correlation_id: str | None = Field(
        default=None,
        pattern=r"^request-[0-9a-f]{32}$",
    )
    status: Literal["queued", "running", "succeeded", "failed"]
    progress: str


class CapabilityDescription(BaseModel):
    """Sanitized description returned by the active protected registry."""

    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    category: str = Field(min_length=1)
    availability: Literal["active"] = "active"
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    required_input_fields: list[str] = Field(default_factory=list)
    output_fields: list[str] = Field(default_factory=list)
    required_variables: list[str] = Field(default_factory=list)
    produced_variables: list[str] = Field(default_factory=list)
    supported_dimensions: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class CapabilityCatalog(BaseModel):
    """Versioned, read-only snapshot of capabilities available to this deployment."""

    schema_version: Literal["1.0"] = "1.0"
    catalog_version: str = Field(min_length=1)
    capabilities: list[CapabilityDescription]


class JobResult(BaseModel):
    intent: str
    reason: str
    answer: str
    mode: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    storage: dict[str, Any] = Field(default_factory=dict)
    layers: list[dict[str, Any]] = Field(default_factory=list)
    geospec: dict[str, Any] | None = None
    artifacts: list[ArtifactInfo] = Field(default_factory=list)
    interpretation_mode: str | None = None
    interpretation_degraded: bool = False
    requested_outputs: list[str] = Field(default_factory=list)
    produced_outputs: list[str] = Field(default_factory=list)
    output_coverage: dict[str, bool] = Field(default_factory=dict)
    provenance_summary: dict[str, Any] = Field(default_factory=dict)


class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    progress: str
    result: JobResult | None = None
    error: str | None = None
