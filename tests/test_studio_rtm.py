"""Portable contract and Studio control regressions; no numerical/private imports."""
from pathlib import Path
import pytest
from geoworld_open.client.rtm import RTMExperiment, RTMModelPreview, RTMPreview
from geoworld_open.client.models import JobCreateRequest, JobResult


def experiment():
    return RTMExperiment(geospec={"grid": {"nz": 64, "nx": 96, "dx_m": 10, "dz_m": 10},
        "geology": {"layers": [{"lithology": "shale"}, {"lithology": "sand"}], "faults": []}})


def model_preview():
    nz, nx = 64, 96
    grid = lambda value: [[value] * nx for _ in range(nz)]
    return RTMModelPreview(shape_zx=[nz, nx], x_m=[5 + 10*x for x in range(nx)], z_m=[5 + 10*z for z in range(nz)],
        vp_zx=grid(2500), vs_zx=grid(1400), density_zx=grid(2200),
        units={"vp": "m/s", "vs": "m/s", "density": "kg/m³"},
        ranges={"vp": [2500, 2500], "vs": [1400, 1400], "density": [2200, 2200]}, vp_sha256="a" * 64)


def test_portable_roundtrip_and_no_heavy_dependency():
    request = JobCreateRequest(prompt="An acoustic model", mode_hint="model_rtm", rtm_experiment=experiment())
    assert JobCreateRequest.model_validate_json(request.model_dump_json()) == request
    root = Path(__file__).resolve().parents[1]
    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10
        import tomli as tomllib
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    assert not any("torch" in d or "deepwave" in d for d in project["dependencies"])


def test_model_preview_contract_rejects_misalignment_and_non_vp_solver():
    payload = model_preview().model_dump(mode="json")
    payload["density_zx"][0].pop()
    with pytest.raises(ValueError, match="match shape"):
        RTMModelPreview.model_validate(payload)
    payload = model_preview().model_dump(mode="json")
    payload["solver_fields"] = ["vp", "vs"]
    with pytest.raises(ValueError):
        RTMModelPreview.model_validate(payload)


@pytest.mark.parametrize("payload", [{"shots": 5}, {"nt": 10000}, {"coordinate_order": "x,z"}, {"distance_unit": "ft"}, {"frequency_hz": float("nan")}])
def test_invalid_acquisition(payload):
    with pytest.raises(ValueError):
        RTMExperiment(geospec={}, acquisition=payload)


def test_local_ui_cannot_enable_for_render(monkeypatch):
    pytest.importorskip("streamlit")
    from geoworld_open.studio_rtm import local_rtm_ui_enabled
    monkeypatch.setenv("GEOWORLD_STUDIO_LOCAL_RTM", "1")
    assert local_rtm_ui_enabled("http://127.0.0.1:8100")
    assert not local_rtm_ui_enabled("https://geoworld-he94.onrender.com")
    assert not local_rtm_ui_enabled("http://127.0.0.1.evil.test")


def test_rtm_model_attribution():
    from geoworld_open.studio_llm import result_model_lines
    r = JobResult(intent="model_rtm", reason="test", answer="test", interpretation_mode="structured_input")
    lines = result_model_lines(r)
    assert any("no LLM call" in line for line in lines)
    assert any("Deepwave" in line for line in lines)
    r.interpretation_mode = "llm_rtm_interpretation"
    lines = result_model_lines(r, trace={"capability_uses": [{"capability_name": "rtm_interpretation",
        "diagnostics": {"llm": {"provider": "bedrock", "model": "test-model", "success": True}}}]})
    assert any("Amazon Bedrock" in line for line in lines)


def test_studio_prepare_invalidates_on_edits_and_does_not_legacy_route(monkeypatch):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest
    from geoworld_open.client import GeoWorldBackendClient
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("GEOWORLD_BACKEND_URL", "http://127.0.0.1:8100")
    monkeypatch.setenv("GEOWORLD_STUDIO_LOCAL_RTM", "1")
    monkeypatch.setattr(GeoWorldBackendClient, "get_llm_health", lambda _: {"reachable": True})
    calls = []
    def preview(self, **kwargs):
        calls.append(kwargs)
        return RTMPreview(experiment=experiment(), interpretation_mode="structured_input", assumptions=["Synthetic only"],
                          preparation_id="b" * 32, model_preview=model_preview())
    monkeypatch.setattr(GeoWorldBackendClient, "preview_rtm", preview)
    def forbidden(*args, **kwargs):
        pytest.fail("RTM UI must not call legacy intent/GeoSpec preview")
    monkeypatch.setattr(GeoWorldBackendClient, "preview_intent", forbidden)
    monkeypatch.setattr(GeoWorldBackendClient, "preview_geospec", forbidden)
    at = AppTest.from_file(str(root / "apps/studio_streamlit.py"))
    at.session_state["access_token"] = "local-test-only"
    at.session_state["manual_tools"] = True
    at.session_state["user_email"] = "local@example.test"
    at.run(timeout=20)
    next(r for r in at.radio if r.label == "Workspace").set_value("Model + RTM").run(timeout=20)
    next(b for b in at.button if b.label == "Prepare experiment").click().run(timeout=20)
    assert not at.exception and len(calls) == 1
    assert calls[-1]["device"] == "auto"
    run = next(b for b in at.button if b.label == "Run approved model")
    assert run.disabled
    assert {tab.label for tab in at.tabs} >= {"Vp · solver input", "Vs · context", "Density · context"}
    next(c for c in at.checkbox if c.label.startswith("I reviewed this model")).check().run(timeout=20)
    assert not next(b for b in at.button if b.label == "Run approved model").disabled
    at.selectbox(key="rtm_device").set_value("cuda").run()
    assert not any(b.label == "Run approved model" for b in at.button)
    next(b for b in at.button if b.label == "Prepare experiment").click().run(timeout=20)
    assert calls[-1]["device"] == "cuda"
    assert next(b for b in at.button if b.label == "Run approved model").disabled
    at.text_area(key="rtm_prompt").set_value("A changed request").run()
    assert not any(b.label == "Run approved model" for b in at.button)
