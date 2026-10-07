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


@pytest.mark.parametrize("origin,defaults", [
    ("build shale, sand, shale with CO2 in sand", False),
    ("build shale, sand, carbonate. sand has CO2, carbonate is very porous", True),
])
def test_typed_prepared_context_run_turn_submits_exact_spec_once(app, monkeypatch, origin, defaults):
    preparations, jobs, contexts = [], [], []
    spec = {"geology": {"layers": [{"lithology": rock, "porosity": .28 if rock == "carbonate" else None}
           for rock in ("shale", "sand", "carbonate" if defaults else "shale")]},
           "petrophysics": {"co2_plume": {"enabled": True}}, "assumptions": ["Documented grid defaults"]}
    def route(_self, prompt, **kwargs):
        context = kwargs["context"]
        contexts.append(context.model_dump())
        action = "run_prepared_build" if prompt == "run it" else (
            "prepare_build" if prompt == "use your best assumptions" else "new_task")
        if action != "new_task":
            assert context.build.geospec == spec
            assert context.execution_allowed
            assert context.active_task == "build"
        return StudioDecision(interpretation=StudioIntent(operation="build"), route="build_model",
            action=action, continues_build=action == "prepare_build", message="Review model.")
    def preview(_self, **kwargs):
        preparations.append(kwargs)
        return {"valid": True, "geospec": spec, "assumptions": spec["assumptions"]}
    monkeypatch.setattr(GeoWorldBackendClient, "interpret_studio", route)
    monkeypatch.setattr(GeoWorldBackendClient, "preview_geospec", preview)
    monkeypatch.setattr(GeoWorldBackendClient, "submit_job", lambda _self, req:
        jobs.append(req) or JobCreateResponse(job_id="d" * 32, status="queued", progress="queued"))
    monkeypatch.setattr(GeoWorldBackendClient, "get_job", lambda *_:
        JobStatusResponse(job_id="d" * 32, status="succeeded", progress="done",
                          result=JobResult(intent="build_model", reason="test", answer="Built prepared model.")))
    app.run(timeout=20)
    send(app, origin)
    assert not jobs
    assert any("Assumptions before execution" in turn["content"] for turn in app.session_state["assistant_history"])
    if defaults:
        send(app, "use your best assumptions")
        assert preparations[-1]["geospec"] == spec
        assert preparations[-1]["prior_turns"] == [origin]
    send(app, "run it")
    assert len(jobs) == 1
    assert jobs[0].geospec == spec
    assert origin in jobs[0].prompt
    assert len(preparations) == (2 if defaults else 1)
    app.run(timeout=20)
    assert len(jobs) == 1
    assert app.text_area(key="assistant_prompt").value == ""


def test_seismic_qa_detour_keeps_dataset_view_and_next_trace_context(app, monkeypatch):
    turns, received = [], []
    _seismic_workspace_backend(monkeypatch, turns)
    def route(_self, prompt, **kwargs):
        received.append(kwargs["context"].model_dump())
        question = prompt == "What is acoustic impedance?"
        return StudioDecision(interpretation=StudioIntent(operation="question" if question else "seismic"),
            route="ask_question" if question else "seismic_explorer", action="general_question" if question else "seismic_view_command",
            command=None if question else prompt, message="Accepted.")
    monkeypatch.setattr(GeoWorldBackendClient, "interpret_studio", route)
    monkeypatch.setattr(GeoWorldBackendClient, "submit_job", lambda *_:
        JobCreateResponse(job_id="e" * 32, status="queued", progress="queued"))
    monkeypatch.setattr(GeoWorldBackendClient, "get_job", lambda *_:
        JobStatusResponse(job_id="e" * 32, status="succeeded", progress="done",
                          result=JobResult(intent="qa", reason="test", answer="Density times velocity.")))
    app.session_state["studio_active_context"] = "seismic"
    app.run(timeout=20)
    before = app.session_state["studio_task_context"].model_dump()
    send(app, "What is acoustic impedance?")
    assert app.session_state["studio_active_context"] == "seismic"
    assert len(app.get("plotly_chart")) == 1
    after = app.session_state["studio_task_context"].model_dump()
    assert after["active_seismic_dataset_id"] == before["active_seismic_dataset_id"]
    assert after["seismic_view"] == before["seismic_view"]
    send(app, "show the trace at inline 1215, crossline 315")
    assert received[-1]["active_seismic_dataset_id"] == before["active_seismic_dataset_id"]
    assert received[-1]["seismic_view"] == before["seismic_view"]
    assert turns[-1][0] == "show the trace at inline 1215, crossline 315"


def test_question_detour_keeps_prepared_build_and_no_reprepare(app, monkeypatch):
    requests = []
    def route(_self, prompt, **_kwargs):
        question = prompt.startswith("What")
        return StudioDecision(interpretation=StudioIntent(operation="question" if question else "build"),
            route="ask_question" if question else "build_model", action="general_question" if question else "new_task", message="Accepted.")
    monkeypatch.setattr(GeoWorldBackendClient, "interpret_studio", route)
    monkeypatch.setattr(GeoWorldBackendClient, "preview_geospec", lambda _self, **kwargs:
        requests.append(kwargs) or {"valid": True, "geospec": {"geology": {"layers": [{"lithology": "sand"}]}}})
    monkeypatch.setattr(GeoWorldBackendClient, "submit_job", lambda *_:
        JobCreateResponse(job_id="f" * 32, status="queued", progress="queued"))
    monkeypatch.setattr(GeoWorldBackendClient, "get_job", lambda *_:
        JobStatusResponse(job_id="f" * 32, status="succeeded", progress="done", result=JobResult(intent="qa", reason="test", answer="Answer.")))
    app.run(timeout=20)
    send(app, "build sand")
    before = app.session_state["studio_task_context"].build.model_dump()
    send(app, "What is acoustic impedance?")
    assert app.session_state["studio_task_context"].build.model_dump() == before
    assert any(item.value == "Prepared model" for item in app.subheader)
    assert len(requests) == 1
    app.run(timeout=20)
    assert len(requests) == 1


def test_qa_provider_job_failure_keeps_active_data_and_reports_error_once(app, monkeypatch):
    _seismic_workspace_backend(monkeypatch)
    monkeypatch.setattr(GeoWorldBackendClient, "interpret_studio", lambda *_args, **_kwargs:
        StudioDecision(interpretation=StudioIntent(operation="question"), route="ask_question", action="general_question", message="Answer question."))
    monkeypatch.setattr(GeoWorldBackendClient, "submit_job", lambda *_:
        JobCreateResponse(job_id="b" * 32, status="queued", progress="queued"))
    monkeypatch.setattr(GeoWorldBackendClient, "get_job", lambda *_:
        JobStatusResponse(job_id="b" * 32, status="failed", progress="failed", error="Provider unavailable; retry later."))
    app.session_state["studio_active_context"] = "seismic"
    app.run(timeout=20)
    before = app.session_state["studio_task_context"].model_dump()
    send(app, "What is acoustic impedance?")
    after = app.session_state["studio_task_context"].model_dump()
    assert after["active_seismic_dataset_id"] == before["active_seismic_dataset_id"]
    assert after["seismic_view"] == before["seismic_view"]
    assert len(app.get("plotly_chart")) == 1
    history = list(app.session_state["assistant_history"])
    assert sum("Provider unavailable" in item["content"] for item in history) == 1
    app.run(timeout=20)
    assert app.session_state["assistant_history"] == history


def test_failed_question_job_preserves_previous_model_result(app, monkeypatch):
    from test_studio_request import completed
    completed(app)
    previous = app.session_state["last_job"]
    previous_id = app.session_state["last_job_id"]
    monkeypatch.setattr(GeoWorldBackendClient, "interpret_studio", lambda *_args, **_kwargs:
        StudioDecision(interpretation=StudioIntent(operation="question"), route="ask_question", message="Answer question."))
    monkeypatch.setattr(GeoWorldBackendClient, "submit_job", lambda *_:
        JobCreateResponse(job_id="c" * 32, status="queued", progress="queued"))
    monkeypatch.setattr(GeoWorldBackendClient, "get_job", lambda *_:
        JobStatusResponse(job_id="c" * 32, status="failed", progress="failed", error="Provider unavailable; retry later."))
    app.run(timeout=20)
    send(app, "What is acoustic impedance?")
    assert app.session_state["last_job_id"] == previous_id
    assert app.session_state["last_job"] == previous
    assert sum("Provider unavailable" in item["content"] for item in app.session_state["assistant_history"]) == 1
    app.run(timeout=20)
    assert app.session_state["last_job_id"] == previous_id


def test_typed_build_immediate_preview_edit_and_exact_run(app, monkeypatch):
    from copy import deepcopy
    spec = {'geology': {'layers': [{'lithology': 'shale'}, {'lithology': 'sand', 'porosity': .2}, {'lithology': 'carbonate', 'porosity': .3}, {'lithology': 'shale'}]}}
    previews, jobs = [], []
    def interpret(_self,prompt,**kwargs):
        if prompt=='run it':
            assert kwargs['context'].build.geospec['geology']['layers'][2]['porosity']==.25
            return StudioDecision(interpretation=StudioIntent(operation='build'), route='build_model',action='run_prepared_build',message='Run reviewed model.')
        changed=deepcopy(spec)
        if prompt.startswith('change'):
            changed['geology']['layers'][2]['porosity']=.25
        return StudioDecision(interpretation=StudioIntent(operation='build'),route='build_model',
            build_spec=changed,continues_build=prompt.startswith('change'), action='patch_build' if prompt.startswith('change') else 'new_task',message='Review.')
    def preview(_self,**kwargs):
        assert set(kwargs)=={'geospec'}
        payload=kwargs['geospec'];previews.append(deepcopy(payload))
        rows=[{'index':index,'lithology':layer['lithology'],'thickness_m':200.,'porosity':layer.get('porosity',.08),
               'vp':3000.,'vs':1500.,'density':2300.,'sources':{'lithology':'user','porosity':'user' if layer.get('porosity') else 'default','vp':'derived','vs':'derived','density':'derived','thickness_m':'default'}} for index,layer in enumerate(payload['geology']['layers'])]
        return {'valid':True,'geospec':payload,'assumptions':['Documented policy'], 'model_preview':{
            'layers':rows,'x_m':[0,100],'z_m':[0,200,400,600],'layer_indices':[[1,1],[2,2],[3,3],[4,4]],
            'co2_enabled':False,'fault_count':0,'note':'Prepared geometry; before Run.'}}
    monkeypatch.setattr(GeoWorldBackendClient,'interpret_studio',interpret)
    monkeypatch.setattr(GeoWorldBackendClient,'preview_geospec',preview)
    monkeypatch.setattr(GeoWorldBackendClient,'submit_job',lambda _self,request:jobs.append(request) or JobCreateResponse(job_id='a'*32,status='queued',progress='queued'))
    monkeypatch.setattr(GeoWorldBackendClient,'get_job',lambda *_:JobStatusResponse(job_id='a'*32,status='succeeded',progress='done',result=JobResult(intent='build_model',reason='test',answer='Built exact reviewed model.')))
    app.run(timeout=20)
    send(app,'Build a formation with shale, sand, carbonate, and shale layers. Sand has porosity of 0.2, and carbonate 0.3.')
    assert len(app.get('plotly_chart'))==1 and len(app.dataframe)==2
    assert not jobs
    send(app,'change carbonate porosity to 0.25')
    assert len(app.get('plotly_chart'))==1
    assert app.session_state['studio_task_context'].build.geospec['geology']['layers'][2]['porosity']==.25
    import hashlib,json
    current=app.session_state['studio_task_context'].build.geospec
    revision=hashlib.sha256(json.dumps(current,sort_keys=True).encode()).hexdigest()[:12]
    app.session_state['model_layer_editor_'+revision]={'edited_rows':{1:{'porosity':.22}},'added_rows':[],'deleted_rows':[]}
    button(app,'Apply layer edits').click().run(timeout=20)
    assert not app.exception
    assert app.session_state['studio_task_context'].build.geospec['geology']['layers'][1]['porosity']==.22
    send(app,'run it')
    assert len(jobs)==1 and jobs[0].geospec==previews[-1]
    app.run(timeout=20)
    assert len(jobs)==1 and len(previews)==3
