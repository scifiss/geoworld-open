"""Pure presentation rules for protected-runtime responses."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Iterable, Mapping, TypeVar

from geoworld_open.client.models import ArtifactInfo, UploadedLASFile


ArtifactT = TypeVar("ArtifactT")

LAS_INVENTORY_NAME = "las_curve_inventory.json"
LAS_QC_NAME = "las_qc_summary.json"
LAS_OBSERVATION_NAME = "las_observation_summary.json"


@dataclass(frozen=True)
class LASHeaderMetadata:
    """Non-numerical names discovered in one uploaded LAS header."""

    filename: str
    well_name: str
    depth_mnemonic: str | None
    curve_mnemonics: tuple[str, ...]
    warnings: tuple[str, ...] = ()


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


def inspect_las_header(filename: str, content: bytes) -> LASHeaderMetadata:
    """Read well and curve names without parsing or interpreting numerical samples."""

    safe_name = PurePosixPath(str(filename).replace("\\", "/")).name.strip()
    if not safe_name or not content:
        raise ValueError("LAS header inspection requires a named, non-empty file")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    current_section: str | None = None
    well_name = ""
    curve_names: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("~"):
            current_section = stripped[1:2].upper()
            if current_section == "A":
                break
            continue
        if current_section not in {"W", "C"}:
            continue
        definition = _parse_las_header_definition(line)
        if definition is None:
            continue
        mnemonic, value = definition
        if current_section == "W" and mnemonic.upper() == "WELL":
            well_name = value.strip()
        elif current_section == "C" and mnemonic not in curve_names:
            curve_names.append(mnemonic)

    warnings: list[str] = []
    if not well_name:
        well_name = _safe_las_identifier(PurePosixPath(safe_name).stem)
        warnings.append("WELL name is missing; the sanitized filename will identify this well.")
    if not curve_names:
        warnings.append("No curve definitions were found in the LAS header.")

    return LASHeaderMetadata(
        filename=safe_name,
        well_name=well_name,
        depth_mnemonic=curve_names[0] if curve_names else None,
        curve_mnemonics=tuple(curve_names[1:]),
        warnings=tuple(warnings),
    )


def recommended_las_curves(available: Iterable[str], *, limit: int = 4) -> list[str]:
    """Choose familiar available curves while preserving explicit user control."""

    options = list(dict.fromkeys(str(item).strip() for item in available if str(item).strip()))
    preferred = ["GR", "RHOB", "NPHI", "DT"]
    by_uppercase = {name.upper(): name for name in options}
    selected = [by_uppercase[name] for name in preferred if name in by_uppercase]
    return selected[:limit] or options[:limit]


def _parse_las_header_definition(line: str) -> tuple[str, str] | None:
    left, _, _description = line.partition(":")
    match = re.match(r"\s*([A-Za-z0-9_]+)\.([^\s]*)\s*(.*?)\s*$", left)
    if not match:
        return None
    return match.group(1).strip(), match.group(3).strip()


def _safe_las_identifier(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.:-]+", "_", value.strip())
    cleaned = cleaned.strip("._:-") or "well"
    if not re.match(r"^[A-Za-z0-9]", cleaned):
        cleaned = f"well_{cleaned}"
    return cleaned[:80]


def las_form_signature(
    files: Iterable[tuple[str, int]],
    settings: object,
) -> str:
    """Identify one LAS form state without retaining uploaded file contents."""

    settings_payload = (
        settings.model_dump(mode="json")
        if hasattr(settings, "model_dump")
        else settings
    )
    payload = {
        "files": [
            {
                "filename": PurePosixPath(name.replace("\\", "/")).name,
                "size_bytes": size_bytes,
            }
            for name, size_bytes in files
        ],
        "settings": settings_payload,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def friendly_job_error(error: str | None) -> str:
    """Translate known workflow failures into an actionable user message."""

    message = str(error or "").strip()
    if "incompatible measured-depth units" in message:
        return (
            "These wells use different depth units. Choose metres or feet under "
            "Display depth in, then run the quicklook again."
        )
    if "No selected LAS curves" in message or "selected curves has valid samples" in message:
        return (
            "GeoWorld could not find usable samples for the selected curves. Choose one or more "
            "curves from the detected list and try again."
        )
    if "No valid LAS files" in message:
        return "GeoWorld could not read a valid LAS file. Check the file format and try again."
    return message or "GeoWorld could not complete this job. Please adjust the inputs and try again."


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
