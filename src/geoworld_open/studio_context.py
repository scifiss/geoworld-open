"""PUBLIC_SDK_INFRA: typed session state and legacy presentation adapters.

No intent policy lives here. The backend resolves turns against this contract.
"""
import streamlit as st
from geoworld_open.client.studio_request import StudioTaskContext, StudioBuildContext


def task_context():
    value = st.session_state.get("studio_task_context")
    if value is None:
        # One-time migration for compatibility tools and existing browser sessions.
        pending = st.session_state.get("studio_pending_build")
        value = StudioTaskContext(
            active_task="seismic" if st.session_state.get("studio_active_context") == "seismic" else "none",
            active_seismic_dataset_id=st.session_state.get("seismic_dataset_id"),
            build=StudioBuildContext(**pending) if pending else None,
        )
        st.session_state["studio_task_context"] = value
    return value


def commit_build(response, turns):
    if not isinstance(response.get("geospec"), dict):
        return
    previous = task_context()
    errors = [issue["message"] for issue in response.get("issues", [])
              if issue.get("severity") == "error"]
    build = StudioBuildContext(
        geospec=response["geospec"], turns=turns if len(turns) <= 20 else [turns[0], *turns[-19:]], valid=bool(response.get("valid")),
        confirmation_required=bool(response.get("confirmation_required")),
        degraded=bool(response.get("degraded")), interpretation_mode=response.get("interpretation_mode"),
    )
    st.session_state["studio_task_context"] = previous.model_copy(update={
        "active_task": "build", "build": build,
        "unresolved_clarification": errors[0] if errors else None,
        "execution_allowed": build.valid and not build.confirmation_required,
    })
    st.session_state["studio_pending_build"] = build.model_dump(exclude={"valid"})


def commit_seismic(dataset_id, *, view=None, conversation_id=None):
    previous = task_context()
    changed = previous.active_seismic_dataset_id != dataset_id
    st.session_state["studio_task_context"] = previous.model_copy(update={
        "active_task": "seismic", "active_seismic_dataset_id": dataset_id,
        "seismic_view": view if view is not None else (None if changed else previous.seismic_view),
        "seismic_conversation_id": conversation_id or (None if changed else previous.seismic_conversation_id),
    })
