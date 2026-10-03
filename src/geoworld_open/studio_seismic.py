"""Public HTTP-only Seismic Explorer presentation."""
from __future__ import annotations

import numpy as np
import streamlit as st

from geoworld_open.client.backend import GeoWorldClientError
from geoworld_open.client.horizon import HorizonTrackRequest
from geoworld_open.client.seismic import SeismicViewRequest


def _figure(view, clip_percentile: float):
    import plotly.graph_objects as go

    values = np.asarray(view.values, dtype=float)
    if values.ndim == 1 or view.request.view_kind == "trace":
        axis = view.vertical_coordinates or list(range(values.size))
        figure = go.Figure(go.Scatter(x=values.ravel(), y=axis, mode="lines"))
        figure.update_yaxes(
            autorange="reversed" if view.vertical_unit in {"s", "m"} else True,
            title=f"{view.vertical_label} ({view.vertical_unit})",
        )
        figure.update_xaxes(title="Amplitude")
    else:
        limit = float(np.percentile(np.abs(values), clip_percentile)) if values.size else 1.
        limit = limit or 1.
        figure = go.Figure(go.Heatmap(
            z=values, x=view.horizontal_coordinates, y=view.vertical_coordinates,
            colorscale="Greys", zmin=-limit, zmax=limit, colorbar_title="Amplitude",
        ))
        figure.update_yaxes(
            autorange="reversed" if view.vertical_unit in {"s", "m"} else True,
            title=f"{view.vertical_label} ({view.vertical_unit})",
        )
        figure.update_xaxes(title=f"{view.horizontal_label} ({view.horizontal_unit})")
    figure.update_layout(title=view.title, height=560, margin=dict(l=50, r=20, t=55, b=50))
    return figure


def _render_analysis(result) -> None:
    if result is None:
        return
    st.subheader("Analysis")
    st.write(result.summary)
    if result.statistics:
        columns = st.columns(min(4, len(result.statistics)))
        for column, (name, value) in zip(columns, result.statistics.items()):
            column.metric(name.replace("_", " ").title(), f"{value:.5g}")
    if result.x and result.y:
        import plotly.graph_objects as go
        figure = go.Figure(go.Scatter(x=result.x, y=result.y, name="Selected trace"))
        if result.secondary_y:
            figure.add_trace(go.Scatter(x=result.x, y=result.secondary_y, name="Comparison trace"))
        figure.update_layout(height=300, margin=dict(l=40, r=20, t=30, b=40))
        st.plotly_chart(figure, width="stretch")


def _horizon_figure(view, result, clip):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    figure = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[.8, .2],
                          vertical_spacing=.08)
    figure.add_trace(_figure(view, clip).data[0], row=1, col=1)
    x = result.horizontal_coordinates
    figure.add_trace(go.Scatter(x=x, y=result.truth_time_s, name="Synthetic truth",
                               line=dict(color="cyan", width=2)), row=1, col=1)
    figure.add_trace(go.Scatter(x=x, y=result.picked_time_s, name="Seeded pick",
                               mode="lines+markers", connectgaps=False,
                               line=dict(color="orangered")), row=1, col=1)
    figure.add_trace(go.Scatter(x=[x[result.request.seed_trace]], y=[result.request.seed_time_s],
                               name="User seed", mode="markers",
                               marker=dict(symbol="star", size=14, color="gold")), row=1, col=1)
    figure.add_trace(go.Scatter(x=x, y=result.errors_ms, name="Error (ms)",
                               mode="lines+markers", connectgaps=False), row=2, col=1)
    missing = [coordinate for coordinate, pick in zip(x, result.picked_time_s) if pick is None]
    figure.add_trace(go.Scatter(x=missing, y=[0] * len(missing), name="No pick",
                               mode="markers", marker=dict(symbol="x", color="black")), row=2, col=1)
    figure.add_hrect(y0=result.request.window_start_s, y1=result.request.window_stop_s,
                    fillcolor="gold", opacity=.1, line_width=0, row=1, col=1)
    figure.update_yaxes(autorange="reversed", title="Time (s)", row=1, col=1)
    figure.update_yaxes(title="Error (ms)", row=2, col=1)
    figure.update_xaxes(title=view.horizontal_label, row=2, col=1)
    figure.update_layout(height=700, title=f"Synthetic horizon V0 · {result.status}")
    return figure


def _render_horizon_controls(api, view):
    st.subheader("Synthetic horizon tracking V0")
    st.caption("Select a starting trace and waveform extremum, and a bounded time window. "
               "The deterministic baseline stops at weak matches or excessive jumps. "
               "This is a synthetic reference evaluation, not automatic interpretation.")
    identity = view.dataset.dataset_id
    section_number = view.request.inline if view.request.view_kind == "inline" else view.request.crossline
    prefix = f"horizon_{identity}_{view.request.view_kind}_{section_number}"
    seed_trace = st.number_input("Starting trace column (zero-based)", min_value=0,
                                 max_value=view.shape[1] - 1, value=None, step=1,
                                 key=f"{prefix}_trace")
    seed_time = st.number_input("Starting time (s)", min_value=0., max_value=1.02,
                                value=None, step=.004, format="%.3f", key=f"{prefix}_time")
    start = st.number_input("Tracking window start (s)", min_value=.020, max_value=.996,
                           value=.30, step=.004, format="%.3f", key=f"{prefix}_start")
    stop = st.number_input("Tracking window stop (s)", min_value=.024, max_value=1.,
                          value=.50, step=.004, format="%.3f", key=f"{prefix}_stop")
    jump = st.slider("Maximum jump per trace (samples)", 1, 8, 2, key=f"{prefix}_jump")
    configuration = (identity, view.request.view_kind, section_number, seed_trace, seed_time, start, stop, jump)
    if st.session_state.get("horizon_configuration") != configuration:
        st.session_state.pop("horizon_result", None)
        st.session_state["horizon_configuration"] = configuration
    ready = seed_trace is not None and seed_time is not None
    if st.button("Track selected synthetic horizon", disabled=not ready, key="horizon_track"):
        try:
            request = HorizonTrackRequest(
                dataset_id=identity, view_kind=view.request.view_kind, section_number=section_number,
                seed_trace=seed_trace, seed_time_s=seed_time, window_start_s=start,
                window_stop_s=stop, max_jump_samples=jump,
            )
            st.session_state["horizon_result"] = api.track_synthetic_horizon(request)
        except (GeoWorldClientError, ValueError) as exc:
            st.error(str(exc))
    return st.session_state.get("horizon_result")


def render_seismic_explorer(api) -> None:
    st.subheader("Seismic Explorer")
    st.caption("Inspect configured or privately uploaded regular post-stack SEG-Y and RSF data. Views are bounded reads; no numerical solver runs.")
    uploaded = st.file_uploader(
        "Upload SEG-Y", type=["sgy", "segy"], accept_multiple_files=False,
        key="seismic_upload",
    )
    if st.button(
        "Validate upload", disabled=uploaded is None, key="seismic_upload_submit",
    ):
        try:
            uploaded.seek(0)
            record = api.upload_seismic(uploaded.name, uploaded)
            st.session_state["seismic_upload_notice"] = (
                f"{record.display_filename} is validated and ready."
            )
            st.session_state.pop("seismic_response", None)
            st.session_state.pop("seismic_conversation_id", None)
            st.rerun()
        except GeoWorldClientError as exc:
            st.error(str(exc))
    if notice := st.session_state.pop("seismic_upload_notice", None):
        st.success(notice)
    try:
        catalog = api.list_seismic_datasets()
    except GeoWorldClientError as exc:
        st.warning(str(exc))
        return
    try:
        benchmarks = api.list_horizon_benchmarks()
        catalog = catalog.model_copy(update={"datasets": catalog.datasets + benchmarks.datasets})
    except GeoWorldClientError:
        st.caption("Synthetic horizon benchmarks are unavailable on this backend.")
    for warning in catalog.warnings:
        st.warning(warning)
    if not catalog.datasets:
        st.info("No seismic datasets are configured on this backend. Set an allowed seismic data root, then restart the backend.")
        return

    by_id = {item.dataset_id: item for item in catalog.datasets}
    selected_id = st.selectbox(
        "Dataset", list(by_id), format_func=lambda item: by_id[item].display_name,
        key="seismic_dataset_id",
    )
    if st.session_state.get("seismic_active_dataset") != selected_id:
        st.session_state["seismic_active_dataset"] = selected_id
        st.session_state.pop("seismic_response", None)
        st.session_state.pop("seismic_conversation_id", None)
        st.session_state.pop("horizon_result", None)

    dataset = by_id[selected_id]
    synthetic = dataset.provenance.get("horizon_tracking_scope") == "geoworld_generated_synthetic_only"
    st.write(
        f"**{dataset.dimensionality.upper()} {dataset.format.upper()}** · "
        f"{' × '.join(str(value) for value in dataset.shape)} · "
        f"{dataset.sample_interval:g} {dataset.sample_unit} sample interval"
    )
    section_options = {}
    if synthetic:
        kind = st.selectbox("Section direction", ["inline", "crossline"], key="horizon_direction")
        axis = dataset.axes[0 if kind == "inline" else 1]
        number = st.number_input(f"{kind.title()} number", min_value=int(axis.start),
                                 max_value=int(axis.stop), value=1212 if kind == "inline" else 316,
                                 step=1, key=f"horizon_section_{kind}")
        section_options = {"view_kind": kind, kind: number}
        response = st.session_state.get("seismic_response") or {}
        current = response.get("view") if isinstance(response, dict) else response.view
        if current is not None and (current.request.view_kind != kind or
                                    getattr(current.request, kind) != number):
            st.session_state.pop("seismic_response", None)
            st.session_state.pop("horizon_result", None)
    if st.button("Open dataset", type="primary", key="seismic_open"):
        try:
            view = api.get_seismic_view(SeismicViewRequest(dataset_id=selected_id, **section_options))
            st.session_state["seismic_response"] = {"view": view, "analysis": None, "state": None}
            st.session_state.pop("horizon_result", None)
        except GeoWorldClientError as exc:
            st.error(str(exc))

    if not synthetic:
        st.caption("Field data may be viewed; horizon tracking V0 is limited to built-in GeoWorld synthetics.")
        prompt = st.text_input(
            "Change the view or analyze it",
            placeholder="Show inline 1200 · Zoom from 1.5 to 2.5 seconds · Show the spectrum of this trace",
            key="seismic_prompt",
        )
        if st.button("Apply request", disabled=not prompt.strip(), key="seismic_apply"):
            try:
                response = api.continue_seismic_explorer(
                    prompt, dataset_id=selected_id,
                    conversation_id=st.session_state.get("seismic_conversation_id"),
                )
                st.session_state["seismic_response"] = response
                st.session_state["seismic_conversation_id"] = response.state.conversation_id
            except GeoWorldClientError as exc:
                st.error(str(exc))

    response = st.session_state.get("seismic_response")
    view = response.view if hasattr(response, "view") else (response or {}).get("view")
    analysis = response.analysis if hasattr(response, "analysis") else (response or {}).get("analysis")
    if view is None:
        return
    st.write(f"**Current view:** {view.selection_summary}")
    with st.expander("Display settings", expanded=False):
        clip = st.slider(
            "Symmetric amplitude clip percentile", 90.0, 100.0, 99.0, .5,
            help="Display-only. Source samples and metadata are unchanged.",
            key=f"seismic_clip_{selected_id}",
        )
        st.caption("Display-only clipping; this does not create processed seismic.")
    horizon = _render_horizon_controls(api, view) if synthetic else None
    if horizon is not None:
        st.write(f"**Tracking status:** {horizon.status}")
        metrics = horizon.metrics
        columns = st.columns(4)
        for column, name, label in zip(columns, ["mae_ms", "rmse_ms", "failure_rate", "coverage"],
                                       ["MAE (ms)", "RMSE (ms)", "Failure rate", "Coverage"]):
            value = metrics[name]
            text = "—" if value is None else f"{value:.1%}" if name in {"failure_rate", "coverage"} else f"{value:.3g}"
            column.metric(label, text)
        st.caption("MAE/RMSE describe returned picks. Failure rate includes missing picks and errors above 8 ms.")
        st.plotly_chart(_horizon_figure(view, horizon, clip), width="stretch")
        st.caption(horizon.limitations)
        st.download_button("Download derived horizon and provenance", horizon.model_dump_json(indent=2),
                           file_name="synthetic-horizon-v0.json", mime="application/json")
        with st.expander("Tracking confidence and failure details"):
            st.json({"confidence": horizon.confidence, "failure_reasons": horizon.failure_reasons})
    else:
        st.plotly_chart(_figure(view, clip), width="stretch")
    _render_analysis(analysis)
    with st.expander("Advanced: headers, provenance and raw metadata", expanded=False):
        st.json(dataset.model_dump(mode="json"))
        st.json(view.provenance)
