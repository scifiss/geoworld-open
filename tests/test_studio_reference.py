"""Public UI/HTTP tests, independent of private routing and numerical imports."""
from pathlib import Path
import json

import pytest

from geoworld_open.client.reference_experiment import ReferencePreview, ReferenceSelection
from geoworld_open.reference.deepwave_marmousi.definition import reference_definition, configuration_hash


def make_preview(action="run"):
    base = reference_definition()
    return ReferencePreview(selection=ReferenceSelection(action=action), classification="unchanged_reference",
        prepare_only=action == "prepare", requested_values={"action": action}, inherited_reference_values=base,
        proposed_modifications=[], unresolved_conflicts=[], suggestions=["Prepared only"] if action == "prepare" else [],
        resolved_configuration=base, configuration_sha256=configuration_hash(base), runnable=action == "run",
        interpretation_mode="structured_input", preparation_id="a" * 32)


def test_reference_http_contract_uses_authenticated_preview_only():
    from geoworld_open.client import GeoWorldBackendClient
    class Transport:
        calls = []
        def send(self, method, url, headers, body, timeout):
            self.calls.append((method, url, headers, json.loads(body)))
            return 200, make_preview().model_dump_json().encode()
    transport = Transport()
    api = GeoWorldBackendClient("http://localhost:8100", token="test-token", transport=transport)
    preview = api.preview_reference(prompt="Reproduce the official reference")
    assert preview.classification == "unchanged_reference"
    assert transport.calls[0][0:2] == ("POST", "http://localhost:8100/references/preview")
    assert transport.calls[0][2]["Authorization"] == "Bearer test-token"
    assert transport.calls[0][3]["selection"] is None


def test_reference_ui_invalidates_edits_and_prepare_only_cannot_run(monkeypatch):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest
    from geoworld_open.client import GeoWorldBackendClient
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("GEOWORLD_BACKEND_URL", "http://127.0.0.1:8100")
    monkeypatch.setenv("GEOWORLD_STUDIO_LOCAL_RTM", "1")
    monkeypatch.setattr(GeoWorldBackendClient, "get_llm_health", lambda _: {"reachable": False})
    calls = []
    def preview(self, **kwargs):
        calls.append(kwargs)
        return make_preview("prepare")
    monkeypatch.setattr(GeoWorldBackendClient, "preview_reference", preview)
    def forbidden(*args, **kwargs):
        pytest.fail("Reference UI must not use legacy routing or execute a prepare-only preview")
    monkeypatch.setattr(GeoWorldBackendClient, "preview_intent", forbidden)
    monkeypatch.setattr(GeoWorldBackendClient, "preview_geospec", forbidden)
    monkeypatch.setattr(GeoWorldBackendClient, "submit_job", forbidden)
    app = AppTest.from_file(str(root / "apps/studio_streamlit.py"))
    app.session_state["access_token"] = "test-token"
    app.session_state["manual_tools"] = True
    app.session_state["user_email"] = "reference@example.test"
    app.run(timeout=20)
    next(r for r in app.radio if r.label == "Workspace").set_value("Deepwave reference").run(timeout=20)
    next(b for b in app.button if b.label == "Interpret & validate reference").click().run(timeout=20)
    assert not app.exception and len(calls) == 1
    assert next(b for b in app.button if b.label == "Run verified reference").disabled
    assert any("no LLM call" in caption.value for caption in app.caption)
    app.text_area(key="reference_prompt").set_value("A changed reference request").run(timeout=20)
    assert not any(b.label == "Run verified reference" for b in app.button)


def test_reference_attribution_never_labels_numerics_as_llm():
    from geoworld_open.client.models import JobResult
    from geoworld_open.client.reference_experiment import ReferenceResult
    from geoworld_open.studio_llm import result_model_lines
    result = JobResult(intent="deepwave_reference", reason="test", answer="test", interpretation_mode="llm_reference_selection",
        reference=ReferenceResult(configuration_sha256="a"*64, runtime_seconds=1, comparison={"passed": True}, reports=[],
            interpretation_mode="llm_reference_selection", llm={"provider": "bedrock", "model": "test-only-model", "success": True}))
    lines = result_model_lines(result)
    assert "Amazon Bedrock" in lines[0]
    assert "Deepwave" in lines[1] and "not an LLM" in lines[1]
