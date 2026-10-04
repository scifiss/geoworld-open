"""One composer, authoritative HTTP decisions and session context across workflows."""
from io import BytesIO
from types import SimpleNamespace

import pytest

from test_studio_request import app, button, _seismic_workspace_backend
from tests.fixtures.seismic_explorer_app import DATASETS
from tests.fixtures.horizon_explorer_app import API as HorizonAPI
from geoworld_open.client import GeoWorldBackendClient, GeoWorldClientError
from geoworld_open.client.models import JobCreateResponse, JobResult, JobStatusResponse
from geoworld_open.client.seismic import SeismicDatasetCatalog
from geoworld_open.client.studio_request import StudioDecision, StudioIntent


def send(app, text):
    app.text_area(key="assistant_prompt").set_value(text)
    button(app, "Send").click().run(timeout=20)
    assert not app.exception
    assert [item.label for item in app.text_area] == ["Message GeoWorld"]


def test_shared_composer_moves_between_question_seismic_and_model_and_keeps_history(app, monkeypatch):
    _seismic_workspace_backend(monkeypatch, [])
    routed = []
    def route(_self, prompt):
        routed.append(prompt)
        operation, selected = {
            "What is impedance?": ("question", "ask_question"),
            "show inline 1212 of my seismic": ("seismic", "seismic_explorer"),
            "Build shale and sand": ("build", "build_model"),
            "Inspect my uploaded LAS logs": ("las", "las_quicklook"),
        }[prompt]
        return StudioDecision(interpretation=StudioIntent(operation=operation), route=selected, message="Request accepted.")
    monkeypatch.setattr(GeoWorldBackendClient, "interpret_studio", route)
    monkeypatch.setattr(GeoWorldBackendClient, "submit_job", lambda *_: JobCreateResponse(job_id="a" * 32, status="queued", progress="queued"))
    monkeypatch.setattr(GeoWorldBackendClient, "get_job", lambda *_: JobStatusResponse(
        job_id="a" * 32, status="succeeded", progress="done",
        result=JobResult(intent="qa", reason="test", answer="Impedance is density times velocity."),
    ))
    monkeypatch.setattr(GeoWorldBackendClient, "preview_geospec", lambda *_args, **_kwargs: {
        "valid": True, "geospec": {"assumptions": ["User-selected synthetic layers"]},
    })
    app.run(timeout=20)
    send(app, "What is impedance?")
    send(app, "show inline 1212 of my seismic")
    assert len(app.get("plotly_chart")) == 1
    assert not any(item.label == "Dataset" for item in app.selectbox)
    send(app, "Build shale and sand")
    assert any(item.value == "Prepared model" for item in app.subheader)
    assert any("Impedance is density" in item.value for item in app.markdown)
    assert any("Applied deterministic section" in item.value for item in app.markdown)
    send(app, "Inspect my uploaded LAS logs")
    assert app.session_state["studio_decision"].route == "las_quicklook"
    assert routed == ["What is impedance?", "show inline 1212 of my seismic", "Build shale and sand", "Inspect my uploaded LAS logs"]
    history = list(app.session_state["assistant_history"])
    app.run(timeout=20)
    assert app.session_state["assistant_history"] == history
    assert len(routed) == 4


def test_benchmarks_are_fetched_only_by_explicit_example_action(app, monkeypatch):
    _seismic_workspace_backend(monkeypatch)
    calls = []
    benchmark = HorizonAPI()
    monkeypatch.setattr(GeoWorldBackendClient, "list_horizon_benchmarks", lambda *_: calls.append("catalog") or SeismicDatasetCatalog(datasets=[benchmark.dataset]))
    app.run(timeout=20)
    assert calls == []
    assert not any(item.label == "Synthetic benchmark case" for item in app.selectbox)
    app.session_state["studio_active_context"] = "seismic"
    app.run(timeout=20)
    assert calls == []
    assert "Attached: Line A" in [item.value for item in app.caption]
    button(app, "Explore a synthetic horizon example").click().run(timeout=20)
    assert calls == ["catalog"]
    assert app.selectbox(key="assistant_example_choice").options == [benchmark.dataset.display_name]
    monkeypatch.setattr(GeoWorldBackendClient, "get_seismic_view", lambda _self, request: benchmark.get_seismic_view(request))
    button(app, "Open example").click().run(timeout=20)
    assert not app.exception
    assert any("Synthetic benchmark" in item.value for item in app.markdown)
    assert not any(item.label == "Dataset" for item in app.selectbox)
    assert app.button(key="horizon_track").disabled
    assert len(app.text_area) == 1


def test_secure_attachment_activates_returned_dataset_without_copying_source(monkeypatch):
    from geoworld_open import studio_assistant
    state = {"seismic_dataset_id": DATASETS[1].dataset_id, "seismic_response": {"old": True}, "manual_tools": True}
    monkeypatch.setattr(studio_assistant.st, "session_state", state)
    source = BytesIO(b"fixture content")
    source.name = "attached.sgy"
    source.seek(5)
    def upload(name, stream):
        assert name == "attached.sgy" and stream is source and stream.tell() == 0
        return SimpleNamespace(status="ready", dataset=DATASETS[0], display_filename=name)
    studio_assistant.attach_seismic(SimpleNamespace(upload_seismic=upload), source)
    assert state["seismic_dataset_id"] == DATASETS[0].dataset_id
    assert state["studio_active_context"] == "seismic"
    assert "seismic_response" not in state
    assert state["assistant_notice"] == "Attached: attached.sgy"
    assert source.getvalue() == b"fixture content"
    assert state["manual_tools"] is False


def test_failed_attachment_keeps_existing_context(monkeypatch):
    from geoworld_open import studio_assistant
    state = {"seismic_dataset_id": DATASETS[0].dataset_id}
    monkeypatch.setattr(studio_assistant.st, "session_state", state)
    source = BytesIO(b"bad file")
    source.name = "bad.sgy"
    api = SimpleNamespace(upload_seismic=lambda *_: SimpleNamespace(status="failed", dataset=None, validation_message="Invalid SEG-Y"))
    with pytest.raises(GeoWorldClientError, match="Invalid SEG-Y"):
        studio_assistant.attach_seismic(api, source)
    assert state == {"seismic_dataset_id": DATASETS[0].dataset_id}


def test_missing_uploaded_file_is_actionable_and_raw_condition_is_retained(app, monkeypatch, caplog):
    warning = "lost.sgy: uploaded dataset is unavailable or failed revalidation."
    monkeypatch.setattr(GeoWorldBackendClient, "list_seismic_datasets", lambda *_: SeismicDatasetCatalog(warnings=[warning]))
    app.session_state["studio_active_context"] = "seismic"
    app.session_state["seismic_dataset_id"] = "d" * 24
    app.run(timeout=20)
    assert not app.exception
    assert any("Reattach it to continue" in item.value for item in app.warning)
    assert not any("failed revalidation" in item.value for item in app.warning)
    assert app.session_state["seismic_catalog_warnings"] == [warning]
    assert warning in caplog.text
    assert len(app.get("plotly_chart")) == 0
    assert len(app.get("file_uploader")) == 1


def test_logout_clears_session_conversation_and_attachment_context(app):
    app.session_state["assistant_history"] = [{"role": "user", "content": "Private session"}]
    app.session_state["seismic_context_dataset"] = DATASETS[0]
    app.run(timeout=20)
    button(app, "Log out").click().run(timeout=20)
    assert "assistant_history" not in app.session_state
    assert "seismic_context_dataset" not in app.session_state
