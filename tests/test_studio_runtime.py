from __future__ import annotations

from geoworld_open.client.models import ArtifactInfo
from geoworld_open.studio_runtime import (
    health_diagnostic,
    output_coverage_rows,
    provenance_lines,
    sort_figure_artifacts,
)


def test_primary_summary_precedes_flagship_diagnostic_and_avo_figures() -> None:
    artifacts = [
        ArtifactInfo(name="model/avo_summary.png", kind="image", media_type="image/png"),
        ArtifactInfo(name="model/structure_diagnostic.png", kind="image", media_type="image/png"),
        ArtifactInfo(name="model/flagship_public.png", kind="image", media_type="image/png"),
        ArtifactInfo(name="model/summary.png", kind="image", media_type="image/png"),
    ]

    ordered = sort_figure_artifacts(artifacts)

    assert [item.name.rsplit("/", 1)[-1] for item in ordered] == [
        "summary.png",
        "flagship_public.png",
        "structure_diagnostic.png",
        "avo_summary.png",
    ]


def test_requested_output_coverage_is_explicit() -> None:
    rows = output_coverage_rows(
        ["vp", "vs", "impedance", "reflectivity"],
        ["vp", "vs", "impedance"],
        {"vp": True, "vs": True, "impedance": True, "reflectivity": False},
    )

    assert rows[-1] == {
        "Requested output": "reflectivity",
        "Status": "Not produced",
    }


def test_health_diagnostic_does_not_call_unreachable_fallback_active() -> None:
    diagnostic = health_diagnostic(
        {
            "provider": "bedrock",
            "reachable": False,
            "details": {
                "overall_status": "unavailable",
                "active_provider": None,
                "active_model": None,
                "primary": {"provider": "bedrock", "reachable": False},
                "fallback": {"provider": "ollama", "reachable": False},
            },
        }
    )

    assert diagnostic["overall_status"] == "unavailable"
    assert diagnostic["active_provider"] is None
    assert diagnostic["fallback"]["reachable"] is False


def test_provenance_summary_is_concise_and_trace_derived() -> None:
    lines = provenance_lines(
        {
            "trace_id": "trace-123",
            "capabilities": ["request_router", "semantic_model_parser", "synthetic_avo_runner"],
            "artifact_count": 17,
            "manifest_artifact": "manifest.json",
        }
    )

    assert lines == [
        "Trace: trace-123",
        "Capabilities: request_router -> semantic_model_parser -> synthetic_avo_runner",
        "Artifacts recorded: 17",
        "Manifest: manifest.json",
    ]
