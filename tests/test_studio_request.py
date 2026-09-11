"""Real Streamlit reruns with fake HTTP responses; never starts a solver."""
import json
from pathlib import Path

import pytest
pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

from geoworld_open.client import GeoWorldBackendClient, GeoWorldClientError
from geoworld_open.client.models import JobCreateResponse, JobResult, JobStatusResponse
from geoworld_open.client.marmousi import MarmousiInterpretation, MarmousiSelection
from geoworld_open.client.studio_request import StudioDecision, StudioIntent
from test_studio_marmousi import make_preview
from test_studio_reference import make_preview as reference_preview

ROOT = Path(__file__).resolve().parents[1]


def button(app, label):
    return next(b for b in app.button if b.label == label)


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("GEOWORLD_BACKEND_URL", "http://127.0.0.1:8100")
    monkeypatch.setenv("GEOWORLD_STUDIO_LOCAL_RTM", "1")
    monkeypatch.setattr(GeoWorldBackendClient, "get_llm_health", lambda _: {})
    monkeypatch.setattr(GeoWorldBackendClient, "get_export", lambda *_: b"archive-fixture")
    monkeypatch.setattr(GeoWorldBackendClient, "get_artifact", lambda *_: (ROOT / "docs/assets/flagship_world_demo.png").read_bytes())
    monkeypatch.setattr(GeoWorldBackendClient, "submit_job", lambda *_: pytest.fail("No implicit numerical job permitted"))
    at = AppTest.from_file(str(ROOT / "apps/studio_streamlit.py"))
    at.session_state["access_token"] = "test-token"
    at.session_state["user_email"] = "fixture@example.test"
    return at


def completed(app):
    result = JobResult(intent="deepwave_reference", reason="test", answer="Saved RTM result", artifacts=[
        {"name": "reference/example_rtm.jpg", "kind": "image", "media_type": "image/jpeg"}])
    app.session_state["last_job_id"] = "a" * 32
    app.session_state["last_job"] = JobStatusResponse(job_id="a"*32, status="succeeded", progress="complete", result=result)
    app.session_state["last_submitted_prompt"] = "Original RTM request."


def test_default_is_one_prompt_no_workspace_choices_or_dataset_default(app):
    app.run(timeout=20)
    assert not app.exception
    assert [t.label for t in app.text_area] == ["What would you like GeoWorld to do?"]
    assert not any(r.label in {"Workspace", "Intent"} for r in app.radio)
    assert not any(s.label == "Benchmark dataset" for s in app.selectbox)


def test_hosted_marmousi1_shows_plot_and_only_available_properties(app, monkeypatch):
    monkeypatch.setenv("GEOWORLD_BACKEND_URL", "https://backend.example.test")
    monkeypatch.delenv("GEOWORLD_STUDIO_LOCAL_RTM", raising=False)
    monkeypatch.setattr(GeoWorldBackendClient, "interpret_studio", lambda _self, prompt:
        StudioDecision(interpretation=StudioIntent(operation="preview", dataset="marmousi1"),
            route="marmousi_model", message="Preview Marmousi 1",
            llm={"provider": "bedrock", "model": "test-nova", "success": True}))
    monkeypatch.setattr(GeoWorldBackendClient, "interpret_marmousi", lambda _self, prompt:
        MarmousiInterpretation(selection=MarmousiSelection(dataset="marmousi1"), unresolved=[]))
    def preview(_self, selection):
        result = make_preview(selection)
        result.fields = ["vp", "density"]
        return result
    monkeypatch.setattr(GeoWorldBackendClient, "preview_marmousi", preview)
    app.run(timeout=20)
    app.text_area(key="prompt").set_value("show Marmousi 1").run()
    button(app, "Interpret request").click().run(timeout=20)
    assert not app.exception
    assert len(app.get("plotly_chart")) == 1
    assert app.selectbox(key="marmousi_property").options == ["vp", "density"]
    assert not any(b.label in {"Run verified reference", "Run model"} for b in app.button)
    assert button(app, "Save model preview & provenance")
    assert any("What can I demo here?" == e.label for e in app.expander)


def test_marmousi2_interpretation_drives_preview_and_rerun_is_free(app, monkeypatch):
    calls = []
    def route(_self, prompt):
        calls.append(("route", prompt))
        return StudioDecision(interpretation=StudioIntent(operation="preview", dataset="marmousi2"),
            route="marmousi_model", message="Preview Marmousi 2", llm={"provider": "bedrock", "model": "test-nova", "success": True})
    def model(_self, prompt):
        calls.append(("model", prompt))
        return MarmousiInterpretation(selection=MarmousiSelection(dataset="marmousi2"), unresolved=[])
    monkeypatch.setattr(GeoWorldBackendClient, "interpret_studio", route)
    monkeypatch.setattr(GeoWorldBackendClient, "interpret_marmousi", model)
    monkeypatch.setattr(GeoWorldBackendClient, "preview_marmousi", lambda _self, selection: make_preview(selection))
    app.run(timeout=20)
    app.text_area(key="prompt").set_value("Show Marmousi 2").run()
    button(app, "Interpret request").click().run(timeout=20)
    assert not app.exception
    assert app.session_state["marmousi_preview"].selection.dataset == "marmousi2"
    assert any("**Dataset:** Marmousi 2" == m.value for m in app.markdown)
    assert not any(s.label == "Benchmark dataset" for s in app.selectbox)
    assert not any("no LLM" in b.label for b in app.button)
    app.selectbox(key="display_layout").set_value("Two columns").run(timeout=20)
    assert not app.exception and len(calls) == 2
    app.text_area(key="prompt").set_value("Run FWI on Marmousi 2").run()
    assert not any(b.label == "Save model preview & provenance" for b in app.button)
    assert len(calls) == 2


def test_new_preview_request_hides_previous_rtm_result(app, monkeypatch):
    completed(app)

    def route(_self, prompt):
        return StudioDecision(
            interpretation=StudioIntent(operation="preview", dataset="marmousi2"),
            route="marmousi_model",
            message="Preview Marmousi 2",
            llm={"provider": "bedrock", "model": "test-nova", "success": True},
        )

    def model(_self, prompt):
        return MarmousiInterpretation(selection=MarmousiSelection(dataset="marmousi2"), unresolved=[])

    monkeypatch.setattr(GeoWorldBackendClient, "interpret_studio", route)
    monkeypatch.setattr(GeoWorldBackendClient, "interpret_marmousi", model)
    monkeypatch.setattr(GeoWorldBackendClient, "preview_marmousi", lambda _self, selection: make_preview(selection))

    app.run(timeout=20)
    assert any("Saved RTM result" in item.value for item in app.markdown)
    app.text_area(key="prompt").set_value("Show Marmousi 2").run()
    button(app, "Interpret request").click().run(timeout=20)

    assert not app.exception
    assert any("**Dataset:** Marmousi 2" == item.value for item in app.markdown)
    assert not any("Saved RTM result" in item.value for item in app.markdown)
    assert app.session_state["last_job_id"] == "a" * 32


def test_reference_figures_are_labeled_as_input_processing_and_output(app):
    result = JobResult(intent="deepwave_reference", reason="test", answer="Saved RTM result", artifacts=[
        {"name": "reference/velocity_acquisition.png", "kind": "image", "media_type": "image/png"},
        {"name": "reference/example_rtm_mask.jpg", "kind": "image", "media_type": "image/jpeg"},
        {"name": "reference/example_rtm.jpg", "kind": "image", "media_type": "image/jpeg"},
    ])
    app.session_state["last_job_id"] = "a" * 32
    app.session_state["last_job"] = JobStatusResponse(
        job_id="a" * 32,
        status="succeeded",
        progress="complete",
        result=result,
    )
    app.session_state["last_submitted_prompt"] = "Run official RTM reference."
    app.session_state["last_result_source"] = "saved_run"

    app.run(timeout=20)

    captions = [item.value for item in app.caption]
    assert any("INPUT / PROVENANCE" in item for item in captions)
    assert any("PROCESSING DIAGNOSTIC" in item for item in captions)
    assert any("OUTPUT: one-update Born-adjoint RTM image" in item for item in captions)


def test_export_keeps_reference_and_does_not_reinterpret_or_submit(app, monkeypatch):
    completed(app)
    calls = []
    def route(*_):
        calls.append("route")
        return StudioDecision(interpretation=StudioIntent(operation="rtm", dataset="marmousi1", prepare_only=True),
            route="deepwave_reference", message="Prepare reference")
    def prepare(*_, **kwargs):
        calls.append("prepare")
        return reference_preview("prepare")
    monkeypatch.setattr(GeoWorldBackendClient, "interpret_studio", route)
    monkeypatch.setattr(GeoWorldBackendClient, "preview_reference", prepare)
    app.run(timeout=20)
    app.text_area(key="prompt").set_value("Prepare the RTM reference but do not run").run()
    button(app, "Interpret request").click().run(timeout=20)
    assert not app.exception and button(app, "Run verified reference").disabled
    button(app, "Prepare HTML report").click().run(timeout=20)
    assert not app.exception
    assert calls == ["route", "prepare"]
    assert app.session_state["last_job_id"] == "a"*32
    assert "Original RTM request." in app.session_state["clean_report"][2]
    assert "Saved RTM result" in app.session_state["clean_report"][2]
    assert "data:image/" in app.session_state["clean_report"][2]
    assert app.session_state["studio_decision"].route == "deepwave_reference"
    app.checkbox(key="manual_tools").check().run(timeout=20)
    assert not app.exception and app.session_state["last_job_id"] == "a"*32
    button(app, "Prepare HTML report").click().run(timeout=20)
    app.checkbox(key="manual_tools").uncheck().run(timeout=20)
    assert not app.exception and app.session_state["last_job_id"] == "a"*32


def test_reopen_saved_job_restores_prompt_without_llm_or_job(app, monkeypatch):
    job = JobStatusResponse(job_id="b"*32, status="succeeded", progress="done",
        result=JobResult(intent="deepwave_reference", reason="replay", answer="Saved result"))
    monkeypatch.setattr(GeoWorldBackendClient, "get_job", lambda *_: job)
    monkeypatch.setattr(GeoWorldBackendClient, "get_artifact", lambda *_: json.dumps({"prompt": "Recorded question"}).encode())
    app.run(timeout=20)
    app.text_input(key="saved_job_id").set_value("b"*32).run()
    button(app, "Open run").click().run(timeout=20)
    assert not app.exception and app.session_state["last_job_id"] == "b"*32
    assert app.session_state["last_submitted_prompt"] == "Recorded question"
    button(app, "Prepare HTML report").click().run(timeout=20)
    assert "Recorded question" in app.session_state["clean_report"][2]
    monkeypatch.setattr(GeoWorldBackendClient, "get_job", lambda *_: (_ for _ in ()).throw(GeoWorldClientError("Job not found")))
    app.text_input(key="saved_job_id").set_value("c"*32).run()
    button(app, "Open run").click().run(timeout=20)
    assert not app.exception and app.session_state["last_job_id"] == "b"*32


def test_unsupported_request_shows_explanation_without_model_controls(app, monkeypatch):
    monkeypatch.setattr(GeoWorldBackendClient, "interpret_studio", lambda *_: StudioDecision(
        interpretation=StudioIntent(operation="fwi", dataset="marmousi1"), route="blocked", message="FWI is not implemented."))
    completed(app)
    app.run(timeout=20)
    app.text_area(key="prompt").set_value("Run FWI using Marmousi1 cropped x=0 to x=1000").run()
    button(app, "Interpret request").click().run(timeout=20)
    assert not app.exception and any("FWI is not implemented" in w.value for w in app.warning)
    assert not any("Run model" == b.label or "Run verified" in b.label for b in app.button)
    assert app.session_state["last_job_id"] == "a"*32


def test_question_route_submits_existing_qa_workflow_and_shows_answer(app, monkeypatch):
    prompt = "How does GeoWorld calculate acoustic impedance and normal-incidence reflectivity?"
    submitted = []
    monkeypatch.setattr(GeoWorldBackendClient, "interpret_studio", lambda *_: StudioDecision(
        interpretation=StudioIntent(operation="question"), route="ask_question",
        message="Answer your question using the existing knowledge/Q&A workflow.",
        llm={"provider": "bedrock", "model": "test-nova", "success": True}))
    def create(_self, request):
        submitted.append(request)
        return JobCreateResponse(job_id="d"*32, status="queued", progress="queued")
    monkeypatch.setattr(GeoWorldBackendClient, "submit_job", create)
    monkeypatch.setattr(GeoWorldBackendClient, "get_job", lambda *_: JobStatusResponse(
        job_id="d"*32, status="succeeded", progress="complete",
        result=JobResult(intent="qa", reason="question", answer="AI = density multiplied by Vp.")))
    app.run(timeout=20)
    app.text_area(key="prompt").set_value(prompt).run()
    button(app, "Interpret request").click().run(timeout=20)
    assert not app.exception
    assert len(submitted) == 1
    assert submitted[0].mode_hint == "ask_question" and submitted[0].prompt == prompt
    assert app.session_state["last_job"].result.answer == "AI = density multiplied by Vp."
