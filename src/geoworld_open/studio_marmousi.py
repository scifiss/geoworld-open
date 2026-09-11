"""PUBLIC_SDK_INFRA: service-backed benchmark model explorer."""
from __future__ import annotations

import streamlit as st

from geoworld_open.client import GeoWorldClientError
from geoworld_open.client.marmousi import MarmousiSelection, ModelCrop, PropertyOverrides, MarmousiPreviewRequest
from geoworld_open.client.models import JobCreateRequest
from geoworld_open.studio_llm import execution_model_line


def box_crop(box, extent):
    """Normalize plot coordinates; reject invalid/outside selections server-side too."""
    xs, zs = sorted(box["x"]), sorted(box["y"])
    return ModelCrop(x_start_m=max(extent.x_start_m, xs[0]), x_stop_m=min(extent.x_stop_m, xs[-1]),
                     z_start_m=max(extent.z_start_m, zs[0]), z_stop_m=min(extent.z_stop_m, zs[-1]))


def model_figure(preview, *, selectable=False):
    import plotly.graph_objects as go
    fig = go.Figure(go.Heatmap(x=preview.x_m, y=preview.z_m, z=preview.values_zx,
        colorscale="Viridis", colorbar={"title": preview.unit},
        hovertemplate="x=%{x:.1f} m<br>depth=%{y:.1f} m<br>value=%{z:.3f}<extra></extra>"))
    if selectable:
        # Heatmaps have no Plotly selection event. A transparent, bounded
        # scatter lattice makes box selection available without a custom JS bridge.
        xs = preview.x_m[::max(1, len(preview.x_m)//60)]
        zs = preview.z_m[::max(1, len(preview.z_m)//30)]
        fig.add_trace(go.Scatter(x=[x for x in xs for _ in zs], y=[z for _ in xs for z in zs],
            mode="markers", marker={"size": 5, "opacity": .01}, showlegend=False, hoverinfo="skip"))
    fig.update_layout(dragmode="select" if selectable else "zoom", height=380,
        margin={"l": 50, "r": 15, "t": 10, "b": 40}, xaxis_title="x (m)", yaxis_title="Depth (m)")
    fig.update_xaxes(constrain="domain")
    fig.update_yaxes(autorange="reversed", scaleanchor="x", scaleratio=1, constrain="domain")
    return fig


def _set_controls(selection, extent):
    st.session_state["marmousi_dataset"] = selection.dataset
    st.session_state["marmousi_property"] = selection.display_property
    for key, value in (selection.crop or extent).model_dump().items():
        st.session_state["marmousi_" + key] = value
    for key, value in selection.overrides.model_dump().items():
        st.session_state["marmousi_enable_" + key] = value is not None
        if value is not None:
            st.session_state["marmousi_" + key] = value


def render_model_workspace(api, submit, *, prompt=None, auto_prepare=False):
    unified = prompt is not None
    st.subheader("Marmousi model explorer")
    st.caption("Load an existing Marmousi 1 or 2 model, inspect it, then crop in metres. This is separate from exact-reference RTM; no solver runs here.")
    if not unified:
        prompt = st.text_input("Describe the model you want to inspect", placeholder="Show Marmousi 2", key="marmousi_prompt")
    if st.session_state.get("marmousi_interpreted_prompt") != prompt:
        st.session_state.pop("marmousi_interpretation", None)
    interpret_clicked = not unified and st.button("Interpret & show model", disabled=not prompt.strip())
    if interpret_clicked or auto_prepare:
        st.session_state.pop("marmousi_load_error", None)
        # Clear stale previews before a new interpretation, including failure.
        st.session_state.pop("marmousi_base", None)
        st.session_state.pop("marmousi_preview", None)
        st.session_state.pop("marmousi_interpretation", None)
        try:
            response = api.interpret_marmousi(prompt)
            st.session_state["marmousi_interpretation"] = response
            st.session_state["marmousi_interpreted_prompt"] = prompt
            if response.selection and not response.unresolved:
                base = api.preview_marmousi(MarmousiSelection(dataset=response.selection.dataset))
                st.session_state["marmousi_base"] = base
                _set_controls(response.selection, base.dataset_extent)
        except GeoWorldClientError as exc:
            st.session_state["marmousi_load_error"] = str(exc)
    interpretation = st.session_state.get("marmousi_interpretation")
    if interpretation:
        if interpretation.llm:
            st.caption(execution_model_line(interpretation.llm, purpose="Model request interpretation"))
        for issue in interpretation.unresolved:
            st.warning(issue)
        st.caption("Review/edit the controls below. They—not unconfirmed words in a prompt—define the model preview.")
    if unified:
        if interpretation is None or interpretation.selection is None or interpretation.unresolved:
            if st.session_state.get("marmousi_load_error"):
                st.error(st.session_state["marmousi_load_error"])
            return
        dataset = interpretation.selection.dataset
        st.write("**Dataset:** " + ("Marmousi 1" if dataset == "marmousi1" else "Marmousi 2"))
    else:
        dataset = st.selectbox("Benchmark dataset", ["marmousi1", "marmousi2"],
            format_func=lambda name: "Marmousi 1" if name == "marmousi1" else "Marmousi 2", key="marmousi_dataset")
    base = st.session_state.get("marmousi_base")
    if base and base.selection.dataset != dataset:
        st.session_state.pop("marmousi_base", None)
        st.session_state.pop("marmousi_preview", None)
        base = None
    if base is None:
        if st.session_state.get("marmousi_load_error"):
            st.error(st.session_state["marmousi_load_error"])
        if st.button("Retry loading selected model" if unified else "Load selected dataset (manual)"):
            try:
                base = api.preview_marmousi(MarmousiSelection(dataset=dataset))
                st.session_state["marmousi_base"] = base
                # Dataset widget already exists in this render; update other controls only.
                for key, value in base.dataset_extent.model_dump().items():
                    st.session_state["marmousi_" + key] = value
                for key in PropertyOverrides.model_fields:
                    st.session_state["marmousi_enable_" + key] = False
                st.session_state["marmousi_property"] = "vp"
                if unified:
                    _set_controls(interpretation.selection, base.dataset_extent)
                st.session_state.pop("marmousi_load_error", None)
            except GeoWorldClientError as exc:
                st.error(str(exc))
        if base is None:
            return
    extent = base.dataset_extent
    st.write(f"Original: **{base.shape_xz[0]:,} × {base.shape_xz[1]:,}** samples · {base.spacing_m:g} m grid · "
             f"{extent.x_stop_m:g} m wide × {extent.z_stop_m:g} m deep")
    st.caption("Drag a rectangle on the original Vp plot, then apply it, or enter exact bounds below. Plot is a display thumbnail, not a resampled solver model.")
    try:
        chart = st.plotly_chart(model_figure(base, selectable=True), key="marmousi_map_" + dataset,
                               on_select="rerun", selection_mode="box", width="stretch")
        boxes = chart.selection.get("box", [])
        if boxes:
            try:
                chosen = box_crop(boxes[-1], extent)
                def apply_box():
                    for key, value in chosen.model_dump().items():
                        st.session_state["marmousi_" + key] = value
                st.button("Use selected rectangle", on_click=apply_box)
            except (ValueError, KeyError):
                st.info("Select a non-empty rectangle inside the model.")
    except ImportError:
        st.info("Install the Studio demo dependencies for the interactive plot. Exact crop controls remain available.")
    columns = st.columns(2)
    bounds = {}
    for i, (key, label, limit) in enumerate([
        ("x_start_m", "X start (m)", extent.x_stop_m), ("x_stop_m", "X stop (m)", extent.x_stop_m),
        ("z_start_m", "Z start (m)", extent.z_stop_m), ("z_stop_m", "Z stop (m)", extent.z_stop_m)]):
        bounds[key] = columns[i % 2].number_input(label, min_value=0., max_value=float(limit),
            step=float(base.spacing_m), key="marmousi_" + key)
    overrides = {}
    with st.expander("Optional properties · uniform assumptions over this crop"):
        st.caption("Original fields are retained unless checked. Porosity is not present in the files. Overrides do not derive other properties or change the original benchmark.")
        for key, label, default, low, high in [
            ("vp_m_s", "Vp (m/s)", 3000., 500., 10000.), ("vs_m_s", "Vs (m/s)", 1500., 0., 6000.),
            ("density_kg_m3", "Density (kg/m³)", 2300., 500., 5000.),
            ("porosity_fraction", "Porosity (fraction, 0–1)", .2, 0., 1.)]:
            enabled = st.checkbox("Override " + label, key="marmousi_enable_" + key)
            value = st.number_input(label, min_value=low, max_value=high, value=default,
                disabled=not enabled, key="marmousi_" + key)
            if enabled:
                overrides[key] = value
    prop = st.selectbox("Display property", ["vp", "vs", "density", "porosity"], key="marmousi_property")
    try:
        crop = ModelCrop(**bounds)
        selection = MarmousiSelection(dataset=dataset, crop=None if crop == extent else crop,
                                     overrides=PropertyOverrides(**overrides), display_property=prop)
        current = st.session_state.get("marmousi_preview")
        if current is None or current.selection != selection:
            # Bounded read-only preview on every actual selection edit, not solver execution.
            current = api.preview_marmousi(selection)
            st.session_state["marmousi_preview"] = current
        st.write(f"Selected: **{current.shape_xz[0]:,} × {current.shape_xz[1]:,}** native samples · "
                 f"{current.resolved_crop.x_stop_m-current.resolved_crop.x_start_m:g} m × "
                 f"{current.resolved_crop.z_stop_m-current.resolved_crop.z_start_m:g} m")
        if selection.crop or overrides or prop != "vp":
            try:
                st.plotly_chart(model_figure(current), key="marmousi_crop", width="stretch")
            except ImportError:
                pass
        else:
            st.caption("The original Vp plot above is the current selection.")
        for warning in current.warnings:
            st.caption(warning)
        with st.expander("Crop, property assumptions & source provenance"):
            st.json(current.provenance)
        if st.button("Save model preview & provenance"):
            submit(api, JobCreateRequest(prompt=prompt or "Save explicitly reviewed Marmousi model controls", mode_hint="marmousi_model",
                                        marmousi_model=MarmousiPreviewRequest(selection=selection)))
    except (ValueError, GeoWorldClientError) as exc:
        st.session_state.pop("marmousi_preview", None)
        st.error(str(exc))
