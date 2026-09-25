"""HTTP-only scientific stepper for a prepared Marmousi crop and simple FWI."""
from __future__ import annotations

from io import BytesIO

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from geoworld_open.client import GeoWorldClientError
from geoworld_open.client.models import JobCreateRequest
from geoworld_open.studio_execution import render_preflight


def _preview_figure(preview):
    model = preview.forward.model_preview
    geometry = preview.forward.resolved_acquisition
    figure = go.Figure()
    figure.add_trace(go.Heatmap(
        x=model.x_m, y=model.z_m, z=model.values_zx,
        colorscale="Viridis", colorbar=dict(title="Vp (m/s)"), name="Vp crop",
    ))
    figure.add_trace(go.Scatter(
        x=[point[0] for point in geometry.receiver_coordinates_xz_m],
        y=[point[1] for point in geometry.receiver_coordinates_xz_m],
        mode="markers", name="Receivers", marker=dict(color="white", size=5),
    ))
    figure.add_trace(go.Scatter(
        x=[point[0] for point in geometry.source_coordinates_xz_m],
        y=[point[1] for point in geometry.source_coordinates_xz_m],
        mode="markers", name="Shots", marker=dict(color="red", size=8, symbol="star"),
    ))
    figure.update_layout(title="INPUT: resolved Marmousi 1 Vp crop and acquisition",
                         xaxis_title="x (m)", yaxis_title="Depth (m)")
    figure.update_yaxes(autorange="reversed", scaleanchor="x")
    return figure


def render_workspace(api, submit, *, prompt, auto_prepare=False, prepare_only=False):
    st.subheader("Marmousi 1 · configurable forward → simple acoustic FWI")
    st.caption("Modified benchmark experiment. Forward observations are generated before inversion; this is not the official Deepwave FWI reference.")
    if st.session_state.get("configurable_fwi_prompt") != prompt:
        st.session_state.pop("configurable_fwi_conversation", None)
        st.session_state.pop("configurable_fwi_preview", None)
        st.session_state["configurable_fwi_prompt"] = prompt
    if auto_prepare or st.button("Interpret & preview experiment"):
        try:
            with st.spinner("Understanding the request and resolving the crop; no solver is running…"):
                response = api.continue_experiment(prompt)
                st.session_state["configurable_fwi_conversation"] = response
                st.session_state.pop("configurable_fwi_preview", None)
                if response.state.status in {"ready", "prepare_only"}:
                    st.session_state["configurable_fwi_preview"] = api.preview_configurable_fwi(
                        response.state.active_experiment,
                    )
        except GeoWorldClientError as exc:
            st.error(str(exc))
    response = st.session_state.get("configurable_fwi_conversation")
    if response is None:
        return
    state = response.state
    st.markdown("#### 1 · Understand")
    if state.issues:
        for issue in state.issues:
            st.warning(issue)
        return
    draft = state.active_experiment
    with st.container(border=True):
        st.write(f"Dataset: Marmousi 1 · crop x={draft.model.x_start_m:g}–{draft.model.x_stop_m:g} m, "
                 f"z={draft.model.z_start_m:g}–{draft.model.z_stop_m:g} m")
        st.write(f"Acquisition: {draft.acquisition.shots} shots × {draft.acquisition.receivers} receivers · "
                 f"source/receiver depth {draft.acquisition.source_depth_m:g}/{draft.acquisition.receiver_depth_m:g} m")
        st.write(f"Simple acoustic Vp FWI: {draft.inversion.updates} optimizer updates · "
                 f"outputs: {', '.join(name for name, enabled in draft.requested_outputs.model_dump().items() if enabled)}")
        st.caption("Scientific classification: modified experiment. Deepwave computes the wavefields; AI only interprets the request.")
    with st.expander("Advanced: typed conversation and verified user fields"):
        st.json(draft.model_dump(mode="json"))
        for turn in state.visible_history:
            st.caption(turn.user_text + " → " + turn.assistant_summary)
    follow_up = st.text_input("Refine this experiment", key="configurable_fwi_follow_up",
                              placeholder="Make it 30 shots; also show the residual; use 75 updates; run it")
    if st.button("Apply follow-up", disabled=not follow_up.strip()):
        try:
            updated = api.continue_experiment(follow_up, conversation_id=state.conversation_id)
            st.session_state["configurable_fwi_conversation"] = updated
            st.session_state.pop("configurable_fwi_preview", None)
            if updated.state.status in {"ready", "prepare_only"}:
                st.session_state["configurable_fwi_preview"] = api.preview_configurable_fwi(
                    updated.state.active_experiment,
                )
            st.rerun()
        except GeoWorldClientError as exc:
            st.error(str(exc))
    preview = st.session_state.get("configurable_fwi_preview")
    if preview is None:
        return
    st.markdown("#### 2 · Preview experiment")
    st.plotly_chart(_preview_figure(preview), width="stretch")
    model = preview.forward.model_preview
    values = np.asarray(model.values_zx)
    st.caption(f"Resolved crop: {model.shape_xz[0]} × {model.shape_xz[1]} cells, {model.spacing_m:g} m grid. "
               f"Display Vp range {values.min():.0f}–{values.max():.0f} m/s; "
               f"mean {values.mean():.0f} m/s. Full-resolution solver input SHA-256: {preview.forward.crop_vp_sha256}.")
    st.caption(f"Geometry SHA-256: {preview.forward.geometry_sha256}. "
               f"Source x: {preview.forward.resolved_acquisition.source_coordinates_xz_m[0][0]:g}–"
               f"{preview.forward.resolved_acquisition.source_coordinates_xz_m[-1][0]:g} m; "
               f"receiver x: {preview.forward.resolved_acquisition.receiver_coordinates_xz_m[0][0]:g}–"
               f"{preview.forward.resolved_acquisition.receiver_coordinates_xz_m[-1][0]:g} m.")
    settings = preview.forward.experiment.settings
    st.write(f"Resolved wavelet/record: {settings.source_frequency_hz:g} Hz Ricker, "
             f"{settings.time_samples} samples at {settings.sample_interval_s * 1000:g} ms; "
             f"Ricker peak {settings.ricker_peak_time_s:g} s; float32, accuracy {settings.accuracy}.")
    with st.expander("Advanced: setting origins and exact scientific identities"):
        st.json(settings.model_dump(mode="json"))
        st.write("Acoustic settings SHA-256: " + preview.forward.settings_sha256)
        for assumption in preview.assumptions:
            st.caption(assumption)
    st.markdown("#### GeoWorld recommends")
    forward_estimate = preview.forward.execution_plan.estimate.runtime_seconds
    fwi_estimate = preview.execution_plan.estimate.runtime_seconds
    st.caption(f"Combined pre-run range: {(forward_estimate[0] + fwi_estimate[0]) / 60:.1f}–"
               f"{(forward_estimate[1] + fwi_estimate[1]) / 60:.1f} min; confidence low. "
               "Forward and FWI have separately measured live ETAs after Run.")
    feasible = render_preflight(preview.execution_plan) and preview.forward.execution_plan.feasible
    with st.expander("Advanced: forward plan and resource reserves"):
        st.json(preview.forward.execution_plan.model_dump(mode="json"))
    st.markdown("#### 3 · Forward modelling → 4 · FWI → 5 · Results")
    st.caption(f"Forward: {draft.acquisition.shots} shot gathers. FWI: {draft.inversion.updates} completed optimizer updates. "
               f"Display snapshots at {', '.join(map(str, preview.snapshot_schedule))} updates; no per-iteration image flood.")
    if prepare_only or draft.status == "prepare_only":
        st.info("Prepared only. Ask to run in a follow-up; preview cannot launch wave propagation.")
    same_submitted = (st.session_state.get("last_submitted_mode_hint") == "configurable_marmousi_fwi"
                      and st.session_state.get("last_submitted_prompt") == prompt
                      and st.session_state.get("last_job_id"))
    if same_submitted:
        st.info("This experiment is already submitted. The measured-progress panel and saved result remain available.")
    if st.button("Run forward → simple FWI", disabled=not preview.runnable or not feasible or prepare_only or bool(same_submitted)):
        submit(api, JobCreateRequest(prompt=prompt, mode_hint="configurable_marmousi_fwi",
                                     configurable_fwi_experiment=draft,
                                     configurable_fwi_preparation_id=preview.preparation_id))


def render_result(api, job_id, result):
    custom = result.configurable_fwi
    st.success(f"Forward complete · {custom.completed_updates} FWI updates · "
               f"{custom.diagnostics['resolved_device'].upper()} · modified experiment")
    st.write(f"Receiver-data objective before updates: {custom.objective_history[0]:.5g} → "
             f"{custom.objective_history[-1]:.5g}. Lower loss alone is not proof of geological recovery.")
    st.caption(f"Forward {custom.forward_runtime_seconds:.1f} s · FWI {custom.fwi_runtime_seconds:.1f} s · "
               f"peak RAM {custom.peak_ram_mib:.0f} MiB · peak allocated VRAM {custom.peak_vram_mib:.0f} MiB.")
    st.caption("Model, acquisition, settings and observed-data hashes are continuous from preview through forward and FWI.")
    st.caption("Snapshot updates: " + ", ".join(map(str, custom.snapshot_schedule)))
    try:
        with np.load(BytesIO(api.get_artifact(job_id, "configurable_fwi_arrays.npz")), allow_pickle=False) as data:
            observed, predicted, residual = (data[name].copy() for name in
                                             ("observed_shots", "predicted_shots", "residual_shots"))
        shot = st.selectbox("Representative shot", range(1, observed.shape[0] + 1),
                            index=observed.shape[0] // 2, key="configurable_fwi_result_shot") - 1
        limit = max(float(np.quantile(np.abs(np.stack([observed[shot], predicted[shot], residual[shot]])), .99)), 1e-12)
        for name, gather in (("Observed", observed[shot]), ("Predicted", predicted[shot]),
                             ("Residual = predicted − observed", residual[shot])):
            figure = go.Figure(go.Heatmap(z=gather.T, zmin=-limit, zmax=limit,
                                          colorscale="Greys", colorbar=dict(title="Amplitude")))
            figure.update_layout(title=f"{name} shot {shot + 1} · common display scale",
                                 xaxis_title="Receiver index", yaxis_title="Time sample")
            figure.update_yaxes(autorange="reversed")
            st.plotly_chart(figure, width="stretch")
    except (GeoWorldClientError, ValueError, KeyError) as exc:
        st.warning(f"Shot-gather selector unavailable; saved figures and raw artifacts remain available: {exc}")
