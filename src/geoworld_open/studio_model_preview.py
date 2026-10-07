"""PUBLIC_SDK_INFRA: display backend preparation data; editing stays HTTP validated."""
from copy import deepcopy
import streamlit as st
import plotly.graph_objects as go
from geoworld_open.client import GeoWorldClientError


def render_prepared_geometry(api, preview):
    data = preview.get("model_preview")
    if not data:
        return
    rows = data["layers"]
    palette = {"shale": "#4c566a", "sand": "#d8b365", "sandstone": "#b8860b", "carbonate": "#80cdc1", "limestone": "#35978f", "salt": "#c2a5cf"}
    colors = []
    for index,row in enumerate(rows):
        color = palette.get(row["lithology"], "#999999")
        colors.extend([[index/len(rows),color],[(index+1)/len(rows),color]])
    fig = go.Figure(go.Heatmap(x=data["x_m"], y=data["z_m"], z=data["layer_indices"],
        colorscale=colors, zmin=.5, zmax=len(rows)+.5,
        colorbar={"tickvals": list(range(1,len(rows)+1)), "ticktext": [f"{index+1}: {row['lithology']}" for index,row in enumerate(rows)]},
        hovertemplate="x=%{x} m<br>depth=%{y} m<br>layer=%{z}<extra></extra>"))
    fig.update_layout(title="Prepared geological cross-section", xaxis_title="Distance (m)", yaxis_title="Depth (m)")
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, width="stretch")
    st.caption(data["note"])
    st.caption(f"CO₂: {'enabled in sand' if data['co2_enabled'] else 'off'} · Faults: {data['fault_count']}")
    display = [{key: value for key,value in row.items() if key != "sources"} |
               {f"{key} source": value for key,value in row["sources"].items()} for row in rows]
    st.dataframe(display, hide_index=True, width="stretch", column_config={
        "vp": st.column_config.NumberColumn("Vp (m/s)"), "vs": st.column_config.NumberColumn("Vs (m/s)"),
        "density": st.column_config.NumberColumn("Density (kg/m³)"), "thickness_m": st.column_config.NumberColumn("Thickness (m)")})
    with st.expander("Edit basic layer properties", expanded=False):
        st.caption("Edit porosity or thickness, then Apply. Values and geometry are validated before Run.")
        import hashlib, json
        revision = hashlib.sha256(json.dumps(preview['geospec'], sort_keys=True).encode()).hexdigest()[:12]
        edits = st.data_editor([{key: row[key] for key in ("index", "lithology", "thickness_m", "porosity")} for row in rows],
            key="model_layer_editor_"+revision, hide_index=True, disabled=["index", "lithology"],
            column_config={"porosity": st.column_config.NumberColumn(min_value=.01,max_value=.4),
                           "thickness_m": st.column_config.NumberColumn(min_value=.01,max_value=20000)})
        if st.button("Apply layer edits", key="apply_model_layer_edits"):
            spec = deepcopy(preview["geospec"])
            for original, edited, layer in zip(rows, edits, spec["geology"]["layers"]):
                for key in ("porosity", "thickness_m"):
                    if edited[key] != original[key]:
                        layer[key] = edited[key]
                        if key == "porosity":
                            layer["porosity_range"] = None
            try:
                response = api.preview_geospec(geospec=spec)
            except GeoWorldClientError as exc:
                st.error(str(exc))
            else:
                if response.get("valid"):
                    from geoworld_open.studio_context import commit_build, task_context
                    from geoworld_open.studio_assistant import append_message
                    response['interpretation_mode'] = 'user_table_edit'
                    response['degraded'] = preview.get('degraded',False)
                    response['confirmation_required'] = preview.get('confirmation_required',False)
                    commit_build(response, task_context().build.turns)
                    st.session_state['prepared_preview'] = response
                    st.session_state['studio_auto_edit_serial'] = st.session_state.get('studio_auto_edit_serial', 0) + 1
                    st.session_state.pop('unified_fallback_confirmed',None)
                    append_message('assistant', 'Layer edits validated. Review the updated geometry, values and assumptions before Run.')
                    st.rerun()
                else:
                    st.warning(next((item['message'] for item in response.get('issues',[]) if item.get('severity')=='error'), 'Layer edits could not be validated.'))
