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
    fig.update_layout(title="Model geometry · baseline policy", xaxis_title="Distance (m)", yaxis_title="Depth (m)", height=350,
        margin=dict(l=50,r=20,t=45,b=45))
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, width="stretch")
    st.caption(data["note"])
    st.caption(f"CO₂: {'enabled in sand' if data['co2_enabled'] else 'off'} · Faults: {data['fault_count']}")
    st.caption('Edit primary inputs and Apply. Vp, Vs and density are read-only baseline values from the deterministic policy; simulation computes localized effects.')
    # Commit the editable table atomically with Apply; intermediate cell changes
    # must not race a Streamlit rerender or silently change the prepared model.
    with st.form('model_primary_inputs', clear_on_submit=False):
        import hashlib, json
        revision = hashlib.sha256(json.dumps(preview['geospec'], sort_keys=True).encode()).hexdigest()[:12]
        edits = st.data_editor(primary_rows(rows),
            key="model_layer_editor_"+revision, hide_index=True, width='stretch',
            disabled=['Layer', 'Vp (m/s)', 'Vs (m/s)', 'Density (kg/m³)'],
            column_config={'Lithology': st.column_config.SelectboxColumn(options=['shale','sand','carbonate','limestone','salt']),
                'Porosity (%)': st.column_config.NumberColumn(min_value=1.,max_value=40.,format='%.1f'),
                'Thickness (m)': st.column_config.NumberColumn(min_value=.01,max_value=20000,format='%.1f'),
                'Vp (m/s)':st.column_config.NumberColumn(help='Derived baseline policy; read-only'),
                'Vs (m/s)':st.column_config.NumberColumn(help='Derived baseline policy; read-only'),
                'Density (kg/m³)':st.column_config.NumberColumn(help='Derived baseline policy; read-only')})
        if st.form_submit_button("Apply layer edits"):
            spec = apply_primary_edits(preview['geospec'], rows, edits)
            if spec == preview['geospec']:
                st.info('Inputs are unchanged.')
                return
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
                    append_message('assistant', 'Edited inputs validated for a new experiment. Run simulation when ready; saved results remain unchanged.')
                    st.rerun()
                else:
                    st.warning(next((item['message'] for item in response.get('issues',[]) if item.get('severity')=='error'), 'Layer edits could not be validated.'))


def primary_rows(rows):
    return [{'Layer':row['index']+1, 'Lithology':row['lithology'], 'Thickness (m)':row['thickness_m'],
        'Porosity (%)':row['porosity']*100., 'Vp (m/s)':row['vp'], 'Vs (m/s)':row['vs'],
        'Density (kg/m³)':row['density']} for row in rows]


def apply_primary_edits(geospec, original_rows, edited_rows):
    """Convert display units only; the protected preview API validates the edit."""
    spec = deepcopy(geospec)
    for original, edited, layer in zip(original_rows, edited_rows, spec['geology']['layers']):
        for key,label in [('lithology','Lithology'),('thickness_m','Thickness (m)'),('porosity','Porosity (%)')]:
            value = edited[label]/100. if key == 'porosity' else edited[label]
            if value != original[key]:
                layer[key] = value
                if key == 'porosity':
                    layer['porosity_range'] = None
    return spec
