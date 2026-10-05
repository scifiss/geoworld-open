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


def test_send_clears_composer_only_after_acceptance_and_preserves_unsent_draft(app, monkeypatch):
    _seismic_workspace_backend(monkeypatch)
    monkeypatch.setattr(GeoWorldBackendClient, "interpret_studio", lambda *_args, **_kwargs:
                        StudioDecision(interpretation=StudioIntent(operation="seismic"),
                                       route="seismic_explorer", message="Inspect active data."))
    app.session_state["studio_active_context"] = "seismic"
    app.run(timeout=20)
    prompt = "Show the amplitude statistics"
    app.text_area(key="assistant_prompt").set_value(prompt).run(timeout=20)
    app.slider(key=f"seismic_clip_{DATASETS[0].dataset_id}").set_value(97.0).run(timeout=20)
    assert app.text_area(key="assistant_prompt").value == prompt
    button(app, "Send").click().run(timeout=20)
    assert not app.exception
    assert any(item == {"role": "user", "content": prompt}
               for item in app.session_state["assistant_history"])
    assert app.text_area(key="assistant_prompt").value == ""
    assert app.session_state["assistant_prompt"] == ""


def test_failed_interpretation_preserves_composer_draft(app, monkeypatch):
    monkeypatch.setattr(GeoWorldBackendClient, "interpret_studio", lambda *_args, **_kwargs:
                        (_ for _ in ()).throw(GeoWorldClientError("Provider unavailable")))
    app.run(timeout=20)
    prompt = "Build a model of shale and sand"
    app.text_area(key="assistant_prompt").set_value(prompt).run(timeout=20)
    button(app, "Send").click().run(timeout=20)
    assert app.text_area(key="assistant_prompt").value == prompt
    assert any("Provider unavailable" in item["content"]
               for item in app.session_state["assistant_history"] if item["role"] == "assistant")


def test_shared_composer_moves_between_question_seismic_and_model_and_keeps_history(app, monkeypatch):
    _seismic_workspace_backend(monkeypatch, [])
    routed = []
    def route(_self, prompt, **_context):
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


def test_exact_model_followups_accumulate_in_session_without_qa(app, monkeypatch):
    first = (
        "build a model of sand, shale, carbonate, and sand. the sand is high porous, "
        "list assumptions. there is a fault in the top 2 layers."
    )
    second = "use your best assumptions."
    previews = []

    def route(_self, prompt, **context):
        assert context.get("has_pending_build", False) == (prompt == second)
        return StudioDecision(
            interpretation=StudioIntent(operation="build", dataset="synthetic"),
            route="build_model", message="Review the pending model.",
            continues_build=prompt == second,
        )

    def preview(_self, **request):
        previews.append(request)
        spec = request.get("geospec") or {"geology": {"layers": [
            {"lithology": name, "porosity": .28 if name == "sand" else None}
            for name in ("sand", "shale", "carbonate", "sand")
        ]}, "assumptions": ["Default grid and layer thickness policy"]}
        return {"valid": False, "geospec": spec, "assumptions": spec["assumptions"],
                "issues": [{"severity": "error", "message":
                            "A fault confined to the top two layers is not supported. "
                            "Should I use a through-going fault or omit the fault?"}]}

    monkeypatch.setattr(GeoWorldBackendClient, "interpret_studio", route)
    monkeypatch.setattr(GeoWorldBackendClient, "preview_geospec", preview)
    app.run(timeout=20)
    send(app, first)
    send(app, second)
    pending = app.session_state["studio_pending_build"]
    assert pending["turns"] == [first, second]
    assert [layer["lithology"] for layer in pending["geospec"]["geology"]["layers"]] == [
        "sand", "shale", "carbonate", "sand",
    ]
    assert previews[0] == {"prompt": first}
    assert previews[1] == {"geospec": pending["geospec"],
                           "follow_up": second, "prior_turns": [first]}
    assert button(app, "Run model").disabled
    assert any("through-going fault or omit" in item["content"]
               for item in app.session_state["assistant_history"] if item["role"] == "assistant")


def test_interpretation_failure_keeps_active_seismic_view_and_history(app, monkeypatch):
    _seismic_workspace_backend(monkeypatch)
    app.session_state["studio_active_context"] = "seismic"
    app.run(timeout=20)
    original = app.session_state["seismic_response"]
    dataset = app.session_state["seismic_dataset_id"]
    monkeypatch.setattr(GeoWorldBackendClient, "interpret_studio",
                        lambda *_args, **_kwargs: (_ for _ in ()).throw(
                            GeoWorldClientError("Provider temporarily unavailable")))
    send(app, "what is the sample interval?")
    assert app.session_state["studio_active_context"] == "seismic"
    assert app.session_state["seismic_dataset_id"] == dataset
    assert app.session_state["seismic_response"] == original
    assert len(app.get("plotly_chart")) == 1
    assert any("Provider temporarily unavailable" in item["content"]
               for item in app.session_state["assistant_history"] if item["role"] == "assistant")


def test_three_turn_limestone_request_keeps_explicit_layer_and_porosity(app, monkeypatch):
    turns = [
        "create a model with highly carbon dioxide rich limestone",
        "make it 3 layers, the limestone layer has porosity of 0.3",
        "please make reasonable assumptions for the unspecified parameters",
    ]
    previews = []

    def route(_self, prompt, **context):
        assert context.get("has_pending_build", False) == (prompt != turns[0])
        return StudioDecision(
            interpretation=StudioIntent(operation="build", dataset="synthetic"),
            route="build_model", message="Review the pending model.",
            continues_build=prompt != turns[0],
        )

    def preview(_self, **request):
        previews.append(request)
        spec = request.get("geospec") or {"geology": {"layers": [
            {"lithology": "limestone", "porosity": None}
        ]}, "assumptions": ["Existing grid default"]}
        if request.get("follow_up") == turns[1]:
            spec = {**spec, "geology": {"layers": [
                {"lithology": "shale", "porosity": None},
                {"lithology": "limestone", "porosity": .3},
                {"lithology": "shale", "porosity": None},
            ]}}
        return {"valid": False, "geospec": spec,
                "issues": [{"severity": "error", "message":
                            "CO2 substitution applies to sand, not limestone. "
                            "Use a sand host or omit CO2?"}]}

    monkeypatch.setattr(GeoWorldBackendClient, "interpret_studio", route)
    monkeypatch.setattr(GeoWorldBackendClient, "preview_geospec", preview)
    app.run(timeout=20)
    for turn in turns:
        send(app, turn)
    pending = app.session_state["studio_pending_build"]
    assert pending["turns"] == turns
    assert [layer["lithology"] for layer in pending["geospec"]["geology"]["layers"]] == [
        "shale", "limestone", "shale",
    ]
    assert pending["geospec"]["geology"]["layers"][1]["porosity"] == .3
    assert previews[2]["prior_turns"] == turns[:2]
    assert previews[2]["follow_up"] == turns[2]
    assert button(app, "Run model").disabled


def test_sand_co2_and_porous_carbonate_followups_keep_pending_spec(app, monkeypatch):
    turns = [
        "build a model of 3 layers, shale, sand, and carbonate. sand has CO2, and carbonate is very porous",
        "yes, use sand as the CO2 host and keep carbonate without CO2",
        "use your best assumptions",
    ]
    requests = []
    spec = {"geology": {"layers": [
        {"lithology": "shale", "porosity": None},
        {"lithology": "sand", "porosity": None},
        {"lithology": "carbonate", "porosity": .28},
    ]}, "petrophysics": {"co2_plume": {"enabled": True}},
        "assumptions": ["CO2 host is sand", "Very porous carbonate uses 0.28"]}

    def route(_self, prompt, **context):
        continuing = prompt != turns[0]
        assert context.get("has_pending_build", False) == continuing
        return StudioDecision(
            interpretation=StudioIntent(operation="build", dataset="synthetic"),
            route="build_model", message="Review model.", continues_build=continuing,
        )

    def preview(_self, **request):
        requests.append(request)
        return {"valid": True, "geospec": request.get("geospec") or spec,
                "assumptions": spec["assumptions"], "issues": []}

    monkeypatch.setattr(GeoWorldBackendClient, "interpret_studio", route)
    monkeypatch.setattr(GeoWorldBackendClient, "preview_geospec", preview)
    app.run(timeout=20)
    for turn in turns:
        send(app, turn)
        assert app.text_area(key="assistant_prompt").value == ""
    pending = app.session_state["studio_pending_build"]
    assert pending["turns"] == turns
    assert pending["geospec"]["geology"]["layers"][2] == {
        "lithology": "carbonate", "porosity": .28,
    }
    assert pending["geospec"]["petrophysics"]["co2_plume"]["enabled"]
    assert requests[1]["prior_turns"] == turns[:1]
    assert requests[2]["prior_turns"] == turns[:2]
    assert not any(request.get("prompt") in turns[1:] for request in requests)


def test_attached_seismic_commands_forward_dataset_context_and_keep_single_chat(app, monkeypatch):
    turns = []
    routed = []
    _seismic_workspace_backend(monkeypatch, turns)

    def route(_self, prompt, **context):
        routed.append((prompt, context))
        return StudioDecision(interpretation=StudioIntent(operation="seismic"),
                              route="seismic_explorer", message="Use active seismic data.")

    monkeypatch.setattr(GeoWorldBackendClient, "interpret_studio", route)
    app.session_state["studio_active_context"] = "seismic"
    app.run(timeout=20)
    commands = [
        "what are the inline and crossline ranges?",
        "what kind of data is this?",
        "what is the sample interval?",
        "show inline 1212",
        "show crossline 320",
        "show the trace at inline 1215, crossline 315",
        "what's the data of the sgy? what's the inline and crossline ranges?",
        "what kind of data is this and what are its inline/crossline ranges?",
        "what's the inline and outline ranges?",
        "what is the vertical domain and sample count?",
    ]
    for command in commands:
        send(app, command)
    assert [entry[0] for entry in routed] == commands
    assert all(entry[1]["active_seismic_dataset_id"] == DATASETS[0].dataset_id for entry in routed)
    assert [entry[0] for entry in turns] == commands
    assert len(app.text_area) == 1
    assert all(any(message["content"] == command for message in app.session_state["assistant_history"])
               for command in commands)


def test_model_provider_failure_restores_active_seismic_workspace(app, monkeypatch):
    _seismic_workspace_backend(monkeypatch)
    monkeypatch.setattr(GeoWorldBackendClient, "interpret_studio", lambda *_args, **_kwargs:
                        StudioDecision(interpretation=StudioIntent(operation="build"),
                                       route="build_model", message="Prepare model."))
    monkeypatch.setattr(GeoWorldBackendClient, "preview_geospec", lambda *_args, **_kwargs:
                        (_ for _ in ()).throw(GeoWorldClientError("Model provider unavailable")))
    app.session_state["studio_active_context"] = "seismic"
    app.run(timeout=20)
    dataset = app.session_state["seismic_dataset_id"]
    original = app.session_state["seismic_response"]
    send(app, "build a model of sand and shale")
    assert app.session_state["studio_active_context"] == "seismic"
    assert app.session_state["seismic_dataset_id"] == dataset
    assert app.session_state["seismic_response"] == original
    assert len(app.get("plotly_chart")) == 1
    assert any("Model provider unavailable" in item["content"]
               for item in app.session_state["assistant_history"] if item["role"] == "assistant")


def test_seismic_command_failure_keeps_current_view_and_reports_in_history(app, monkeypatch):
    _seismic_workspace_backend(monkeypatch)
    monkeypatch.setattr(GeoWorldBackendClient, "interpret_studio", lambda *_args, **_kwargs:
                        StudioDecision(interpretation=StudioIntent(operation="seismic"),
                                       route="seismic_explorer", message="Inspect active data."))
    monkeypatch.setattr(GeoWorldBackendClient, "continue_seismic_explorer",
                        lambda *_args, **_kwargs: (_ for _ in ()).throw(
                            GeoWorldClientError("Seismic service temporarily unavailable")))
    app.session_state["studio_active_context"] = "seismic"
    app.run(timeout=20)
    original = app.session_state["seismic_response"]
    send(app, "show inline 1212")
    assert app.session_state["studio_active_context"] == "seismic"
    assert app.session_state["seismic_response"] == original
    assert len(app.get("plotly_chart")) == 1
    assert any("Seismic service temporarily unavailable" in item["content"]
               for item in app.session_state["assistant_history"] if item["role"] == "assistant")


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
    monkeypatch.setattr(GeoWorldBackendClient, "list_seismic_datasets", lambda *_: SeismicDatasetCatalog(warnings=[warning, warning]))
    app.session_state["studio_active_context"] = "seismic"
    app.session_state["seismic_dataset_id"] = "d" * 24
    app.run(timeout=20)
    assert not app.exception
    assert sum("Reattach it to continue" in item.value for item in app.warning) == 1
    assert not any("failed revalidation" in item.value for item in app.warning)
    assert app.session_state["seismic_catalog_warnings"] == [warning, warning]
    assert warning in caplog.text
    assert len(app.get("plotly_chart")) == 0
    assert len(app.get("file_uploader")) == 1
    assert button(app, "Upload and attach").disabled
    assert any("Choose a SEG-Y file, then click Upload and attach" in item.value
               for item in app.caption)


def test_logout_clears_session_conversation_and_attachment_context(app):
    app.session_state["assistant_history"] = [{"role": "user", "content": "Private session"}]
    app.session_state["seismic_context_dataset"] = DATASETS[0]
    app.run(timeout=20)
    button(app, "Log out").click().run(timeout=20)
    assert "assistant_history" not in app.session_state
    assert "seismic_context_dataset" not in app.session_state
