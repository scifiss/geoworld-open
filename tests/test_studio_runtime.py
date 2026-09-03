from __future__ import annotations

import base64
from pathlib import Path

import pytest

from geoworld_open.client.models import ArtifactInfo, LASQuicklookSettings
from geoworld_open.studio_runtime import (
    LAS_INVENTORY_NAME,
    artifact_named,
    decode_json_object,
    encode_las_upload,
    friendly_job_error,
    health_diagnostic,
    inspect_las_header,
    las_form_signature,
    output_coverage_rows,
    provenance_lines,
    recommended_las_curves,
    sort_figure_artifacts,
)


ROOT = Path(__file__).resolve().parents[1]


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


def test_las_upload_encoding_is_content_preserving_and_filename_safe() -> None:
    upload = encode_las_upload("../private/path/WELL.LAS", b"~Version\nVERS. 2.0")

    assert upload.filename == "WELL.LAS"
    assert upload.size_bytes == 18
    assert base64.b64decode(upload.content_base64) == b"~Version\nVERS. 2.0"

    with pytest.raises(ValueError, match=".las filename"):
        encode_las_upload("well.txt", b"content")
    with pytest.raises(ValueError, match="must not be empty"):
        encode_las_upload("well.las", b"")


def test_las_summary_artifacts_are_found_and_safely_decoded() -> None:
    artifacts = [
        ArtifactInfo(
            name=f"run/results/{LAS_INVENTORY_NAME}",
            kind="json",
            media_type="application/json",
        )
    ]

    found = artifact_named(artifacts, LAS_INVENTORY_NAME)

    assert found is artifacts[0]
    assert decode_json_object(b'{"wells": [{"well_id": "ALPHA-1"}]}')["wells"]
    with pytest.raises(ValueError, match="JSON must be an object"):
        decode_json_object(b"[]")


def test_public_las_samples_are_synthetic_and_available_to_studio() -> None:
    first = ROOT / "examples" / "las" / "gw_demo_01_layered.las"
    second = ROOT / "examples" / "las" / "gw_demo_02_layered.las"
    first_text = first.read_text(encoding="utf-8")
    second_text = second.read_text(encoding="utf-8")

    assert "WELL.          GW-DEMO-01" in first_text
    assert "WELL.          GW-DEMO-02" in second_text
    assert "STRT.M              1800.0" in first_text
    assert "STRT.M              1810.0" in second_text
    assert "high porosity clean sand" in first_text
    assert "lower porosity cemented sand" in second_text
    assert len([line for line in first_text.splitlines() if line[:1].isdigit()]) == 201
    assert len([line for line in second_text.splitlines() if line[:1].isdigit()]) == 201


def test_las_header_inspection_discovers_uploaded_well_and_curve_choices() -> None:
    path = ROOT / "examples" / "las" / "gw_demo_01_layered.las"

    metadata = inspect_las_header(path.name, path.read_bytes())

    assert metadata.filename == "gw_demo_01_layered.las"
    assert metadata.well_name == "GW-DEMO-01"
    assert metadata.depth_mnemonic == "DEPT"
    assert metadata.curve_mnemonics == (
        "VP",
        "VS",
        "RHOB",
        "GR",
        "RESD",
        "SW",
        "PHIE",
        "NPHI",
        "DT",
        "DTS",
    )
    assert metadata.warnings == ()


def test_las_header_inspection_falls_back_safely_when_well_name_is_missing() -> None:
    metadata = inspect_las_header(
        "../Odd Well.las",
        b"~Curve\n MD.FT : depth\n gam.API : gamma ray\n~Ascii\n1000 80\n",
    )

    assert metadata.filename == "Odd Well.las"
    assert metadata.well_name == "Odd_Well"
    assert metadata.depth_mnemonic == "MD"
    assert metadata.curve_mnemonics == ("gam",)
    assert "sanitized filename" in metadata.warnings[0]


def test_recommended_las_curves_use_only_discovered_options() -> None:
    assert recommended_las_curves(["VP", "gr", "RESD", "RHOB", "DT", "NPHI"]) == [
        "gr",
        "RHOB",
        "NPHI",
        "DT",
    ]
    assert recommended_las_curves(["VP", "VS", "RESD"]) == ["VP", "VS", "RESD"]


def test_las_form_signature_changes_with_files_and_unit_without_storing_content() -> None:
    native = LASQuicklookSettings(selected_curves=["GR"])
    metric = LASQuicklookSettings(selected_curves=["GR"], target_depth_unit="m")

    first = las_form_signature([("alpha.las", 100)], native)
    changed_file = las_form_signature([("alpha.las", 100), ("beta.las", 200)], native)
    changed_unit = las_form_signature([("alpha.las", 100)], metric)

    assert first != changed_file
    assert first != changed_unit
    assert "alpha" not in first
    assert len(first) == 64


def test_known_las_failures_are_actionable() -> None:
    units = friendly_job_error(
        "Selected wells use incompatible measured-depth units; choose a target depth unit."
    )
    curves = friendly_job_error("No selected LAS curves have valid values to plot.")

    assert "Choose metres or feet" in units
    assert "Choose one or more curves" in curves


def test_studio_sidebar_does_not_expose_developer_diagnostics() -> None:
    source = (ROOT / "apps" / "studio_streamlit.py").read_text(encoding="utf-8")

    assert 'st.success("GeoWorld is ready")' in source
    assert 'st.expander("Connection diagnostic")' not in source
    assert 'f"Available capabilities (' not in source


def test_studio_uses_discovered_las_selectors_instead_of_free_text() -> None:
    source = (ROOT / "apps" / "studio_streamlit.py").read_text(encoding="utf-8")

    assert 'selection_columns[0].multiselect(\n            "Wells"' in source
    assert 'selection_columns[1].multiselect(\n            "Curves"' in source
    assert 'text_input(\n            "Wells' not in source
    assert 'text_input(\n            "Curves' not in source
