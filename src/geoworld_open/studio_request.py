"""PUBLIC_SDK_INFRA: one request entry; intelligence stays behind HTTP."""
import streamlit as st

from geoworld_open.client import GeoWorldClientError, JobCreateRequest
from geoworld_open.studio_llm import execution_model_line, preparation_model_line


def seismic_workspace_command(prompt: str) -> str | None:
    """Return a supported deterministic Explorer command embedded in a routed request."""
    text = prompt.strip()
    lower = text.casefold()
    controls = (
        "inline", "crossline", "time slice", "depth slice", "trace ",
        "zoom ", "spectrum", "histogram", "statistics", "amplitude range",
        "sample interval", "sample count", "vertical domain", "what kind of data",
        "data of the sgy",
    )
    return text if any(control in lower for control in controls) else None


def render_build(api, submit, prompt, *, prepare=False, prepare_only=False):
    st.subheader("Prepared model")
    clicked = st.button("Prepare model")
    decision = st.session_state.get("studio_decision")
    if clicked or (prepare and (decision is None or decision.action != "run_prepared_build")):
        st.session_state["studio_build_attempt_error"] = True
        from geoworld_open.studio_context import task_context
        build = task_context().build
        pending = build.model_dump() if build else None
        decision = st.session_state.get("studio_decision")
        continuing = bool(prepare and pending and decision and decision.continues_build)
        try:
            if continuing:
                response = api.preview_geospec(
                    geospec=pending["geospec"], follow_up=prompt,
                    prior_turns=pending["turns"],
                )
            elif clicked and pending and pending["turns"][-1] == prompt:
                response = api.preview_geospec(
                    geospec=pending["geospec"], prior_turns=pending["turns"],
                )
            else:
                response = api.preview_geospec(prompt=prompt)
        except GeoWorldClientError as exc:
            if previous := st.session_state.get("studio_previous_task_context"):
                st.session_state["studio_task_context"] = previous
            st.error(str(exc))
            from geoworld_open.studio_assistant import append_message
            append_message("assistant", str(exc))
            if st.session_state.get("studio_previous_context") == "seismic":
                st.session_state["studio_active_context"] = "seismic"
                st.session_state["assistant_notice"] = str(exc)
                st.rerun()
        else:
            if continuing:
                response["confirmation_required"] = bool(
                    response.get("confirmation_required") or pending.get("confirmation_required")
                )
                response["degraded"] = bool(response.get("degraded") or pending.get("degraded"))
                response["interpretation_mode"] = pending.get("interpretation_mode") or response.get("interpretation_mode")
            if isinstance(response.get("geospec"), dict):
                turns = [*pending["turns"], prompt] if continuing else [prompt]
                from geoworld_open.studio_context import commit_build
                commit_build(response, turns)
                st.session_state["prepared_preview"] = response
                st.session_state["studio_build_attempt_error"] = False
            elif st.session_state.get("prepared_preview") is None:
                st.session_state["prepared_preview"] = response
            from geoworld_open.studio_assistant import append_message
            if not response.get("valid"):
                errors = [issue.get("message", "") for issue in response.get("issues", [])
                          if isinstance(issue, dict) and issue.get("severity") == "error"]
                if errors:
                    append_message("assistant", errors[0])
                    st.warning(errors[0])
                    if not isinstance(response.get("geospec"), dict) and st.session_state.get("studio_previous_context") == "seismic":
                        st.session_state["studio_active_context"] = "seismic"
                        st.session_state["assistant_notice"] = errors[0]
                        st.rerun()
            else:
                assumptions = list(dict.fromkeys(
                    response.get("assumptions") or (response.get("geospec") or {}).get("assumptions") or []
                ))
                summary = "Model prepared for review."
                if assumptions:
                    summary += " Assumptions before execution:\n" + "\n".join(
                        f"- {item}" for item in assumptions
                    )
                append_message("assistant", summary)
    preview = st.session_state.get("prepared_preview")
    if not preview:
        return
    st.caption(preparation_model_line(preview))
    from geoworld_open.studio_context import task_context
    current = task_context()
    valid = bool(current.build and current.build.valid
                 and not st.session_state.get("studio_build_attempt_error"))
    if not valid:
        st.warning("No valid model prepared. Review the interpretation and try again.")
    with st.expander("Prepared model / assumptions", expanded=True):
        st.write("**Assumptions before execution**")
        for assumption in list(dict.fromkeys(
            preview.get("assumptions") or (preview.get("geospec") or {}).get("assumptions") or []
        )):
            st.write(assumption)
        for issue in preview.get("issues") or []:
            st.write(issue.get("message", "") if isinstance(issue, dict) else str(issue))
        if preview.get("diagnostic"):
            st.caption(preview["diagnostic"])
    with st.expander("Advanced: validated model specification"):
        st.json(preview.get("geospec"))
    confirmed = not preview.get("confirmation_required", False)
    if not confirmed:
        confirmed = st.checkbox("I reviewed this limited deterministic interpretation and want to run it", key="unified_fallback_confirmed")
    if prepare_only:
        st.info("Prepared only, as requested. Submit a new request to run it.")
    from geoworld_open.studio_context import task_context
    current = task_context()
    if current.build and not st.session_state.get("studio_build_attempt_error"):
        st.session_state["studio_task_context"] = current.model_copy(update={
            "execution_allowed": valid and confirmed,
        })
    requested_run = bool(prepare and decision and decision.action == "run_prepared_build")
    clicked_run = st.button("Run model", disabled=not valid or not confirmed or prepare_only)
    if (clicked_run or requested_run) and valid and confirmed and not prepare_only:
        try:
            submit(api, JobCreateRequest(prompt="\n".join(current.build.turns) if requested_run and current.build else prompt, mode_hint="build_model", geospec=current.build.geospec,
                interpretation_mode=current.build.interpretation_mode or preview.get("parser_mode"),
                interpretation_degraded=current.build.degraded, degraded_fallback_confirmed=confirmed))
        except GeoWorldClientError as exc:
            st.error(str(exc))


def submit_request(api, prompt):
    """Explicit submission only; the protected backend remains the route authority."""
    from geoworld_open.studio_context import task_context
    working = task_context()
    context = {"context": working}
    if working.build:
        context["has_pending_build"] = True
    if working.active_seismic_dataset_id:
        context["active_seismic_dataset_id"] = working.active_seismic_dataset_id
    try:
        with st.spinner("GeoWorld is understanding your request…"):
            decision = api.interpret_studio(prompt, **context)
    except GeoWorldClientError as exc:
        st.session_state["studio_request_error"] = str(exc)
        return None
    previous_decision = st.session_state.get("studio_decision")
    if previous_decision and previous_decision.route == "ask_question":
        previous_decision = st.session_state.get("studio_workspace_decision")
    preserving = decision.route == "ask_question" or decision.action in {"continue_specialized_workflow", "run_prepared_build"}
    if decision.route == "ask_question" and st.session_state.get("studio_decision") and st.session_state["studio_decision"].route != "ask_question":
        st.session_state["studio_workspace_decision"] = st.session_state["studio_decision"]
        st.session_state["studio_workspace_prompt"] = st.session_state.get("studio_request_prompt", "")
    for key in ([] if preserving else list(st.session_state)):
        if key.startswith("marmousi_"):
            st.session_state.pop(key, None)
    for key in ("studio_decision", "studio_prepare_attempted", "studio_request_error",
                "reference_preview", "rtm_preview", "marmousi_interpretation", "marmousi_base", "marmousi_preview",
                "marmousi_load_error", "unified_fallback_confirmed", "rtm_model_approved", "fwi_preview", "fwi_prompt",
                "configurable_fwi_conversation", "configurable_fwi_preview", "configurable_fwi_prompt",
                "seismic_unified_request"):
        if not preserving or key in {"studio_decision", "studio_prepare_attempted", "studio_request_error", "seismic_unified_request"}:
            st.session_state.pop(key, None)
    if decision.action == "continue_specialized_workflow":
        st.session_state["studio_prepare_attempted"] = True
        prompt = st.session_state.get("studio_workspace_prompt", st.session_state.get("studio_request_prompt", prompt))
        if previous_decision:
            decision = previous_decision.model_copy(update={"action": "continue_specialized_workflow"})
    if decision.action == "run_prepared_build":
        st.session_state["studio_build_attempt_error"] = False
    st.session_state["studio_previous_task_context"] = working
    update = {"last_action": decision.action}
    if decision.route == "seismic_explorer":
        update["active_task"] = "seismic"
    elif decision.route not in {"ask_question", "blocked", "build_model"}:
        update.update(active_task="specialized", specialized_route=decision.route)
    st.session_state["studio_task_context"] = working.model_copy(update=update)
    st.session_state["studio_request_prompt"] = prompt
    st.session_state["studio_decision"] = decision
    if decision.route == "seismic_explorer":
        command = decision.command or seismic_workspace_command(prompt)
        if command:
            st.session_state["seismic_unified_request"] = command
    return decision


def render_request(api, submit, render_las):
    """Render the accepted request without adding a workflow-specific composer."""
    prompt = st.session_state.get("studio_request_prompt", "")
    if st.session_state.get("studio_request_error"):
        st.error(st.session_state["studio_request_error"])
    decision = st.session_state.get("studio_decision")
    if decision is None or not hasattr(decision, "route"):
        return
    if decision.llm:
        st.caption(execution_model_line(decision.llm, purpose="Request understanding"))
    if decision.route == "blocked":
        st.warning(decision.message)
        return
    st.info(decision.message)
    prepare_only = decision.interpretation.prepare_only
    with st.expander("How GeoWorld understood the request"):
        st.write("Task: " + decision.interpretation.operation)
        if decision.interpretation.dataset:
            st.write("Model: " + decision.interpretation.dataset.replace("marmousi", "Marmousi "))
        st.write("Prepare only: " + ("yes" if prepare_only else "no"))
        st.caption(
            ("AI interpreted this request; " if decision.llm else "GeoWorld routed this request deterministically; ")
            + "validated data loaders and numerical tools produce models and images."
        )
    # Exactly once per explicit submission. Export, layout and other widget
    # reruns must not incur another interpretation or scientific execution.
    prepare = not st.session_state.get("studio_prepare_attempted", False)
    st.session_state["studio_prepare_attempted"] = True
    if decision.route == "marmousi_model":
        from geoworld_open.studio_marmousi import render_model_workspace
        render_model_workspace(api, submit, prompt=prompt, auto_prepare=prepare)
    elif decision.route == "deepwave_reference":
        from geoworld_open.studio_reference import render_reference_workspace
        render_reference_workspace(api, submit, prompt=prompt, auto_prepare=prepare)
    elif decision.route == 'bounded_fwi':
        from geoworld_open.studio_fwi import render_fwi_workspace
        render_fwi_workspace(api, submit, prompt=prompt, auto_prepare=prepare, prepare_only=prepare_only)
    elif decision.route == "configurable_marmousi_fwi":
        from geoworld_open.studio_configurable_fwi import render_workspace
        render_workspace(api, submit, prompt=prompt, auto_prepare=prepare,
                         prepare_only=prepare_only)
    elif decision.route in {"model_rtm", "model_forward"}:
        from geoworld_open.studio_rtm import render_rtm_workspace
        render_rtm_workspace(api, submit, prompt=prompt, auto_prepare=prepare, prepare_only=prepare_only,
                             operation='forward' if decision.route=='model_forward' else 'rtm')
    elif decision.route == "build_model":
        render_build(api, submit, prompt, prepare=prepare, prepare_only=prepare_only)
    elif decision.route == "las_quicklook":
        render_las(api)
    elif decision.route == "seismic_explorer":
        from geoworld_open.studio_seismic import render_seismic_explorer
        render_seismic_explorer(api)
    elif decision.route == "ask_question":
        if prepare_only:
            st.info("Question workflow selected. No answer job submitted because you requested preparation only.")
        elif prepare or st.button("Answer again"):
            try:
                submit(api, JobCreateRequest(prompt=prompt, mode_hint="ask_question"))
            except GeoWorldClientError as exc:
                st.error(str(exc))
                from geoworld_open.studio_assistant import append_message
                append_message("assistant", str(exc))

        from geoworld_open.studio_context import task_context
        context = task_context()
        saved = st.session_state.get("studio_workspace_decision")
        if context.active_task in {"build", "specialized"} and saved:
            st.session_state["studio_decision"] = saved
            st.session_state["studio_request_prompt"] = st.session_state.get("studio_workspace_prompt", "")
            try:
                render_request(api, submit, render_las)
            finally:
                st.session_state["studio_decision"] = decision
                st.session_state["studio_request_prompt"] = prompt
