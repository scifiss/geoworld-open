"""PUBLIC_SDK_INFRA: shared session conversation and HTTP-only Studio presentation.

Capability selection belongs to the protected backend. These helpers only adapt
its existing decisions, job results and SeismicExplorerState to one UI surface.
"""
from __future__ import annotations

import streamlit as st

from geoworld_open.client import GeoWorldClientError
from geoworld_open.studio_request import submit_request
from geoworld_open.studio_seismic import (
    _response_parts, activate_dataset, catalog_warning_message,
)


def append_message(role, content):
    st.session_state.setdefault("assistant_history", []).append({"role": role, "content": content})


def sync_history():
    """Adapt existing server history and completed results without claiming persistence."""
    _, _, state = _response_parts(st.session_state.get("seismic_response"))
    if state is not None:
        history = state.get("visible_history", []) if isinstance(state, dict) else state.visible_history
        identity = state.get("conversation_id") if isinstance(state, dict) else state.conversation_id
        seen = st.session_state.setdefault("assistant_seismic_seen", [])
        for index, turn in enumerate(history):
            user = turn.get("user_text") if isinstance(turn, dict) else turn.user_text
            summary = turn.get("assistant_summary") if isinstance(turn, dict) else turn.assistant_summary
            token = (identity, index, user, summary)
            if token in seen:
                continue
            messages = st.session_state.setdefault("assistant_history", [])
            if not messages or messages[-1] != {"role": "user", "content": user}:
                append_message("user", user)
            append_message("assistant", summary)
            seen.append(token)
    job = st.session_state.get("last_job")
    job_id = st.session_state.get("last_job_id")
    seen_jobs = st.session_state.setdefault("assistant_job_seen", [])
    if job_id and job_id not in seen_jobs and job is not None and job.result is not None:
        prompt = st.session_state.get("last_submitted_prompt")
        messages = st.session_state.setdefault("assistant_history", [])
        if prompt and not any(message == {"role": "user", "content": prompt} for message in messages):
            append_message("user", prompt)
        if job.result.geospec and job.result.intent in {"scenario_generation", "build_model"}:
            layers = job.result.geospec.get("geology", {}).get("layers", [])
            co2 = job.result.geospec.get("petrophysics", {}).get("co2_plume", {})
            carbonate = next((layer.get("porosity") for layer in layers
                              if layer.get("lithology") == "carbonate"), None)
            message = f"Generated {len(layers)}-layer synthetic model."
            if co2.get("enabled"):
                message += " CO₂ plume in sand;"
            if carbonate is not None:
                message += f" carbonate porosity {carbonate:.2f}."
            message += " Results ready."
            append_message("assistant", message)
        else:
            append_message("assistant", job.result.answer)
        seen_jobs.append(job_id)
    elif job_id and job_id not in seen_jobs and job is not None and job.status == "failed":
        from geoworld_open.studio_runtime import friendly_job_error
        append_message("assistant", friendly_job_error(job.error))
        seen_jobs.append(job_id)


def attach_seismic(api, uploaded):
    """Use the existing secure validation API; keep only its returned context."""
    uploaded.seek(0)
    record = api.upload_seismic(uploaded.name, uploaded)
    if record.status != "ready" or record.dataset is None:
        raise GeoWorldClientError(record.validation_message or "The file could not be attached. Try another SEG-Y file.")
    activate_dataset(record.dataset)
    st.session_state["manual_tools"] = False
    st.session_state.pop("seismic_unified_request", None)
    st.session_state["assistant_notice"] = f"Attached: {record.display_filename}"
    append_message("assistant", f"Attached {record.display_filename}. You can now request a section, trace or analysis.")


def render_composer(api):
    context = st.session_state.get("seismic_context_dataset")
    if context is not None:
        prefix = "Example: " if context.format == "synthetic" else "Attached: "
        st.caption(prefix + context.display_name)
    with st.container(key="assistant_composer"):
        # Keep the draft through unrelated widget reruns before Send is clicked.
        prompt = st.text_area(
            "Message GeoWorld", key="assistant_prompt", height=120,
            placeholder="Ask a question, describe a model, or inspect an attached file…",
        )
        sent = st.button("Send", type="primary", use_container_width=True, key="assistant_send")
        with st.expander("Attach", expanded=False):
            uploaded = st.file_uploader("Seismic file (SEG-Y)", type=["sgy", "segy"], key="assistant_attachment")
            st.caption("Choose a SEG-Y file, then click Upload and attach to validate and use it.")
            if st.button("Upload and attach", disabled=uploaded is None, key="assistant_attach"):
                try:
                    attach_seismic(api, uploaded)
                    st.rerun()
                except GeoWorldClientError as exc:
                    st.session_state["assistant_notice"] = catalog_warning_message(str(exc))
        with st.expander("Examples", expanded=False):
            st.caption("Try “show Marmousi 1”, “build shale–sand–shale”, or “inspect my uploaded LAS logs”.")
            if st.button("Explore a synthetic horizon example", key="assistant_open_examples"):
                try:
                    st.session_state["assistant_examples"] = api.list_horizon_benchmarks().datasets
                except GeoWorldClientError as exc:
                    st.session_state["assistant_notice"] = str(exc)
            examples = st.session_state.get("assistant_examples", [])
            if examples:
                by_id = {item.dataset_id: item for item in examples}
                choice = st.selectbox(
                    "Synthetic benchmark case", list(by_id),
                    format_func=lambda identity: by_id[identity].display_name, key="assistant_example_choice",
                )
                if st.button("Open example", key="assistant_use_example"):
                    activate_dataset(by_id[choice], demo=True)
                    st.session_state["manual_tools"] = False
                    st.session_state.pop("seismic_unified_request", None)
                    append_message("user", "Open the synthetic horizon example: " + by_id[choice].display_name)
                    append_message("assistant", "Synthetic benchmark opened. Select a starting position and bounded time window to evaluate Horizon V0.")
                    st.rerun()
    if sent and prompt.strip():
        st.session_state["manual_tools"] = False
        st.session_state["studio_previous_context"] = st.session_state.get("studio_active_context", "request")
        append_message("user", prompt.strip())
        decision = submit_request(api, prompt.strip())
        if decision is not None:
            from geoworld_open.studio_context import task_context
            current = task_context()
            st.session_state["studio_active_context"] = (
                "seismic" if decision.route == "seismic_explorer" or
                (decision.route == "ask_question" and current.active_task == "seismic") else "request"
            )
            if (decision.route != "seismic_explorer" or "seismic_unified_request" not in st.session_state) and not (
                decision.route == "build_model" and decision.semantic_action and
                decision.semantic_action.kind in {"new_build", "patch_build"}
            ):
                append_message("assistant", decision.message)
            # Widget state is cleared before the next widget is instantiated.
            # Clearing the live text_area key here would raise in Streamlit 1.65.
            st.session_state["assistant_clear_composer"] = True
            st.rerun()
        else:
            append_message("assistant", st.session_state["studio_request_error"])


def render_assistant_studio(api, render_active, render_manual):
    if st.session_state.pop("assistant_clear_composer", False):
        st.session_state["assistant_prompt"] = ""
    st.session_state.setdefault("studio_active_context", "request")
    st.session_state.setdefault("studio_pending_build", None)
    st.session_state.setdefault("assistant_history", [])
    st.session_state.setdefault("assistant_seismic_seen", [])
    st.session_state.setdefault("assistant_job_seen", [])
    st.markdown("""
        <style>
        .st-key-assistant_workspace_layout > div > [data-testid="stHorizontalBlock"] {align-items: stretch;}
        .st-key-assistant_workspace_layout > div > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child > div {height: 100%;}
        [data-testid="stLayoutWrapper"]:has(> .st-key-assistant_panel) {height: 100%;}
        .st-key-assistant_panel {position: sticky; top: 1rem; height: fit-content !important; flex: 0 1 auto !important;}
        [data-testid="stLayoutWrapper"]:has(> .st-key-assistant_history), .st-key-assistant_history {
            height: clamp(160px, calc(100dvh - 740px), 420px) !important;
            max-height: clamp(160px, calc(100dvh - 740px), 420px) !important;
            min-height: 0 !important; overflow-y: auto; flex: 0 1 auto !important;
        }
        .st-key-assistant_composer {position: sticky; bottom: 0; z-index: 5;
            background: var(--background-color, white); padding-top: .35rem;}
        @media (max-width: 900px) {
          .st-key-assistant_workspace_layout > div > [data-testid="stHorizontalBlock"] {flex-wrap: wrap;}
          .st-key-assistant_workspace_layout > div > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
            min-width: 100%; flex: 1 1 100%;
          }
          .st-key-assistant_panel {position: static;}
        }
        </style>
    """, unsafe_allow_html=True)
    with st.container(key="assistant_workspace_layout"):
        main, assistant = st.columns([2.15, 1], gap="large")
        # Process controls before rendering the workspace so explicit submission
        # can invalidate scientific preparation widget state safely.
        with assistant:
            with st.container(key="assistant_panel"):
                st.markdown("### GeoWorld Assistant")
                st.caption("Conversation is held in this browser session. Persistent project memory is not available yet.")
                history_slot = st.container(key="assistant_history", height=420, border=True)
                notice_slot = st.container()
                render_composer(api)
        with main:
            with st.expander("Advanced: manual tools / debugging", expanded=bool(st.session_state.get("manual_tools"))):
                manual = st.checkbox("Use compatibility tools", key="manual_tools")
                if manual:
                    render_manual(api)
            if not manual:
                render_active(api)
        sync_history()
        with history_slot:
            messages = st.session_state.get("assistant_history", [])
            if not messages:
                st.info("Tell GeoWorld what you want to understand or create. Attach a file when your request uses seismic data.")
            for message in messages:
                with st.chat_message(message["role"]):
                    st.write(message["content"])
        with notice_slot:
            if notice := st.session_state.pop("assistant_notice", None):
                st.info(notice)
