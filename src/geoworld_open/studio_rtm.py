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


def model_preview_figure(model, field):
    import plotly.graph_objects as go
    values = getattr(model, field + "_zx")
    unit = model.units[field]
    figure = go.Figure(go.Heatmap(x=model.x_m, y=model.z_m, z=values, colorscale="Viridis",
        colorbar={"title": unit}, hovertemplate="x=%{x:.1f} m<br>depth=%{y:.1f} m<br>value=%{z:.1f}<extra></extra>"))
    label = {"vp": "Vp", "vs": "Vs", "density": "Density"}[field]
    figure.update_layout(height=390, margin={"l": 55, "r": 15, "t": 35, "b": 45},
        title=label + " · approved model preview", xaxis_title="x (m)", yaxis_title="Depth (m)")
    figure.update_xaxes(constrain="domain")
    figure.update_yaxes(autorange="reversed", scaleanchor="x", scaleratio=1, constrain="domain")
    return figure


def render_rtm_workspace(api, submit, *, prompt=None, auto_prepare=False, prepare_only=False, operation='rtm'):
    st.subheader("Model + RTM · experimental" if operation=='rtm' else 'Model + acoustic forward modelling')
    st.caption("Local CPU/CUDA demonstration. Genuine time-domain acoustic shots and one adjoint image; no elastic AVO or velocity inversion."
               if operation=='rtm' else 'Acoustic shots only. No migration or inversion is performed.')
    input_mode = "Natural language"
    if prompt is None:
        input_mode = st.radio("Experiment input", ["Natural language", "Structured input / debugging"], horizontal=True)
    default = "Build three layers: shale, high-porosity sand, shale, with one planar fault. Generate acoustic shots and an RTM image."
    if prompt is None:
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
    with st.expander('Advanced: execution preference'):
        device = st.selectbox("RTM execution device", ["auto", "cpu", "cuda"], key="rtm_device",
                          help="Runs on the backend computer. Auto selects CUDA after a resource check, otherwise CPU. Changing this requires preparation and approval again.")
    if input_mode != "Natural language":
        st.caption("This device selection overrides the device in pasted JSON; it does not change the model or numerical settings.")
    signature = (input_mode, prompt, structured.model_dump_json() if structured else None, device, operation)
    if st.session_state.get("rtm_input_signature") != signature:
        st.session_state.pop("rtm_preview", None)
        st.session_state.pop("rtm_model_approved", None)
        st.session_state["rtm_input_signature"] = signature
    if st.button("Prepare experiment", type="primary", disabled=not prompt.strip() or (input_mode != "Natural language" and structured is None)) or auto_prepare:
        st.session_state.pop("rtm_preview", None)
        st.session_state.pop("rtm_model_approved", None)
        try:
            with st.spinner("Interpreting and validating the bounded experiment…"):
                preview = api.preview_rtm(prompt=prompt if structured is None else None, experiment=structured, device=device,operation=operation)
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
        if preview.model_preview is not None:
            model = preview.model_preview
            st.markdown("#### Review the model before running")
            st.caption("Vp, Vs and density are deterministically derived from the interpreted lithology and porosity. Deepwave's constant-density acoustic solver uses Vp only; Vs and density are displayed context, not RTM inputs.")
            tabs = st.tabs(["Vp · solver input", "Vs · context", "Density · context"])
            for tab, field in zip(tabs, ["vp", "vs", "density"]):
                with tab:
                    low, high = model.ranges[field]
                    st.caption(f"Range: {low:g}–{high:g} {model.units[field]}")
                    st.plotly_chart(model_preview_figure(model, field), key="rtm_model_" + field, width="stretch")
            st.caption("Approved Vp identity: " + model.vp_sha256[:16] + "… The completed run is rejected if its rebuilt Vp does not match.")
        with st.expander("Prepared experiment / assumptions", expanded=True):
            st.write("Migration uses smoothed synthetic truth. This is an idealized model, not a recovered earth model."
                     if operation=='rtm' else 'Forward propagation uses the reviewed Vp. No migration model or RTM is calculated.')
            for assumption in preview.assumptions:
                st.caption(assumption)
        with st.expander("Resolved request"):
            st.code(experiment.model_dump_json(indent=2), language="json")
        if prepare_only or preview.prepare_only:
            st.info("Prepared only, as requested. Submit a new request to run it.")
        from geoworld_open.studio_execution import render_preflight
        feasible = render_preflight(preview.execution_plan)
        if preview.model_preview is None:
            st.warning("This backend did not return a reviewable model. Restart it with the current code before running.")
        approved = st.checkbox("I reviewed this model and want to use its Vp for acoustic forward modelling"+(' and RTM' if operation=='rtm' else ' only'), key="rtm_model_approved",
                               disabled=preview.model_preview is None)
        if st.button("Run approved model", disabled=prepare_only or preview.prepare_only or not approved or preview.model_preview is None or not feasible):
            try:
                submit(api, JobCreateRequest(prompt=prompt, mode_hint="model_rtm" if operation=='rtm' else 'model_forward', rtm_experiment=experiment,
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
    if evidence.method=='acoustic_forward':
        st.success(f'Acoustic forward shots · {evidence.runtime_seconds:.1f} s · peak worker RSS {evidence.peak_memory_mib:.0f} MiB')
        st.caption(f"Deepwave {d.get('deepwave')} · {d.get('resolved_device')} · {d.get('shots')} shots. No Born adjoint, RTM or inversion was run.")
        return
    st.success(f"Acoustic shots + Born-adjoint image · {evidence.runtime_seconds:.1f} s · peak worker RSS {evidence.peak_memory_mib:.0f} MiB")
    st.caption(f"Deepwave {d.get('deepwave', 'unknown')} · PyTorch {d.get('torch', 'unknown')} · "
               f"{d.get('device', 'unknown')} · {d.get('shots', '?')} shots · dt={d.get('dt_s', '?')} s · nt={d.get('nt', '?')}")
    st.caption("One adjoint image, not FWI or converged LSRTM. True and migration velocities share a color scale; image is globally normalized.")
    if "requested_device" in d:
        st.caption(f"Requested: {d['requested_device']} → used: {d.get('resolved_device')} · "
                   f"GPU: {d.get('gpu_model') or 'not used'} · CUDA: {d.get('cuda_version') or 'none'} · "
                   f"peak allocated VRAM: {d.get('peak_gpu_allocated_bytes', 0) / 1024**2:.1f} MiB")
        st.caption(d.get("device_resolution_reason", ""))
