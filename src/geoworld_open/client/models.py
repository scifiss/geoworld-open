"""Portable public models for the official GeoWorld HTTP API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


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


class JobCreateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    mode_hint: str | None = None
    geospec: dict[str, Any] | None = None
    csv_name: str | None = None
    csv_content: str | None = None


class JobCreateResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    progress: str


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


class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    progress: str
    result: JobResult | None = None
    error: str | None = None
