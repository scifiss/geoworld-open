"""Public HTTP-only Seismic Explorer presentation."""
from __future__ import annotations

import numpy as np
import streamlit as st

from geoworld_open.client.backend import GeoWorldClientError
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

    dataset = by_id[selected_id]
    st.write(
        f"**{dataset.dimensionality.upper()} {dataset.format.upper()}** · "
        f"{' × '.join(str(value) for value in dataset.shape)} · "
        f"{dataset.sample_interval:g} {dataset.sample_unit} sample interval"
    )
    if st.button("Open dataset", type="primary", key="seismic_open"):
        try:
            view = api.get_seismic_view(SeismicViewRequest(dataset_id=selected_id))
            st.session_state["seismic_response"] = {"view": view, "analysis": None, "state": None}
        except GeoWorldClientError as exc:
            st.error(str(exc))

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
    st.plotly_chart(_figure(view, clip), width="stretch")
    _render_analysis(analysis)
    with st.expander("Advanced: headers, provenance and raw metadata", expanded=False):
        st.json(dataset.model_dump(mode="json"))
        st.json(view.provenance)
