"""PUBLIC_SDK_INFRA: one request entry; intelligence stays behind HTTP."""
import streamlit as st

from geoworld_open.client import GeoWorldClientError, JobCreateRequest
from geoworld_open.studio_llm import execution_model_line, preparation_model_line


def render_build(api, submit, prompt, *, prepare=False, prepare_only=False):
    st.subheader("Prepared model")
    if st.button("Prepare model") or prepare:
        st.session_state.pop("prepared_preview", None)
        try:
            st.session_state["prepared_preview"] = api.preview_geospec(prompt=prompt)
        except GeoWorldClientError as exc:
            st.error(str(exc))
    preview = st.session_state.get("prepared_preview")
    if not preview:
        return
    st.caption(preparation_model_line(preview))
    valid = bool(preview.get("valid") and isinstance(preview.get("geospec"), dict))
    if not valid:
        st.warning("No valid model prepared. Review the interpretation and try again.")
    with st.expander("Prepared model / assumptions", expanded=True):
        for assumption in (preview.get("geospec") or {}).get("assumptions", []):
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
    if st.button("Run model", disabled=not valid or not confirmed or prepare_only):
        try:
            submit(api, JobCreateRequest(prompt=prompt, mode_hint="build_model", geospec=preview["geospec"],
                interpretation_mode=preview.get("interpretation_mode") or preview.get("parser_mode"),
                interpretation_degraded=bool(preview.get("degraded")), degraded_fallback_confirmed=confirmed))
        except GeoWorldClientError as exc:
            st.error(str(exc))


def render_request(api, submit, render_las):
    prompt = st.text_area("What would you like GeoWorld to do?", key="prompt", height=130,
        placeholder="Explain seismic imaging, build shale–sand–shale, or show Marmousi 1…")
    st.caption("Describe the task here. GeoWorld selects the tool; you review the preparation before a simulation runs.")
    with st.expander("What can I demo here?"):
        st.markdown("**Questions:** Explain what a seismic survey can and cannot tell us.\n\n"
                    "**Simple model:** Build shale, high-porosity sand, and shale with one dipping fault. Generate Vp, Vs, density, impedance and reflectivity.\n\n"
                    "**Benchmark preview:** Show Marmousi 1. Inspect Vp or density and crop in metres; this does not run RTM.\n\n"
                    "**Well logs:** Inspect my uploaded LAS logs. Use GW-DEMO-01 and GW-DEMO-02.\n\n"
                    "Marmousi 2 and Deepwave numerical runs require the enabled local backend and installed data. "
                    "The first Marmousi 1 preview may take a few seconds to download and verify its published files.")
    if st.button("Interpret request", type="primary", disabled=not prompt.strip()):
        for key in ("studio_decision", "studio_prepare_attempted", "studio_request_error", "prepared_preview",
                    "reference_preview", "rtm_preview", "marmousi_interpretation", "marmousi_base", "marmousi_preview",
                    "marmousi_load_error", "unified_fallback_confirmed", "rtm_model_approved"):
            st.session_state.pop(key, None)
        st.session_state["studio_request_prompt"] = prompt
        try:
            with st.spinner("Interpreting your request with the configured AI…"):
                st.session_state["studio_decision"] = api.interpret_studio(prompt)
        except GeoWorldClientError as exc:
            st.session_state["studio_request_error"] = str(exc)
    if prompt != st.session_state.get("studio_request_prompt"):
        if st.session_state.get("studio_decision"):
            st.info("Request edited. Interpret it again before preparing or running. Your saved result is unchanged.")
        return
    if st.session_state.get("studio_request_error"):
        st.error(st.session_state["studio_request_error"])
    decision = st.session_state.get("studio_decision")
    if decision is None:
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
        st.caption("AI interprets language; validated data loaders and numerical tools produce the model and images.")
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
    elif decision.route == "model_rtm":
        from geoworld_open.studio_rtm import render_rtm_workspace
        render_rtm_workspace(api, submit, prompt=prompt, auto_prepare=prepare, prepare_only=prepare_only)
    elif decision.route == "build_model":
        render_build(api, submit, prompt, prepare=prepare, prepare_only=prepare_only)
    elif decision.route == "las_quicklook":
        render_las(api)
    elif decision.route == "ask_question":
        if prepare_only:
            st.info("Question workflow selected. No answer job submitted because you requested preparation only.")
        elif prepare or st.button("Answer again"):
            try:
                submit(api, JobCreateRequest(prompt=prompt, mode_hint="ask_question"))
            except GeoWorldClientError as exc:
                st.error(str(exc))
