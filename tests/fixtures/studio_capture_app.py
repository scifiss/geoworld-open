"""Offline browser fixture running the real Studio app with a fake HTTP client.

Only a public reference image is used. Never connect this fixture to a real account.
"""
from pathlib import Path
import runpy

import streamlit as st

from geoworld_open.client import GeoWorldBackendClient, GeoWorldClientError
from geoworld_open.client.models import JobResult, JobStatusResponse
from geoworld_open.studio_llm import preparation_model_line


ROOT = Path(__file__).resolve().parents[2]
PROMPT = "Build shale, high-porosity sand, and shale. Add one dipping fault.\nGenerate Vp, Vs, density, impedance, reflectivity, synthetic seismic. List assumptions."

if "capture_fixture_initialized" not in st.session_state:
    st.session_state.update({
        "capture_fixture_initialized": True,
        "access_token": "test-token", "user_email": "private-account@example.test",
        "active_workspace": "Ask or Build", "last_job_id": "job-capture",
        "last_submitted_prompt": PROMPT, "prompt": PROMPT, "runtime_prompt": PROMPT,
        "runtime_intent_label": "Auto",
        "detected_intent": {
            "intent": "build_model", "label": "Build model",
            "reason": "The request asks GeoWorld to build or simulate a supported geoscience model.",
        },
        "prepared_geospec": {"task": "build_model", "layers": [{"lithology": "shale"}, {"lithology": "sand"}]},
        "prepared_preview": {
            "interpretation_mode": "llm_semantic_parser", "valid": True,
            "llm": {"provider": "openai", "model": "gpt-4.1-mini", "success": True,
                    "fallback_reason": "synthetic test failover"},
        },
        "last_job": JobStatusResponse(
            job_id="job-capture", status="succeeded", progress="complete",
            result=JobResult(
                intent="build_model", reason="Offline fixture", answer="Offline display test — no model has been run.",
                layers=[{"name": "Synthetic sand", "thickness_m": 100}],
                storage={"note": "Synthetic test summary; not field evidence.", "mean_porosity": 0.2},
                artifacts=[
                    {"name": f"summary_{index}.png", "kind": "image", "media_type": "image/png"}
                    for index in range(3 if st.query_params.get("capture_figures") == "3" else 1)
                ],
            ),
        ),
    })
    st.session_state["last_preparation_model"] = preparation_model_line(st.session_state["prepared_preview"])
st.session_state["fixture_run_count"] = st.session_state.get("fixture_run_count", 0) + 1
st.html(f'<span id="fixture-run-count" style="display:none">{st.session_state["fixture_run_count"]}</span>')


def no_export(*_args):
    raise GeoWorldClientError("Full archive is not part of this offline fixture.")


def no_submission(*_args, **_kwargs):
    raise AssertionError("A screenshot must not submit a scientific job.")


GeoWorldBackendClient.get_llm_health = lambda _self: {
    "reachable": True, "details": {
        "primary": {"provider": "bedrock", "model": "us.amazon.nova-2-lite-v1:0"},
        "fallback": {"provider": "openai", "model": "gpt-4.1-mini"},
    },
}
GeoWorldBackendClient.get_artifact = lambda *_args: (ROOT / "docs/assets/flagship_world_demo.png").read_bytes()
GeoWorldBackendClient.get_export = no_export
GeoWorldBackendClient.submit_job = no_submission
runpy.run_path(str(ROOT / "apps/studio_streamlit.py"), run_name="__main__")
