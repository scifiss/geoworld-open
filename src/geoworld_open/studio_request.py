"""PUBLIC_SDK_INFRA: one request entry; intelligence stays behind HTTP."""
import streamlit as st

from geoworld_open.client import GeoWorldClientError, JobCreateRequest
from geoworld_open.studio_llm import execution_model_line, preparation_model_line


def small_model_can_run(preview, *, prepare_only=False):
    """UI convenience gate; the backend still validates and limits the job."""
    if prepare_only or not preview.get("valid") or preview.get("confirmation_required") or preview.get("degraded"):
        return False
    spec = preview.get("geospec") or {}
    grid = spec.get("grid") or {}
    layers = (spec.get("geology") or {}).get("layers") or []
    nx, nz = grid.get("nx"), grid.get("nz")
    return (grid.get("dimension") == "2d" and type(nx) is int and type(nz) is int
            and nx <= 400 and nz <= 240 and nx * nz <= 100_000
            and 1 <= len(layers) <= 6)


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
    decision = st.session_state.get("studio_decision")
    if prepare and (decision is None or decision.action != "run_prepared_build"):
        st.session_state["studio_build_attempt_error"] = True
        from geoworld_open.studio_context import task_context
        build = task_context().build
        pending = build.model_dump() if build else None
        decision = st.session_state.get("studio_decision")
        continuing = bool(prepare and pending and decision and decision.continues_build)
        try:
            if decision and decision.build_spec is not None:
                evidence = {"semantic_action": decision.semantic_action} if decision.semantic_action else {}
                response = api.preview_geospec(geospec=decision.build_spec, **evidence)
                response["interpretation_mode"] = (
                    "deterministic_context" if decision.semantic_action and
                    decision.semantic_action.kind == "prepare_build" else "pydantic_ai_semantic_action"
                )
                response["llm"] = decision.llm
            elif continuing:
                response = api.preview_geospec(
                    geospec=pending["geospec"], follow_up=prompt,
                    prior_turns=pending["turns"],
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
                commit_build(response, turns, source_action=decision.semantic_action
                    if decision and decision.semantic_action and decision.semantic_action.kind == 'new_build' else None,
                    source_integrity=decision.replay_integrity if decision else None)
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
                retained = st.session_state.get('studio_build_completed_job')
                unchanged_completed = bool(retained and retained.result and
                    retained.result.geospec == response.get('geospec') and decision and
                    decision.action in {'prepare_build', 'run_prepared_build', 'patch_build'})
                if not unchanged_completed and not (decision and decision.semantic_action and
                        decision.semantic_action.kind in {"new_build", "patch_build"} and
                        small_model_can_run(response, prepare_only=prepare_only)):
                    append_message("assistant", "Model prepared. Review its assumptions and run when ready.")
    preview = st.session_state.get("prepared_preview")
    if not preview:
        return
    from geoworld_open.studio_context import task_context
    current = task_context()
    valid = bool(current.build and current.build.valid
                 and not st.session_state.get("studio_build_attempt_error"))
    if not valid:
        st.warning("No valid model prepared. Review the interpretation and try again.")
    confirmed = not preview.get("confirmation_required", False)
    if not confirmed:
        confirmed = st.checkbox("I reviewed this limited deterministic interpretation and want to run it", key="unified_fallback_confirmed")
    from geoworld_open.studio_context import task_context
    current = task_context()
    if current.build and not st.session_state.get("studio_build_attempt_error"):
        st.session_state["studio_task_context"] = current.model_copy(update={
            "execution_allowed": valid and confirmed,
        })
    requested_run = bool(prepare and decision and decision.action == "run_prepared_build")
    job = st.session_state.get('last_job')
    if not (job and job.status == 'succeeded' and job.result and job.result.geospec
            and job.result.intent in {'scenario_generation','build_model'}):
        job = st.session_state.get('studio_build_completed_job')
    completed = bool(job and job.status == 'succeeded' and job.result and job.result.geospec
                     and job.result.intent in {'scenario_generation','build_model'})
    same_inputs = bool(completed and current.build and job.result.geospec == current.build.geospec
        and (st.session_state.get('studio_model_completed_revision') ==
            (st.session_state.get('studio_request_serial',0), st.session_state.get('studio_auto_edit_serial',0))
            or decision and decision.action in {'prepare_build','run_prepared_build','patch_build'}))
    serial = st.session_state.get("studio_request_serial", 0)
    edit_serial = st.session_state.get("studio_auto_edit_serial", 0)
    auto_key = (serial, edit_serial)
    auto_requested = bool(
        decision and decision.semantic_action and
        decision.semantic_action.kind in {"new_build", "patch_build"} and
        prepare and not edit_serial and small_model_can_run(preview, prepare_only=prepare_only) and
        st.session_state.get("studio_auto_submitted") != auto_key
    )
    def run():
        st.session_state['studio_auto_submitted'] = auto_key
        try:
            submit(api, JobCreateRequest(prompt="\n".join(current.build.turns) if requested_run and current.build else prompt, mode_hint="build_model", geospec=current.build.geospec,
                interpretation_mode=current.build.interpretation_mode or preview.get("parser_mode"),
                interpretation_degraded=current.build.degraded, degraded_fallback_confirmed=confirmed))
            finished = st.session_state.get('last_job')
            if finished and finished.status == 'succeeded' and finished.result and finished.result.geospec == current.build.geospec:
                st.session_state['studio_model_completed_revision'] = (serial, edit_serial)
                st.session_state['studio_build_completed_job'] = finished
                st.rerun()
        except GeoWorldClientError as exc:
            st.error(str(exc))
            from geoworld_open.studio_assistant import append_message
            append_message("assistant", str(exc))
    if (requested_run or auto_requested) and valid and confirmed and not prepare_only:
        run()
        return
    from geoworld_open.studio_scientific_workspace import workspace_tabs, assumption_rows
    def inputs():
        from geoworld_open.studio_model_preview import render_prepared_geometry
        render_prepared_geometry(api, preview)
        assumptions = (preview.get('model_preview') or {}).get('assumptions_table')
        if assumptions is None:
            assumptions = assumption_rows(preview.get('assumptions') or preview.get('geospec',{}).get('assumptions',[]))
        if assumptions:
            st.markdown('**Recorded assumptions**')
            st.table(assumptions)
        if not same_inputs:
            st.info('Edited inputs describe a new experiment; saved results belong to the previous inputs.' if completed else 'Model prepared and validated. Run simulation to calculate results.')
            if st.button('Run simulation', type='primary', disabled=not valid or not confirmed):
                run()
        else:
            st.caption('Completed experiment · apply changed inputs to prepare a new experiment.')
    if completed:
        from geoworld_open.studio_legacy_model import render_legacy_model
        from geoworld_open.studio_presentation import DisplayOptions
        render_legacy_model(api, job.job_id, job.result, DisplayOptions(
            fit_figures=st.session_state.get('display_fit_figures',True),
            figure_px=st.session_state.get('display_figure_px',880)),
                            render_inputs=inputs, pending=not same_inputs)
    else:
        st.subheader('Scientific workspace · prepared model')
        model, results, evidence, advanced = workspace_tabs()
        with model:
            inputs()
        with results:
            st.info('No simulation has completed for these inputs.')
        with evidence:
            st.caption('Numerical checks and downloads appear after execution.')
        with advanced:
            st.caption(preparation_model_line(preview))
            st.json(preview.get('geospec'), expanded=False)
            st.json({'full_preparation_assumptions':preview.get('assumptions',[])},expanded=False)


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
    st.session_state["studio_previous_decision"] = previous_decision
    st.session_state["studio_previous_request_prompt"] = st.session_state.get("studio_request_prompt", "")
    if previous_decision and previous_decision.route == "ask_question":
        previous_decision = st.session_state.get("studio_workspace_decision")
    preserving = decision.route in {"ask_question", "blocked"} or decision.action in {"continue_specialized_workflow", "run_prepared_build"}
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
    if decision.route == "scientific_workflow" and decision.scientific:
        from geoworld_open.client.scientific_workflow import ScientificExperimentContext
        update.update(active_task="scientific", scientific=ScientificExperimentContext(
            preparation_id=decision.scientific.preparation_id, goal=decision.scientific.goal,
            completed_job_id=working.scientific.completed_job_id if working.scientific else None))
    if decision.action == "clarification_required" and decision.semantic_action is not None:
        update.update(pending_semantic_action=decision.semantic_action, unresolved_clarification=decision.message, execution_allowed=False)
    if decision.route == "seismic_explorer":
        update["active_task"] = "seismic"
    elif decision.route not in {"ask_question", "blocked", "build_model", "scientific_workflow"}:
        update.update(active_task="specialized", specialized_route=decision.route)
    st.session_state["studio_task_context"] = working.model_copy(update=update)
    st.session_state["studio_request_prompt"] = prompt
    st.session_state["studio_decision"] = decision
    st.session_state["studio_request_serial"] = st.session_state.get("studio_request_serial", 0) + 1
    st.session_state["studio_auto_edit_serial"] = 0
    if decision.route == "seismic_explorer":
        command = decision.command or seismic_workspace_command(prompt)
        if command:
            st.session_state["seismic_unified_request"] = command
    return decision


def render_request(api, submit, render_las):
    """Render the accepted request without adding a workflow-specific composer."""
    from pydantic import ValidationError
    from geoworld_open.client.studio_request import StudioDecision

    prompt = st.session_state.get("studio_request_prompt", "")
    if st.session_state.get("studio_request_error"):
        st.error(st.session_state["studio_request_error"])
    decision = st.session_state.get("studio_decision")
    if decision is None:
        return
    try:
        decision = StudioDecision.model_validate(
            decision.model_dump(mode="python")
            if isinstance(decision, StudioDecision)
            else decision
        )
    except (ValidationError, TypeError, ValueError):
        st.error("The Studio decision is invalid and cannot be rendered or executed. Please submit the request again.")
        return
    if decision.llm and decision.route not in {'build_model','scientific_workflow'}:
        st.caption(execution_model_line(decision.llm, purpose="Request understanding"))
    if decision.route == "blocked":
        st.warning(decision.message)
        return
    if decision.route == "scientific_workflow":
        from geoworld_open.studio_scientific import render_scientific_request
        render_scientific_request(api, submit, decision)
        return
    if getattr(decision, "evidence_assessment", None) and not getattr(decision, "investigation_plan", None):
        # The single Assistant already contains this answer. Keep the active
        # numerical workspace separate from the latest conversational response.
        return
    if getattr(decision, "investigation_plan", None):
        plan = decision.investigation_plan
        st.subheader("Plan readiness")
        st.write(plan.readiness.title())
        if plan.readiness in {"blocked", "unsupported"}:
            st.warning(
                "This plan cannot currently be executed. Reusable individual steps do not make the overall investigation executable."
            )
        st.subheader("Understanding")
        st.write(plan.understanding)
        st.subheader("Planning objectives")
        for item in plan.objectives:
            st.write(f"- {item}")
        if plan.requested_products:
            st.subheader("Requested products")
            for item in plan.requested_products:
                st.write(f"- {item}")
        st.subheader("Available scientific evidence")
        if plan.evidence:
            for item in plan.evidence:
                st.markdown(f"**{item.kind.replace('_', ' ').title()} · {item.status.replace('_', ' ').title()}**")
                st.write(item.summary)
        else:
            st.write("No verified scientific evidence was available for this request.")
        if plan.findings:
            st.subheader("What the evidence supports")
            for finding in plan.findings:
                st.markdown(f"**{finding.claim_type.replace('_', ' ').title()}** — {finding.statement}")
        st.subheader("Recommended investigation")
        for index, step in enumerate(plan.steps, start=1):
            st.markdown(f"**{index}. {step.method}** · {step.readiness.title()}")
            st.write(step.rationale)
            if step.assumptions:
                st.caption("Assumptions: " + "; ".join(step.assumptions))
            if step.limitations:
                st.caption("Limitations: " + "; ".join(step.limitations))
            if step.required_evidence:
                st.caption("Needed: " + "; ".join(step.required_evidence))
            if step.expected_products:
                st.caption("Expected: " + "; ".join(step.expected_products))
        if plan.competing_explanations:
            st.subheader("Competing explanations")
            for item in plan.competing_explanations:
                st.write(f"- {item}")
        if plan.uncertainties:
            st.subheader("Uncertainty and limitations")
            for item in plan.uncertainties:
                st.write(f"- {item}")
        if plan.clarification_questions:
            st.subheader("Clarification")
            for item in plan.clarification_questions:
                st.write(f"- {item}")
        with st.expander("Evidence references and validation detail"):
            for item in plan.evidence:
                st.write(f"{item.evidence_id}: {item.source_ref or 'no source reference'}")
                if item.metadata:
                    st.write(item.metadata)
            for step in plan.steps:
                st.write(f"{step.step_id}: " + (", ".join(step.validation) or "No validation defined"))
        st.caption("Planning only. No scientific job was started; no candidate was activated.")
        return
    if decision.route == 'build_model':
        prepare = not st.session_state.get('studio_prepare_attempted', False)
        st.session_state['studio_prepare_attempted'] = True
        render_build(api, submit, prompt, prepare=prepare, prepare_only=decision.interpretation.prepare_only)
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
        if context.active_task in {"build", "specialized", "scientific"} and saved:
            st.session_state["studio_decision"] = saved
            st.session_state["studio_request_prompt"] = st.session_state.get("studio_workspace_prompt", "")
            try:
                render_request(api, submit, render_las)
            finally:
                st.session_state["studio_decision"] = decision
                st.session_state["studio_request_prompt"] = prompt
