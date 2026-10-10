"""PUBLIC_SDK_INFRA: owner-authenticated HTTP transcript recovery, no local secrets."""
from uuid import uuid4
import streamlit as st
from geoworld_open.client import GeoWorldClientError
from geoworld_open.client.studio_session import StudioConversationSave


def persist_conversation(api):
    # Recovery is optional: only persist after the authenticated sidebar has
    # confirmed server support. Standalone viewers retain their session history.
    if st.session_state.get('studio_recovery_supported') is not True:
        return
    from .studio_context import task_context
    context=task_context()
    history=st.session_state.get('assistant_history',[])
    if not history:
        return
    job=context.scientific.completed_job_id if context.scientific else None
    try:
        request=StudioConversationSave(revision=st.session_state.get('studio_conversation_revision',0),
            messages=history,active_scientific_job_id=job,
            selected_fields=st.session_state.get('scientific_panel_order',[]))
    except ValueError:
        st.session_state['studio_recovery_error']='This conversation exceeds the bounded recovery record. Browser history is preserved; start a new conversation to save further work.'
        return
    signature=request.model_dump_json(exclude={'revision'})
    if signature==st.session_state.get('studio_saved_conversation_signature'):
        return
    identity=st.session_state.setdefault('studio_conversation_id',uuid4().hex)
    try:
        record=api.save_studio_conversation(identity,request)
        st.session_state['studio_conversation_revision']=record.revision
        st.session_state['studio_saved_conversation_signature']=signature
        st.session_state.pop('studio_recovery_error',None)
    except GeoWorldClientError as exc:
        st.session_state['studio_recovery_error']='Recent conversation could not be saved. Your current browser context remains available. '+str(exc)


def render_recovery(api):
    if 'studio_recent_conversations' not in st.session_state:
        try:
            st.session_state['studio_recent_conversations']=api.recent_studio_conversations()
            st.session_state['studio_recovery_supported']=True
        except GeoWorldClientError:
            st.session_state['studio_recent_conversations']=[]
            st.session_state['studio_recovery_supported']=False
    recent=st.session_state['studio_recent_conversations']
    with st.expander('Restore recent scientific work',expanded=bool(recent and not st.session_state.get('assistant_history'))):
        st.caption('Sign in to restore this account’s recent conversation and scientific reference. Recovery window: three hours after the last saved change. Scientific files must still be available.')
        if st.button('Refresh recent conversations',key='studio_refresh_recovery'):
            st.session_state.pop('studio_recent_conversations',None)
            st.rerun()
        if recent:
            choice=st.selectbox('Recent conversation',range(len(recent)),
                format_func=lambda i:recent[i].title+' · '+recent[i].updated_at[:16].replace('T',' '))
            if st.button('Restore conversation and results',key='studio_restore_conversation'):
                try:
                    record=api.restore_studio_conversation(recent[choice].conversation_id)
                    from .client.studio_request import StudioTaskContext
                    st.session_state['assistant_history']=[m.model_dump() for m in record.messages]
                    st.session_state['studio_conversation_id']=record.conversation_id
                    st.session_state['studio_conversation_revision']=record.revision
                    st.session_state['studio_task_context']=StudioTaskContext(
                        active_task='scientific' if record.scientific_context else 'none',scientific=record.scientific_context)
                    st.session_state['assistant_job_seen']=([record.active_scientific_job_id] if record.active_scientific_job_id else [])
                    for key in ('studio_decision','last_job','last_job_id','studio_saved_conversation_signature','studio_scientific_view_job','studio_selected_figure'):
                        st.session_state.pop(key,None)
                    st.session_state['studio_active_context']='request'
                    st.session_state['studio_restored_fields']=record.selected_fields
                    st.session_state['assistant_notice']=record.recovery_message or 'Conversation and verified scientific results restored.'
                    st.rerun()
                except GeoWorldClientError as exc:
                    st.warning(str(exc))
        elif st.session_state.get('studio_recovery_supported'):
            st.caption('No recent recoverable conversation for this account.')
        else:
            st.caption('Server conversation recovery is unavailable. This browser session still holds your current conversation.')
        if st.session_state.get('studio_recovery_error'):
            st.warning(st.session_state['studio_recovery_error'])
