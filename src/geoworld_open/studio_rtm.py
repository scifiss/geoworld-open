"""Lightweight local RTM UI; all interpretation and numerical work uses authenticated HTTP."""
from __future__ import annotations

import json
import os
import re
from urllib.parse import urlparse

import streamlit as st

from geoworld_open.client.models import JobCreateRequest
from geoworld_open.client.rtm import RTMExperiment
from geoworld_open.client import GeoWorldClientError
from geoworld_open.studio_llm import execution_model_line


def local_rtm_ui_enabled(url):
    return (os.environ.get("GEOWORLD_STUDIO_LOCAL_RTM") == "1"
            and urlparse(url or "").hostname in {"localhost", "127.0.0.1", "::1"})


def render_rtm_workspace(api, submit):
    st.subheader("Model + RTM · experimental")
    st.caption("Local CPU demonstration. Genuine time-domain acoustic shots and one adjoint image; no elastic AVO or velocity inversion.")
    input_mode = st.radio("Experiment input", ["Natural language", "Structured input / debugging"], horizontal=True)
    default = "Build three layers: shale, high-porosity sand, shale, with one planar fault. Generate acoustic shots and an RTM image."
    prompt = st.text_area("Describe the acoustic experiment", value=default, key="rtm_prompt", height=130)
    structured = None
    if input_mode != "Natural language":
        st.info("Structured input does not call an LLM. It is not evidence of live natural-language interpretation.")
        raw = st.text_area("Existing experiment JSON", value="", key="rtm_structured", height=160,
                           help="Paste resolved_experiment.json from a prior run or the private demo command.")
        try:
            structured = RTMExperiment.model_validate_json(raw) if raw.strip() else None
        except ValueError:
            st.warning("The experiment JSON is not valid yet.")
    signature = (input_mode, prompt, structured.model_dump_json() if structured else None)
    if st.session_state.get("rtm_input_signature") != signature:
        st.session_state.pop("rtm_preview", None)
        st.session_state["rtm_input_signature"] = signature
    if st.button("Prepare experiment", type="primary", disabled=not prompt.strip() or (input_mode != "Natural language" and structured is None)):
        st.session_state.pop("rtm_preview", None)
        try:
            with st.spinner("Interpreting and validating the bounded experiment…"):
                preview = api.preview_rtm(prompt=prompt if structured is None else None, experiment=structured)
            st.session_state["rtm_preview"] = preview
        except GeoWorldClientError as exc:
            st.error(str(exc))
    preview = st.session_state.get("rtm_preview")
    if preview is not None:
        experiment = preview.experiment
        grid, geology = experiment.geospec["grid"], experiment.geospec["geology"]
        st.write(f"**{grid['nz']} × {grid['nx']} cells** · {grid['dx_m']:g} m spacing · "
                 f"{experiment.acquisition.shots} shot(s) · {experiment.acquisition.frequency_hz:g} Hz")
        st.write("Layers: " + " → ".join(str(l['lithology']) for l in geology['layers'])
                 + f" · {len(geology.get('faults', []))} fault(s)")
        st.caption(execution_model_line(preview.llm, purpose="Experiment interpretation") if preview.llm
                   else "Experiment interpretation: structured input; no LLM call.")
        with st.expander("Prepared experiment / assumptions", expanded=True):
            st.write("Migration uses smoothed synthetic truth. This is an idealized model, not a recovered earth model.")
            for assumption in preview.assumptions:
                st.caption(assumption)
        with st.expander("Resolved request"):
            st.code(experiment.model_dump_json(indent=2), language="json")
        if st.button("Run experiment"):
            try:
                submit(api, JobCreateRequest(prompt=prompt, mode_hint="model_rtm", rtm_experiment=experiment,
                                            rtm_preparation_id=preview.preparation_id))
            except GeoWorldClientError as exc:
                st.error(str(exc))
    with st.expander("Replay a recorded run"):
        recorded_id = st.text_input("Recorded job ID", key="rtm_replay_id")
        if st.button("Load recorded run", disabled=not re.fullmatch(r"[0-9a-f]{32}", recorded_id)):
            try:
                job = api.get_job(recorded_id)
                if job.status != "succeeded" or not job.result or job.result.intent != "model_rtm":
                    st.warning("Choose a completed Model + RTM run owned by your account.")
                else:
                    st.session_state["last_job"] = job
                    st.session_state["last_job_id"] = recorded_id
                    st.session_state["rtm_replay"] = True
                    for key in ("last_result_models", "last_preparation_model", "last_correlation_id", "clean_report"):
                        st.session_state.pop(key, None)
                    original = json.loads(api.get_artifact(recorded_id, "request.json"))
                    st.session_state["last_submitted_prompt"] = original["prompt"]
            except (GeoWorldClientError, ValueError, KeyError) as exc:
                st.error(str(exc))


def render_rtm_summary(result, replay=False):
    if replay:
        st.warning("Replay of recorded run — no new simulation or LLM call.")
    evidence = result.rtm
    if evidence is None:
        return
    d = evidence.diagnostics
    st.success(f"Acoustic shots + Born-adjoint image · {evidence.runtime_seconds:.1f} s · peak worker RSS {evidence.peak_memory_mib:.0f} MiB")
    st.caption(f"Deepwave {d.get('deepwave', 'unknown')} · PyTorch {d.get('torch', 'unknown')} · "
               f"{d.get('device', 'unknown')} · {d.get('shots', '?')} shots · dt={d.get('dt_s', '?')} s · nt={d.get('nt', '?')}")
    st.caption("One adjoint image, not FWI or converged LSRTM. True and migration velocities share a color scale; image is globally normalized.")
