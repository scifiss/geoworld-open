"""Pure presentation rules for protected-runtime responses."""

from __future__ import annotations

import base64
import json
from pathlib import PurePosixPath
from typing import Any, Iterable, Mapping, TypeVar

from geoworld_open.client.models import ArtifactInfo, UploadedLASFile


ArtifactT = TypeVar("ArtifactT")

LAS_INVENTORY_NAME = "las_curve_inventory.json"
LAS_QC_NAME = "las_qc_summary.json"
LAS_OBSERVATION_NAME = "las_observation_summary.json"


def figure_priority(name: str) -> tuple[int, str]:
    """Rank user-facing composites before specialized diagnostics."""
    basename = PurePosixPath(name.lower()).name
    if basename == "summary.png":
        rank = 0
    elif "flagship_public" in basename or (
        "flagship" in basename and "diagnostic" not in basename
    ):
        rank = 1
    elif "diagnostic" in basename or "world" in basename or "structure" in basename:
        rank = 2
    elif "avo" in basename:
        rank = 3
    else:
        rank = 4
    return rank, name.lower()


def sort_figure_artifacts(artifacts: Iterable[ArtifactT]) -> list[ArtifactT]:
    return sorted(artifacts, key=lambda item: figure_priority(str(getattr(item, "name"))))


def encode_las_upload(filename: str, content: bytes) -> UploadedLASFile:
    """Encode an upload for JSON transport without inspecting scientific contents."""

    safe_name = PurePosixPath(str(filename).replace("\\", "/")).name.strip()
    if not safe_name or not safe_name.lower().endswith(".las"):
        raise ValueError("LAS uploads must use a .las filename")
    if not content:
        raise ValueError("LAS uploads must not be empty")
    return UploadedLASFile(
        filename=safe_name,
        content_base64=base64.b64encode(content).decode("ascii"),
        size_bytes=len(content),
    )


def artifact_named(
    artifacts: Iterable[ArtifactInfo],
    basename: str,
) -> ArtifactInfo | None:
    """Find an artifact by safe POSIX basename regardless of its run subdirectory."""

    return next(
        (
            artifact
            for artifact in artifacts
            if PurePosixPath(artifact.name).name == basename
        ),
        None,
    )


def decode_json_object(payload: bytes) -> dict[str, Any]:
    """Decode one bounded presentation artifact and require a JSON object."""

    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("artifact is not valid UTF-8 JSON") from exc
    if not isinstance(decoded, dict):
        raise ValueError("artifact JSON must be an object")
    return decoded


def output_coverage_rows(
    requested: Iterable[str],
    produced: Iterable[str],
    coverage: Mapping[str, bool] | None = None,
) -> list[dict[str, str]]:
    produced_set = set(produced)
    coverage = coverage or {}
    return [
        {
            "Requested output": name,
            "Status": "Produced" if bool(coverage.get(name, name in produced_set)) else "Not produced",
        }
        for name in dict.fromkeys(requested)
    ]


def health_diagnostic(health: Mapping[str, Any]) -> dict[str, Any]:
    details = health.get("details") if isinstance(health.get("details"), Mapping) else {}
    primary = details.get("primary") if isinstance(details.get("primary"), Mapping) else {}
    fallback = details.get("fallback") if isinstance(details.get("fallback"), Mapping) else None
    local = details.get("local_fallback") if isinstance(details.get("local_fallback"), Mapping) else None
    overall = str(
        details.get("overall_status")
        or ("available" if health.get("reachable") else "unavailable")
    )
    return {
        "overall_status": overall,
        "active_provider": details.get("active_provider"),
        "active_model": details.get("active_model"),
        "primary": dict(primary),
        "fallback": dict(fallback) if fallback else None,
        "local_fallback": dict(local) if local else None,
    }


def provenance_lines(summary: Mapping[str, Any]) -> list[str]:
    lines: list[str] = []
    if summary.get("trace_id"):
        lines.append(f"Trace: {summary['trace_id']}")
    capabilities = summary.get("capabilities")
    if isinstance(capabilities, list) and capabilities:
        lines.append("Capabilities: " + " -> ".join(str(item) for item in capabilities))
    if summary.get("artifact_count") is not None:
        lines.append(f"Artifacts recorded: {summary['artifact_count']}")
    if summary.get("manifest_artifact"):
        lines.append(f"Manifest: {summary['manifest_artifact']}")
    return lines
