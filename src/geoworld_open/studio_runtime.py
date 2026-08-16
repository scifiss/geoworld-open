"""Pure presentation rules for protected-runtime responses."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any, Iterable, Mapping, TypeVar


ArtifactT = TypeVar("ArtifactT")


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
