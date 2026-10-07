"""Offline HTTP fixture: production Studio and a completed scientific image artifact."""
from copy import deepcopy
from pathlib import Path
import runpy

import streamlit as st

from geoworld_open.client import GeoWorldBackendClient, GeoWorldClientError
from geoworld_open.client.models import ArtifactInfo, JobCreateResponse, JobResult, JobStatusResponse
from geoworld_open.client.semantic_action import NewBuild, PatchBuild, RequestedLayer, LayerEdit
from geoworld_open.client.studio_request import StudioDecision, StudioIntent


REQUEST = "build shale sand carbonate, co2 in sand carbonate very porous"
FIGURE = Path(__file__).parents[2] / "docs/assets/geoworld-three-layer-co2.png"
SPEC = {"schema_version": "2.0", "grid": {"dimension": "2d", "nx": 300, "nz": 160},
        "geology": {"layers": [{"lithology": "shale", "porosity": None},
                               {"lithology": "sand", "porosity": None},
                               {"lithology": "carbonate", "porosity": .28}]},
        "petrophysics": {"co2_plume": {"enabled": True, "saturation": .65}}}

st.session_state.setdefault("access_token", "offline-fixture-token")
st.session_state.setdefault("user_email", "fixture@example.test")


def interpret(_self, prompt, **context):
    existing = context["context"].build
    if existing:
        spec = deepcopy(existing.geospec)
        spec["geology"]["layers"][2]["porosity"] = .25
        action = PatchBuild(edits=[LayerEdit(operation="porosity", layer_index=2, value=.25)])
    else:
        spec = deepcopy(SPEC)
        action = NewBuild(layers=[RequestedLayer(lithology="shale"),
            RequestedLayer(lithology="sand"),
            RequestedLayer(lithology="carbonate", porosity_policy="high")], co2_host_index=1)
    return StudioDecision(interpretation=StudioIntent(operation="build", dataset="synthetic"),
        route="build_model", action="patch_build" if existing else "new_task",
        semantic_action=action, build_spec=spec, continues_build=bool(existing),
        message="Validated synthetic model.")


def preview(_self, **request):
    spec = request["geospec"]
    return {"valid": True, "geospec": spec, "assumptions": ["Offline fixture; real image artifact."],
            "model_preview": None}


def submit(_self, request):
    serial = st.session_state.get("fixture_submissions", 0) + 1
    st.session_state["fixture_submissions"] = serial
    st.session_state["fixture_spec"] = request.geospec
    return JobCreateResponse(job_id=f"{serial:032x}", status="queued", progress="queued")


def get_job(_self, job_id):
    return JobStatusResponse(job_id=job_id, status="succeeded", progress="done", result=JobResult(
        intent="scenario_generation", reason="offline fixture", answer="Scientific output ready.",
        geospec=st.session_state["fixture_spec"],
        artifacts=[ArtifactInfo(name="model_runs/summary.png", kind="image", media_type="image/png")],
    ))


GeoWorldBackendClient.interpret_studio = interpret
GeoWorldBackendClient.preview_geospec = preview
GeoWorldBackendClient.submit_job = submit
GeoWorldBackendClient.get_job = get_job
GeoWorldBackendClient.get_artifact = lambda *_: FIGURE.read_bytes()
GeoWorldBackendClient.get_export = lambda *_: (_ for _ in ()).throw(GeoWorldClientError("Offline fixture"))
GeoWorldBackendClient.get_llm_health = lambda *_: {"reachable": True, "details": {}}

runpy.run_path(str(Path(__file__).parents[2] / "apps/studio_streamlit.py"), run_name="__main__")
st.caption("Fixture submissions: " + str(st.session_state.get("fixture_submissions", 0)))
