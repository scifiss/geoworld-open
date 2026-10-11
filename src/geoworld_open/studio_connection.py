"""A lost transport leaves accepted job outcome unknown; reconnect, never rerun."""
import streamlit as st
from .client.backend import GeoWorldClientError


def reconnect_job(api):
    pending = st.session_state.get('studio_interrupted_submission')
    if not pending:
        return None
    st.warning('Connection to the backend was lost after submission. The job outcome is unconfirmed; this is not a scientific failure. Reconnect to check the existing job before submitting again.')
    if not st.button('Reconnect to submitted job'):
        return None
    try:
        job = api.get_job(pending['job_id'])
    except GeoWorldClientError as exc:
        st.warning(str(exc))
        return None
    if job.status in {'queued', 'running'}:
        st.info('The submitted job is still pending. Reconnect again to check its status; no new job was created.')
        return None
    st.session_state.pop('studio_interrupted_submission', None)
    if job.status == 'failed':
        from .studio_assistant import append_message
        message = job.error or 'The backend recorded an interrupted or failed job. Previous results remain available.'
        append_message('assistant', message)
        st.error(message)
        return None
    return pending, job
