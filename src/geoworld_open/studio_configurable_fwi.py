"""HTTP-only scientific stepper for a prepared Marmousi crop and simple FWI."""
from __future__ import annotations

from io import BytesIO

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from geoworld_open.client import GeoWorldClientError
from geoworld_open.client.models import JobCreateRequest
from geoworld_open.studio_execution import render_preflight
from geoworld_open.studio_llm import execution_model_line


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


def metric_percent_change(initial: float, final: float) -> float:
    if initial <= 0:
        return 0.0
    return 100.0 * (initial - final) / initial


def gather_figure(gather, *, receiver_x_m, time_s, limit, title):
    figure = go.Figure(go.Heatmap(
        x=receiver_x_m, y=time_s, z=gather.T, zmin=-limit, zmax=limit,
        colorscale="Greys", colorbar=dict(title="Amplitude"),
    ))
    figure.update_layout(title=title, xaxis_title="Receiver x (m)", yaxis_title="Time (s)")
    figure.update_yaxes(autorange="reversed")
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
                if response.llm:
                    st.session_state["last_preparation_model"] = execution_model_line(
                        response.llm, purpose="Request interpretation"
                    )
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
            if updated.llm:
                st.session_state["last_preparation_model"] = execution_model_line(
                    updated.llm, purpose="Request interpretation"
                )
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
             f"{settings.time_samples} samples at {settings.sample_interval_s * 1000:g} ms "
             f"({settings.time_samples * settings.sample_interval_s:.3f} s); "
             f"Ricker peak {settings.ricker_peak_time_s:g} s; float32, accuracy {settings.accuracy}.")
    adequacy = preview.forward.recording_time_adequacy
    if adequacy:
        message = (f"Recording-time adequacy: {adequacy.adequacy} · record {adequacy.recording_time_s:.3f} s · "
                   f"conservative estimate {adequacy.estimated_required_time_s:.3f} s · "
                   f"margin {adequacy.margin_s:+.3f} s · origin {adequacy.origin}.")
        if adequacy.adequacy == "sufficient":
            st.success(message)
        elif adequacy.adequacy == "marginal":
            st.warning(message)
        else:
            st.error(message)
        st.caption(adequacy.rationale)
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
    st.markdown("#### 5 · Results")
    st.success(f"Forward complete · {custom.completed_updates} optimizer updates · "
               f"{custom.diagnostics['resolved_device'].upper()} · modified experiment")
    objective_initial = custom.initial_data_objective or custom.objective_history[0]
    objective_final = custom.final_data_objective or custom.objective_history[-1]
    objective_reduction = metric_percent_change(objective_initial, objective_final)
    st.metric("Receiver-data objective", f"{objective_final:.5g}",
              delta=f"{objective_reduction:.1f}% reduction")
    if custom.initial_velocity_rmse_mps is not None and custom.final_velocity_rmse_mps is not None:
        rmse_change = metric_percent_change(
            custom.initial_velocity_rmse_mps, custom.final_velocity_rmse_mps
        )
        label = "improvement" if rmse_change >= 0 else "worsening"
        st.metric("Velocity RMSE vs synthetic truth", f"{custom.final_velocity_rmse_mps:.2f} m/s",
                  delta=f"{abs(rmse_change):.1f}% {label}",
                  delta_color="normal" if rmse_change >= 0 else "inverse")
        st.caption(f"Initial RMSE {custom.initial_velocity_rmse_mps:.2f} m/s → "
                   f"final RMSE {custom.final_velocity_rmse_mps:.2f} m/s. "
                   "Synthetic true Vp is evaluation-only and was excluded from the inversion objective.")
    st.caption(f"Forward {custom.forward_runtime_seconds:.1f} s · FWI {custom.fwi_runtime_seconds:.1f} s · "
               f"peak RAM {custom.peak_ram_mib:.0f} MiB · peak allocated VRAM {custom.peak_vram_mib:.0f} MiB.")
    st.caption("Model, acquisition, settings and observed-data hashes are continuous from preview through forward and FWI.")
    st.caption("Snapshot updates: " + ", ".join(map(str, custom.snapshot_schedule)))
    try:
        with np.load(BytesIO(api.get_artifact(job_id, "configurable_fwi_arrays.npz")), allow_pickle=False) as data:
            observed, predicted, residual = (data[name].copy() for name in
                                             ("observed_shots", "predicted_shots", "residual_shots"))
            receiver_x_m = data["receiver_x_m"].copy()
            time_s = data["time_s"].copy()
        shot = st.selectbox("Representative shot", range(1, observed.shape[0] + 1),
                            index=observed.shape[0] // 2, key="configurable_fwi_result_shot") - 1
        common_limit = max(float(np.quantile(np.abs(np.stack([observed[shot], predicted[shot]])), .99)), 1e-12)
        independent_residual = st.checkbox(
            "Use independent residual display stretch",
            value=False,
            help="Display-only: does not alter saved arrays, hashes, objective, or inversion.",
        )
        residual_limit = (max(float(np.quantile(np.abs(residual[shot]), .99)), 1e-12)
                          if independent_residual else common_limit)
        for name, gather, limit in (
            ("Observed", observed[shot], common_limit),
            ("Predicted", predicted[shot], common_limit),
            ("Residual = predicted − observed", residual[shot], residual_limit),
        ):
            scale = "independent residual scale" if name.startswith("Residual") and independent_residual else "common observed/predicted scale"
            st.plotly_chart(gather_figure(
                gather, receiver_x_m=receiver_x_m, time_s=time_s, limit=limit,
                title=f"{name} shot {shot + 1} · {scale}",
            ), width="stretch")
    except (GeoWorldClientError, ValueError, KeyError) as exc:
        st.warning(f"Shot-gather selector unavailable; saved figures and raw artifacts remain available: {exc}")
