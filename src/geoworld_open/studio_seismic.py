"""Public HTTP-only Seismic Explorer presentation."""
from __future__ import annotations

import logging

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
    st.markdown("#### Track one selected horizon")
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
            st.rerun()
        except (GeoWorldClientError, ValueError) as exc:
            st.error(str(exc))
    return st.session_state.get("horizon_result")


def _response_parts(response):
    if response is None:
        return None, None, None
    if isinstance(response, dict):
        return response.get("view"), response.get("analysis"), response.get("state")
    return response.view, response.analysis, response.state


def _merge_response(previous, current):
    old_view, old_analysis, _ = _response_parts(previous)
    return {
        "view": current.view or old_view,
        "analysis": current.analysis if current.view is not None else (current.analysis or old_analysis),
        "state": current.state,
    }


def _render_horizon_summary(horizon) -> None:
    st.markdown(f"#### Horizon result · {horizon.status}")
    picked = sum(value is not None for value in horizon.picked_time_s)
    failed = len(horizon.picked_time_s) - picked
    accepted = [score for pick, score in zip(horizon.picked_time_s, horizon.confidence)
                if pick is not None]
    columns = st.columns(3)
    columns[0].metric("Picked traces", f"{picked}/{len(horizon.picked_time_s)}")
    columns[1].metric("Abstained", failed)
    columns[2].metric("Mean confidence", f"{np.mean(accepted):.2f}" if accepted else "—")
    if horizon.truth_time_s:
        metrics = horizon.metrics
        columns = st.columns(3)
        columns[0].metric("MAE (ms)", "—" if metrics.get("mae_ms") is None else f"{metrics['mae_ms']:.3g}")
        columns[1].metric("RMSE (ms)", "—" if metrics.get("rmse_ms") is None else f"{metrics['rmse_ms']:.3g}")
        columns[2].metric("Failure rate", f"{metrics['failure_rate']:.1%}")
        st.caption(
            "Synthetic truth evaluation only. MAE/RMSE describe returned picks; "
            "failure rate also counts abstentions and errors above 8 ms."
        )
    reasons = {}
    for reason in horizon.failure_reasons:
        if reason:
            reasons[reason] = reasons.get(reason, 0) + 1
    if reasons:
        st.write("**Failure summary:** " + " · ".join(
            f"{name.replace('_', ' ')}: {count}" for name, count in reasons.items()
        ))
    st.caption(horizon.limitations)
    st.download_button(
        "Download derived horizon and provenance", horizon.model_dump_json(indent=2),
        file_name="synthetic-horizon-v0.json", mime="application/json",
    )
    with st.expander("Per-trace confidence and failure details"):
        st.json({"confidence": horizon.confidence, "failure_reasons": horizon.failure_reasons})


def catalog_warning_message(warning: str) -> str:
    if "uploaded dataset is unavailable or failed revalidation" in warning.casefold():
        return "A previously uploaded seismic file is no longer available. Reattach it to continue."
    return warning


def seismic_catalog(api):
    """Read user/configured data only; retain original diagnostics for provenance."""
    catalog = api.list_seismic_datasets()
    st.session_state["seismic_catalog_warnings"] = list(catalog.warnings)
    shown = set()
    for warning in catalog.warnings:
        logging.getLogger(__name__).warning("Seismic catalog: %s", warning)
        message = catalog_warning_message(warning)
        if message not in shown:
            st.warning(message)
            shown.add(message)
    st.session_state["seismic_visible_warnings"] = list(shown)
    return catalog


def activate_dataset(dataset, *, demo=False):
    """Session context only. Does not create project storage or alter source data."""
    if st.session_state.get("seismic_dataset_id") != dataset.dataset_id:
        for key in ("seismic_response", "seismic_conversation_id", "horizon_result",
                    "horizon_configuration"):
            st.session_state.pop(key, None)
    from geoworld_open.studio_context import commit_seismic
    commit_seismic(dataset.dataset_id)
    st.session_state["seismic_dataset_id"] = dataset.dataset_id
    st.session_state["seismic_context_dataset"] = dataset
    st.session_state["seismic_active_dataset"] = dataset.dataset_id
    st.session_state["studio_active_context"] = "seismic"
    if demo:
        st.session_state["seismic_demo_dataset"] = dataset
    else:
        st.session_state.pop("seismic_demo_dataset", None)


def render_seismic_explorer(api, *, dataset=None) -> None:
    """Contextual workspace only; the shared assistant owns requests and attachments."""
    st.subheader("Seismic view")
    try:
        catalog = seismic_catalog(api)
    except GeoWorldClientError as exc:
        st.warning(str(exc))
        return
    by_id = {item.dataset_id: item for item in catalog.datasets}
    demo = st.session_state.get("seismic_demo_dataset")
    if dataset is None:
        dataset = demo or by_id.get(st.session_state.get("seismic_dataset_id"))
        if dataset is None and catalog.datasets and not st.session_state.get("seismic_dataset_id"):
            dataset = catalog.datasets[0]
    if dataset is None:
        st.info("Attach a seismic file to continue, or open an example from the assistant.")
        st.session_state.pop("seismic_response", None)
        return
    activate_dataset(dataset, demo=bool(demo) or dataset.format == "synthetic")
    synthetic = dataset.provenance.get("horizon_tracking_scope") == "geoworld_generated_synthetic_only"
    if synthetic:
        st.markdown("**Synthetic benchmark** · generated truth available for evaluation")
    else:
        st.caption("Attached: " + dataset.display_name)
        st.caption("View and analysis only for Horizon V0")
    st.caption(
        f"{dataset.dimensionality.upper()} {dataset.format.upper()} · "
        f"{' × '.join(str(value) for value in dataset.shape)} · "
        f"{dataset.sample_interval:g} {dataset.sample_unit} sample interval"
    )
    # Switching is a contextual action and never mixes examples with user data.
    if len(by_id) > 1:
        with st.expander("Switch attached data", expanded=False):
            selected = st.selectbox(
                "Available seismic files", list(by_id),
                index=list(by_id).index(dataset.dataset_id) if dataset.dataset_id in by_id else 0,
                format_func=lambda identity: by_id[identity].display_name,
                key="seismic_context_choice",
            )
            if st.button("Use this file", key="seismic_switch"):
                activate_dataset(by_id[selected])
                st.rerun()

    section_options = {}
    if synthetic:
        columns = st.columns(2)
        kind = columns[0].selectbox("Section direction", ["inline", "crossline"], key="horizon_direction")
        axis = dataset.axes[0 if kind == "inline" else 1]
        number = columns[1].number_input(
            f"{kind.title()} number", min_value=int(axis.start), max_value=int(axis.stop),
            value=1212 if kind == "inline" else 316, step=1, key=f"horizon_section_{kind}",
        )
        section_options = {"view_kind": kind, kind: number}
    requested_view = SeismicViewRequest(dataset_id=dataset.dataset_id, **section_options)
    response = st.session_state.get("seismic_response")
    view, analysis, _ = _response_parts(response)
    changed = view is None or view.dataset.dataset_id != dataset.dataset_id
    if synthetic and view is not None:
        changed = (
            view.request.view_kind != requested_view.view_kind
            or getattr(view.request, requested_view.view_kind) != getattr(requested_view, requested_view.view_kind)
        )
    if changed:
        try:
            view = api.get_seismic_view(requested_view)
            response = {"view": view, "analysis": None, "state": None}
            st.session_state["seismic_response"] = response
            analysis = None
            st.session_state.pop("horizon_result", None)
        except GeoWorldClientError as exc:
            message = catalog_warning_message(str(exc))
            if message not in st.session_state.get("seismic_visible_warnings", []):
                st.warning(message)
            view = None

    pending = st.session_state.pop("seismic_unified_request", None)
    if pending:
        if synthetic:
            st.session_state["assistant_notice"] = (
                "This synthetic example uses the section and Horizon V0 controls below. "
                "Attach a seismic file for navigation and analysis requests."
            )
        else:
            try:
                current = api.continue_seismic_explorer(
                    pending, dataset_id=dataset.dataset_id,
                    conversation_id=st.session_state.get("seismic_conversation_id"),
                )
                response = _merge_response(response, current)
                st.session_state["seismic_response"] = response
                st.session_state["seismic_conversation_id"] = current.state.conversation_id
                view, analysis, _ = _response_parts(response)
            except GeoWorldClientError as exc:
                message = catalog_warning_message(str(exc))
                st.session_state["assistant_notice"] = message
                from geoworld_open.studio_assistant import append_message
                append_message("assistant", message)
    if view is None:
        return
    from geoworld_open.studio_context import commit_seismic
    commit_seismic(dataset.dataset_id, view=view.request, conversation_id=st.session_state.get("seismic_conversation_id"))
    st.write(f"**Current view:** {view.selection_summary}")
    clip_key = f"seismic_clip_{dataset.dataset_id}"
    clip = float(st.session_state.get(clip_key, 99.0))
    figure_slot = st.container()
    horizon = _render_horizon_controls(api, view) if synthetic else None
    with figure_slot:
        st.plotly_chart(
            _horizon_figure(view, horizon, clip) if horizon is not None else _figure(view, clip),
            width="stretch",
        )
    if horizon is not None:
        _render_horizon_summary(horizon)
    _render_analysis(analysis)
    with st.expander("Display settings", expanded=False):
        st.slider(
            "Symmetric amplitude clip percentile", 90.0, 100.0, 99.0, .5,
            help="Display-only. Source samples and metadata are unchanged.", key=clip_key,
        )
        st.caption("Display-only clipping; this does not create processed seismic.")
    with st.expander("Headers and provenance", expanded=False):
        st.json(dataset.model_dump(mode="json"))
        st.json(view.provenance)
        if catalog.warnings:
            st.json({"catalog_warnings": catalog.warnings})
