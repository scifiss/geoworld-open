from __future__ import annotations

import base64
import hashlib
from html.parser import HTMLParser
from pathlib import Path

import pytest

from geoworld_open.client.models import JobResult
from geoworld_open.studio_presentation import (
    DisplayOptions, ReportFigure, build_clean_report, studio_export_controls, studio_display_css,
)


ROOT = Path(__file__).resolve().parents[1]


def example_result(**overrides) -> JobResult:
    fields = dict(
        intent="build_model", reason="manual selection",
        answer="A synthetic model was generated.\nNot a calibrated field interpretation.",
        assumptions=["Depth-domain seismic; no depth-to-time conversion."],
        geospec={"sensitive_metadata": "do-not-export-geospec"},
        provenance_summary={"internal": "do-not-export-trace"},
    )
    return JobResult(**(fields | overrides))


def example_figure() -> ReportFigure:
    return ReportFigure("flagship_world_demo.png", (ROOT / "docs/assets/flagship_world_demo.png").read_bytes())


class Document(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def test_clean_report_embeds_original_images_and_only_display_fields() -> None:
    figure = example_figure()
    html = build_clean_report(prompt="Build shale and sand.", result=example_result(), figures=[figure])
    assert "Build shale and sand." in html
    assert "Not a calibrated field interpretation." in html
    assert "Depth-domain seismic" in html
    assert "do-not-export-geospec" not in html
    assert "do-not-export-trace" not in html
    document = Document(html)
    image = next(attrs for tag, attrs in document.tags if tag == "img")
    assert base64.b64decode(image["src"].split(",", 1)[1]) == figure.data
    assert not any(tag in {"iframe", "link", "form"} for tag, _ in document.tags)
    assert all("src" not in attrs for tag, attrs in document.tags if tag == "script")


def test_report_escapes_all_user_controlled_content_and_restricts_script() -> None:
    injected = '<script>window.pwned=true</script><img src=x onerror="alert(1)">'
    html = build_clean_report(
        prompt=injected,
        result=example_result(answer=injected, assumptions=[injected]),
        figures=[ReportFigure(injected, example_figure().data)],
    )
    assert "&lt;script&gt;" in html
    tags = Document(html).tags
    assert sum(tag == "script" for tag, _ in tags) == 1
    assert sum(tag == "img" for tag, _ in tags) == 1
    assert all(not key.startswith("on") for _, attrs in tags for key in attrs)
    script = html.split("<script>", 1)[1].split("</script>", 1)[0]
    digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    assert f"script-src 'sha256-{digest}'" in html
    assert "default-src 'none'" in html


def test_report_preserves_citation_numbering_and_grounding_label() -> None:
    result = example_result(
        answer="An evidence-backed statement. [1]", grounding_status="geoworld_grounded",
        citations=[{
            "citation_id": "citation:" + "a" * 24,
            "source_id": "source:demo", "chunk_id": "chunk:demo",
            "locator": "demo.md#Scientific limits", "content_hash": "sha256:" + "b" * 64,
        }],
    )
    html = build_clean_report(prompt="Explain the limits.", result=result, figures=[])
    assert "Answer cites GeoWorld knowledge" in html
    assert "[1] demo.md — Scientific limits" in html
    assert "<img " not in html


@pytest.mark.parametrize("status,label", [
    ("evidence_insufficient", "Insufficient evidence"),
    ("general_model_uncited", "General model answer"),
])
def test_no_false_grounding_in_report(status, label) -> None:
    html = build_clean_report(prompt=None, result=example_result(grounding_status=status), figures=[])
    assert label in html
    assert "original submitted question is unavailable" in html
    assert "Answer cites GeoWorld knowledge" not in html


@pytest.mark.parametrize("data", [b"<svg onload='alert(1)'></svg>", b"<html>bad</html>", b""])
def test_active_or_unknown_image_types_are_rejected(data) -> None:
    with pytest.raises(ValueError, match="PNG, JPEG, and WebP"):
        ReportFigure("untrusted.png", data).data_url()


@pytest.mark.parametrize("options", [dict(text_px=12), dict(text_px=25), dict(figure_px=0), dict(figure_px=9999), dict(layout="bad"), dict(fit_figures="yes")])
def test_display_limits_keep_text_readable_and_figures_bounded(options) -> None:
    with pytest.raises(ValueError):
        DisplayOptions(**options)


def test_display_css_is_responsive_and_preserves_aspect_ratio() -> None:
    css = studio_display_css(DisplayOptions(text_px=20, figure_px=720, fit_figures=False))
    assert "font-size: 20px" in css
    assert "max-width: min(100%, 720px)" in css
    assert "height: auto" in css
    assert "max-width: none" in css
    assert "container: studio / inline-size" in css
    assert "min-width: 1020px" in css
    assert "transform:" not in css


def test_layout_rules_use_main_width_and_default_figures_fill_the_column() -> None:
    assert "min-width: 800px" in studio_display_css(DisplayOptions(layout="Two columns"))
    assert "@container studio" not in studio_display_css(DisplayOptions(layout="One column"))
    assert "max-width: min(100%" not in studio_display_css(DisplayOptions())


def test_export_uses_native_print_without_persistent_screenshot_mode() -> None:
    html = studio_export_controls()
    css = studio_display_css(DisplayOptions())
    assert "Save page as PDF" in html
    assert "@media print" in css
    assert "min-height: 0 !important" in css
    assert "min-height: 100vh" not in css
    assert "window.print()" in html
    assert "gw-studio-capture" not in html
    assert "classList.add" not in html
    assert "Your question / request" not in html
    assert "RUN REPORT" not in html
    assert "fetch(" not in html and "localStorage" not in html
    assert "sessionStorage" not in html
