"""Optional real Streamlit widget tests: install the demo extra to run."""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

from geoworld_open.client import GeoWorldBackendClient, GeoWorldClientError
from geoworld_open.client.models import JobCreateResponse, JobResult, JobStatusResponse


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("GEOWORLD_BACKEND_URL", "https://example.test")
    monkeypatch.setattr(GeoWorldBackendClient, "get_llm_health", lambda _self: {"reachable": True})
    monkeypatch.setattr(GeoWorldBackendClient, "get_artifact", lambda *_args: (ROOT / "docs/assets/flagship_world_demo.png").read_bytes())

    def unavailable(*_args):
        raise GeoWorldClientError("Full archive not part of this UI test")

    monkeypatch.setattr(GeoWorldBackendClient, "get_export", unavailable)
    at = AppTest.from_file(str(ROOT / "apps/studio_streamlit.py"))
    at.session_state["access_token"] = "test-token"
    at.session_state["user_email"] = "private-account@example.test"
    at.session_state["active_workspace"] = "Ask or Build"
    result = JobResult(
        intent="build_model", reason="test", answer="A synthetic model was generated.",
        artifacts=[{"name": "summary.png", "kind": "image", "media_type": "image/png"}],
    )
    at.session_state["last_job"] = JobStatusResponse(
        job_id="job-report", status="succeeded", progress="complete", result=result,
    )
    at.session_state["last_job_id"] = "job-report"
    at.session_state["last_submitted_prompt"] = "Original submitted question."
    at.session_state["prompt"] = "Edited but NOT submitted question."
    return at


def button(app, label):
    return next(item for item in app.button if item.label == label)


def test_widgets_change_display_without_resubmitting_and_report_uses_original_prompt(app, monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("display controls must not submit jobs")

    monkeypatch.setattr(GeoWorldBackendClient, "submit_job", forbidden)
    app.run(timeout=15)
    assert not app.exception
    app.checkbox(key="display_fit_figures").uncheck().run()
    app.slider(key="display_text_px").set_value(20).run()
    app.slider(key="display_figure_px").set_value(720).run()
    assert not app.exception
    assert any("font-size: 20px" in item.value for item in app.markdown)
    button(app, "Prepare HTML report").click().run()
    assert not app.exception
    html = app.session_state["clean_report"][2]
    assert "Original submitted question." in html
    assert "Edited but NOT submitted" not in html
    assert "private-account@example.test" not in html
    assert "test-token" not in html
    assert "https://example.test" not in html
    assert "--figure-width: 720px" in html


def test_failed_figure_fetch_does_not_offer_a_partial_report(app, monkeypatch):
    app.run(timeout=15)

    def unavailable(*_args):
        raise GeoWorldClientError("Figure download unavailable")

    monkeypatch.setattr(GeoWorldBackendClient, "get_artifact", unavailable)
    button(app, "Prepare HTML report").click().run()
    assert not app.exception
    assert "clean_report" not in app.session_state
    assert any("Could not prepare the complete clean report" in warning.value for warning in app.warning)


def test_new_submission_binds_prompt_and_clears_old_report(app, monkeypatch):
    monkeypatch.setattr(GeoWorldBackendClient, "submit_job", lambda *_args: JobCreateResponse(job_id="new-job", status="queued", progress="queued"))
    monkeypatch.setattr(GeoWorldBackendClient, "get_job", lambda *_args: JobStatusResponse(
        job_id="new-job", status="succeeded", progress="complete",
        result=JobResult(intent="rag_qa", reason="question", answer="New answer."),
    ))
    app.run(timeout=15)
    button(app, "Prepare HTML report").click().run()
    next(item for item in app.radio if item.label == "Intent").set_value("Ask Question").run()
    button(app, "Ask GeoWorld").click().run()
    assert not app.exception
    assert app.session_state["last_submitted_prompt"] == "Edited but NOT submitted question."
    assert "clean_report" not in app.session_state


def test_logout_clears_report_and_submitted_prompt(app):
    app.run(timeout=15)
    button(app, "Prepare HTML report").click().run()
    button(app, "Log out").click().run()
    assert not app.exception
    assert "clean_report" not in app.session_state
    assert "last_submitted_prompt" not in app.session_state


def test_saving_is_in_sidebar_not_workflow_and_layout_defaults_to_auto(app):
    app.run(timeout=15)
    assert not app.exception
    assert app.selectbox(key="display_layout").value == "Auto"
    assert app.checkbox(key="display_fit_figures").value is True
    assert any("Save page as PDF" in item.proto.body for item in app.sidebar.get("html"))
    assert not app.main.get("html")
    assert any("formatted offline report" in item.value for item in app.caption)
    assert all(item.label != "Screenshot / clean report" for item in app.expander)
    assert any(item.label == "Prepare HTML report" for item in app.sidebar.button)
    assert any(item.label == "What would you like GeoWorld to do?" for item in app.text_area)


def test_layout_choices_keep_results_and_never_submit_jobs(app, monkeypatch):
    monkeypatch.setattr(GeoWorldBackendClient, "submit_job", lambda *_args: pytest.fail("layout must not run science"))
    app.run(timeout=15)
    for choice in ("One column", "Two columns", "Auto"):
        app.selectbox(key="display_layout").set_value(choice).run()
        assert not app.exception
        assert app.session_state["last_job_id"] == "job-report"
        assert app.session_state["last_submitted_prompt"] == "Original submitted question."
        assert "studio_workspace_layout" in next(item.value for item in app.markdown if "<style>" in item.value)


@pytest.mark.parametrize("confirmation_required", [False, True])
def test_model_review_precedes_run_and_keeps_fallback_confirmation(app, monkeypatch, confirmation_required):
    monkeypatch.setattr(GeoWorldBackendClient, "preview_geospec", lambda *_args, **_kwargs: {
        "valid": True,
        "interpretation_mode": "deterministic" if confirmation_required else "llm_semantic_parser",
        "degraded": confirmation_required,
        "confirmation_required": confirmation_required,
        "geospec": {"assumptions": ["Synthetic layers; not a field interpretation."]},
        "issues": [{"severity": "info", "message": "Review these assumptions before running."}],
    })
    app.run(timeout=15)
    next(item for item in app.radio if item.label == "Intent").set_value("Build Model").run()
    button(app, "Prepare model").click().run()
    assert not app.exception
    labels = [getattr(item, "label", None) for item in app.main]
    assert labels.index("Prepare model") < labels.index("Prepared model / assumptions") < labels.index("Run model") < labels.index("Job details")
    assert any("Synthetic layers; not a field interpretation." in item.value for item in app.markdown)
    assert button(app, "Run model").disabled == confirmation_required
    if confirmation_required:
        checkbox = app.checkbox(key="fallback_confirmed")
        assert labels.index("Prepared model / assumptions") < labels.index(checkbox.label) < labels.index("Run model")
        checkbox.check().run()
        assert not app.exception
        assert not button(app, "Run model").disabled
