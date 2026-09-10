"""Optional real Streamlit widget tests: install the demo extra to run."""
from __future__ import annotations

from pathlib import Path
import json

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
    assert "last_result_models" not in app.session_state
    assert "last_preparation_model" not in app.session_state


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


def test_configured_nova_and_actual_openai_backup_are_distinct(app, monkeypatch):
    monkeypatch.setattr(GeoWorldBackendClient, "get_llm_health", lambda _self: {
        "details": {"overall_status": "degraded", "primary": {
            "provider": "bedrock", "model": "us.amazon.nova-2-lite-v1:0",
        }, "fallback": {"provider": "openai", "model": "gpt-4.1-mini"}},
    })
    result = JobResult(intent="rag_qa", reason="test", answer="A recorded answer", artifacts=[{
        "name": "answer.json", "kind": "json", "media_type": "application/json",
    }])
    app.session_state["last_job"] = JobStatusResponse(job_id="job-report", status="succeeded", progress="done", result=result)
    monkeypatch.setattr(GeoWorldBackendClient, "get_artifact", lambda *_args: json.dumps({
        "llm_usage": {"provider": "openai", "model": "gpt-4.1-mini", "success": True,
                      "fallback_reason": "do not expose this raw diagnostic"},
    }).encode())
    monkeypatch.setattr(GeoWorldBackendClient, "submit_job", lambda *_args: pytest.fail("label rendering must not submit jobs"))
    app.run(timeout=15)
    assert not app.exception
    assert any("Configured AI: Amazon Bedrock" in item.value for item in app.sidebar.caption)
    assert any("Backup AI: OpenAI" in item.value for item in app.sidebar.caption)
    assert any("Primary AI is unavailable; a backup is configured." == item.value for item in app.sidebar.warning)
    assert any(item.value == "Answer generation: OpenAI · gpt-4.1-mini (backup used)" for item in app.main.caption)
    assert all("raw diagnostic" not in item.value for item in app.caption)
    app.selectbox(key="display_layout").set_value("One column").run()
    assert any("Answer generation: OpenAI" in item.value for item in app.main.caption)


def test_preview_model_is_bound_to_accepted_job_not_later_previews(app, monkeypatch):
    model = {"provider": "bedrock", "model": "us.amazon.nova-2-lite-v1:0", "success": True}
    monkeypatch.setattr(GeoWorldBackendClient, "preview_geospec", lambda *_args, **_kwargs: {
        "valid": True, "interpretation_mode": "llm_semantic_parser", "llm": model.copy(),
        "geospec": {"assumptions": ["Synthetic test"]},
    })
    monkeypatch.setattr(GeoWorldBackendClient, "submit_job", lambda *_args: JobCreateResponse(job_id="new-model", status="queued", progress="queued"))
    monkeypatch.setattr(GeoWorldBackendClient, "get_job", lambda *_args: JobStatusResponse(
        job_id="new-model", status="succeeded", progress="complete",
        result=JobResult(intent="scenario_generation", reason="test", answer="Model"),
    ))
    app.run(timeout=15)
    next(item for item in app.radio if item.label == "Intent").set_value("Build Model").run()
    button(app, "Prepare model").click().run()
    assert any("Model preparation: Amazon Bedrock" in item.value for item in app.caption)
    button(app, "Run model").click().run()
    assert app.session_state["last_preparation_model"] == "Model preparation: Amazon Bedrock · us.amazon.nova-2-lite-v1:0"
    model.update(provider="openai", model="gpt-4.1-mini")
    button(app, "Prepare model").click().run()
    assert not app.exception
    captions = [item.value for item in app.main.caption]
    assert "Model preparation: OpenAI · gpt-4.1-mini" in captions
    assert "Model preparation: Amazon Bedrock · us.amazon.nova-2-lite-v1:0" in captions
    assert "Scientific model: deterministic computation, not an LLM." in captions
    next(item for item in app.radio if item.label == "Intent").set_value("Ask Question").run()
    button(app, "Ask GeoWorld").click().run()
    assert "last_preparation_model" not in app.session_state


def test_unavailable_model_metadata_does_not_hide_answer_or_use_health_as_evidence(app, monkeypatch):
    result = JobResult(intent="rag_qa", reason="test", answer="Keep this answer", artifacts=[{
        "name": "answer.json", "kind": "json", "media_type": "application/json",
    }])
    app.session_state["last_job"] = JobStatusResponse(job_id="job-report", status="succeeded", progress="done", result=result)

    def unavailable(*_args):
        raise GeoWorldClientError("Unavailable")

    monkeypatch.setattr(GeoWorldBackendClient, "get_artifact", unavailable)
    monkeypatch.setattr(GeoWorldBackendClient, "get_llm_health", unavailable)
    app.run(timeout=15)
    assert not app.exception
    assert any(item.value == "Keep this answer" for item in app.markdown)
    assert any(item.value == "Answer generation: model information not recorded." for item in app.caption)
    assert "last_result_models" not in app.session_state  # A later rerun can retry.
    monkeypatch.setattr(GeoWorldBackendClient, "get_artifact", lambda *_args: json.dumps({
        "llm_usage": {"provider": "bedrock", "model": "us.amazon.nova-2-lite-v1:0", "success": True},
    }).encode())
    app.run()
    assert any("Answer generation: Amazon Bedrock" in item.value for item in app.caption)


def test_logged_out_app_does_not_fetch_model_configuration_or_artifacts(app, monkeypatch):
    del app.session_state["access_token"]

    def forbidden(*_args):
        pytest.fail("model details must stay behind Studio login")

    monkeypatch.setattr(GeoWorldBackendClient, "get_llm_health", forbidden)
    monkeypatch.setattr(GeoWorldBackendClient, "get_artifact", forbidden)
    app.run(timeout=15)
    assert not app.exception
