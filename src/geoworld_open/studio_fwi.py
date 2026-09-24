"""HTTP-only bounded FWI preview in the existing natural-language workspace."""
import streamlit as st
from geoworld_open.client import GeoWorldClientError
from geoworld_open.client.models import JobCreateRequest
from geoworld_open.studio_execution import render_preflight
from geoworld_open.studio_llm import execution_model_line
from geoworld_open.client.fwi import FWI_LABELS, FWI_REFERENCE_ID, FWI_PROGRESSIVE_ID
from geoworld_open.client.intermediate_results import IntermediateResultPolicy


def render_fwi_workspace(api, submit, *, prompt, auto_prepare=False, prepare_only=False):
    st.subheader('Acoustic velocity FWI · Deepwave references')
    st.caption('Review the selected versioned experiment before Run. Acoustic Vp inversion is not RTM or elastic/AVO inversion.')
    if st.session_state.get('fwi_prompt') != prompt:
        st.session_state.pop('fwi_preview',None)
        st.session_state['fwi_prompt']=prompt
    policy=None
    with st.expander('Advanced: intermediate results'):
        mode=st.selectbox('Display snapshot policy',['auto','final','interval','schedule'],key='fwi_snapshot_mode')
        values={'mode':mode}
        if mode=='interval':
            values['interval']=st.number_input('Snapshot interval (completed optimizer steps)',min_value=1,value=50,step=1)
        elif mode=='schedule':
            raw=st.text_input('Snapshot steps (comma-separated; at most ten)',value='50,100,150,200,250')
            try:
                values['schedule']=[int(s.strip()) for s in raw.split(',') if s.strip()]
            except ValueError:
                values['schedule']=[]
        st.caption('Auto: final only for short runs, at most five states for long runs, or one state per scientific frequency stage. This does not change restart checkpoints.')
        try:
            policy=IntermediateResultPolicy(**values)
        except ValueError:
            st.warning('Use positive, unique, increasing snapshot steps and a bounded schedule.')
    signature=policy.model_dump_json() if policy else None
    if st.session_state.get('fwi_snapshot_signature')!=signature:
        st.session_state.pop('fwi_preview',None)
        st.session_state['fwi_snapshot_signature']=signature
    if st.button('Interpret & preview FWI') or auto_prepare:
        st.session_state.pop('fwi_preview',None)
        if policy is None:
            return
        try:
            with st.spinner('Preparing model inputs and execution estimate; no inversion yet…'):
                st.session_state['fwi_preview']=api.preview_fwi(prompt=prompt,intermediate_results=policy)
        except GeoWorldClientError as exc:
            st.error(str(exc))
    preview=st.session_state.get('fwi_preview')
    if preview is None:
        return
    st.write(FWI_LABELS[preview.selection.reference_id])
    if preview.selection.reference_id==FWI_PROGRESSIVE_ID:
        st.caption('This method uses velocity bounds and staged frequency filtering to address extreme updates '
                   'and cycle skipping. It is distinct from simple SGD; convergence is not guaranteed.')
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
    if preview.snapshot_schedule:
        suffix='completed optimizer updates'
        if preview.selection.reference_id==FWI_PROGRESSIVE_ID:
            suffix='completed outer steps'
            if preview.snapshot_schedule==[2,4,6,8,10]:
                suffix+=' (one per frequency stage)'
        st.caption('Display snapshots: '+', '.join(map(str,preview.snapshot_schedule))+' '+suffix+'. Restart checkpoints are separate.')
    for issue in preview.selection.conflicts+preview.selection.requested_changes:
        st.warning(issue)
    if prepare_only or preview.selection.action=='prepare':
        st.info('Prepared only. Ask to run when ready; this preview cannot launch inversion.')
    with st.expander('Advanced: interpreted request, inherited science and assumptions'):
        st.json(preview.selection.model_dump(mode='json'))
        st.json(preview.settings)
    label='Run bounded FWI' if preview.selection.reference_id==FWI_REFERENCE_ID else 'Run FWI'
    same_submitted_fwi=(st.session_state.get('last_submitted_mode_hint')=='bounded_fwi'
        and st.session_state.get('last_submitted_prompt')==prompt
        and st.session_state.get('last_job_id'))
    last_job=st.session_state.get('last_job')
    submitted_not_failed=bool(same_submitted_fwi and (last_job is None or last_job.status!='failed'))
    if submitted_not_failed:
        if last_job is not None and last_job.status=='succeeded':
            st.info('This FWI request already completed; the saved result is shown in the result panel.')
        else:
            st.info('This FWI request is already submitted; the result panel will keep watching the running job.')
    if st.button(label,disabled=prepare_only or not preview.runnable or not feasible or submitted_not_failed):
        submit(api,JobCreateRequest(prompt=prompt,mode_hint='bounded_fwi',fwi_preparation_id=preview.preparation_id))
