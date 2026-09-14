"""HTTP-only bounded FWI preview in the existing natural-language workspace."""
import streamlit as st
from geoworld_open.client import GeoWorldClientError
from geoworld_open.client.models import JobCreateRequest
from geoworld_open.studio_execution import render_preflight
from geoworld_open.studio_llm import execution_model_line


def render_fwi_workspace(api, submit, *, prompt, auto_prepare=False, prepare_only=False):
    st.subheader('Acoustic velocity FWI · bounded reference')
    st.caption('Ten updates of the simple upstream-derived Marmousi 1 inversion, not RTM, AVO or a converged model.')
    if st.session_state.get('fwi_prompt') != prompt:
        st.session_state.pop('fwi_preview',None)
        st.session_state['fwi_prompt']=prompt
    if st.button('Interpret & preview FWI') or auto_prepare:
        st.session_state.pop('fwi_preview',None)
        try:
            with st.spinner('Preparing model inputs and execution estimate; no inversion yet…'):
                st.session_state['fwi_preview']=api.preview_fwi(prompt=prompt)
        except GeoWorldClientError as exc:
            st.error(str(exc))
    preview=st.session_state.get('fwi_preview')
    if preview is None:
        return
    if preview.llm:
        st.caption(execution_model_line(preview.llm,purpose='FWI interpretation'))
    import plotly.graph_objects as go
    m=preview.model_preview
    st.caption(m['label'])
    fig=go.Figure(go.Heatmap(x=m['x_m'],y=m['z_m'],z=m['initial_velocity'],colorbar=dict(title='Vp (m/s)')))
    fig.update_layout(title='INPUT: initial velocity',xaxis_title='x (m)',yaxis_title='Depth (m)')
    fig.update_yaxes(autorange='reversed',scaleanchor='x')
    st.plotly_chart(fig,width='stretch')
    feasible=render_preflight(preview.execution_plan)
    for issue in preview.selection.conflicts+preview.selection.requested_changes:
        st.warning(issue)
    if prepare_only or preview.selection.action=='prepare':
        st.info('Prepared only. Ask to run when ready; this preview cannot launch inversion.')
    with st.expander('Advanced: interpreted request, inherited science and assumptions'):
        st.json(preview.selection.model_dump(mode='json'))
        st.json(preview.settings)
    if st.button('Run bounded FWI',disabled=prepare_only or not preview.runnable or not feasible):
        submit(api,JobCreateRequest(prompt=prompt,mode_hint='bounded_fwi',fwi_preparation_id=preview.preparation_id))
