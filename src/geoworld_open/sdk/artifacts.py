"""Safe artifact loading and implementation-neutral manifest verification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict, Field


class ArtifactEntry(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    path: str
    bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ManifestVerification(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_path: str
    verified_artifacts: tuple[str, ...]


def _safe_artifact_path(root: Path, relative: str) -> Path:
    logical = PurePosixPath(relative)
    if logical.is_absolute() or ".." in logical.parts or not logical.parts:
        raise ValueError(f"unsafe artifact path: {relative!r}")
    resolved = (root / Path(*logical.parts)).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"artifact escapes run directory: {relative!r}") from exc
    return resolved


def load_manifest(run_dir: str | Path) -> dict[str, object]:
    path = Path(run_dir) / "manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("manifest root must be a JSON object")
    return payload


def manifest_entries(run_dir: str | Path) -> tuple[ArtifactEntry, ...]:
    payload = load_manifest(run_dir)
    raw_entries = payload.get("artifacts")
    if not isinstance(raw_entries, list):
        raise ValueError("manifest artifacts must be a list")
    return tuple(ArtifactEntry.model_validate(item) for item in raw_entries)


def verify_manifest(run_dir: str | Path) -> ManifestVerification:
    root = Path(run_dir).resolve()
    verified: list[str] = []
    for entry in manifest_entries(root):
        path = _safe_artifact_path(root, entry.path)
        if not path.is_file():
            raise ValueError(f"manifest artifact is missing: {entry.path}")
        data = path.read_bytes()
        if len(data) != entry.bytes:
            raise ValueError(f"artifact byte count mismatch: {entry.path}")
        if hashlib.sha256(data).hexdigest() != entry.sha256:
            raise ValueError(f"artifact checksum mismatch: {entry.path}")
        verified.append(entry.path)
    return ManifestVerification(
        manifest_path=str(root / "manifest.json"),
        verified_artifacts=tuple(verified),
    )


def load_artifact(run_dir: str | Path, relative_path: str, *, max_bytes: int | None = None) -> bytes:
    root = Path(run_dir).resolve()
    path = _safe_artifact_path(root, relative_path)
    if not path.is_file():
        raise FileNotFoundError(relative_path)
    if max_bytes is not None and path.stat().st_size > max_bytes:
        raise ValueError(f"artifact exceeds max_bytes={max_bytes}")
    return path.read_bytes()
