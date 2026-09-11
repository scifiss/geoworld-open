"""Public GeoWorld Studio frontend backed by the official GeoWorld HTTP service.

This app intentionally contains presentation/client logic only. Protected reasoning,
knowledge, production physics, rendering, persistence, and user data remain behind the
private GeoWorld backend.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import streamlit as st
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from geoworld_open.client import (
    GeoWorldBackendClient,
    GeoWorldClientError,
    JobCreateRequest,
    JobResult,
    LASQuicklookSettings,
)
from geoworld_open.client.backend import backend_url_from_environment
from geoworld_open.studio_llm import (
    configured_model_lines,
    preparation_model_line,
    result_model_lines,
)
from geoworld_open.studio_presentation import (
    DisplayOptions,
    ReportFigure,
    build_clean_report,
    studio_export_controls,
    studio_display_css,
)
from geoworld_open.studio_runtime import (
    LAS_INVENTORY_NAME,
    LAS_OBSERVATION_NAME,
    LAS_QC_NAME,
    artifact_named,
    decode_json_object,
    encode_las_upload,
    friendly_job_error,
    health_diagnostic,
    human_citation_lines,
    inspect_las_header,
    las_form_signature,
    output_coverage_rows,
    provenance_lines,
    recommended_las_curves,
    sort_figure_artifacts,
)


st.set_page_config(page_title="GeoWorld Studio", page_icon="🌍", layout="wide")

EXAMPLES = {
    "Faulted reservoir": (
        "Build a shale-sand-shale reservoir with one dipping normal fault. "
        "Generate elastic properties and synthetic seismic. List assumptions."
    ),
    "Seismic + AVO": (
        "Build shale, high-porosity sand, low-porosity sand and shale. Add one dipping fault. "
        "Generate Vp, Vs, density, impedance, reflectivity, synthetic seismic and AVO stacks. "
        "List assumptions."
    ),
    "CO2 monitoring": (
        "Build a reservoir model with a CO2 plume. Show saturation, elastic response, synthetic seismic, "
        "and assumptions."
    ),
}

LAS_SAMPLE_DIR = PROJECT_ROOT / "examples" / "las"


def backend_url() -> str | None:
    return backend_url_from_environment()


def backend_timeout() -> float:
    raw = os.getenv("GEOWORLD_BACKEND_TIMEOUT_SECONDS", "120").strip()
    try:
        return float(max(30, min(300, int(raw))))
    except ValueError:
        return 120.0


def client(token: str | None = None) -> GeoWorldBackendClient:
    url = backend_url()
    if not url:
        raise GeoWorldClientError(
            "GEOWORLD_BACKEND_URL is not configured. Point this public frontend to the official GeoWorld backend."
        )
    return GeoWorldBackendClient(url, token=token, timeout=backend_timeout())


def clear_session() -> None:
    clear_last_result()
    for key in list(st.session_state):
        if key.startswith(("marmousi_", "studio_", "unified_")):
            st.session_state.pop(key, None)
    for key in (
        "access_token",
        "user_email",
        "prepared_geospec",
        "prepared_preview",
        "detected_intent",
        "auto_route_confirmed",
        "fallback_confirmed",
        "capability_catalog",
        "active_workspace",
        "las_form_signature",
        "rtm_preview", "rtm_prompt", "rtm_structured", "rtm_input_signature", "rtm_replay_id",
        "reference_prompt", "reference_preview", "reference_signature", "reference_debug", "reference_action",
        "reference_compute", "reference_use_gpu",
        "manual_tools", "manual_workspace", "saved_job_id", "prompt",
    ):
        st.session_state.pop(key, None)


def clear_last_result() -> None:
    for key in (
        "last_job", "last_job_id", "last_correlation_id",
        "last_submitted_prompt", "clean_report",
        "last_preparation_model", "last_result_models", "rtm_replay",
        "last_result_source",
    ):
        st.session_state.pop(key, None)


def render_auth() -> str | None:
    token = st.session_state.get("access_token")
    if token:
        return str(token)

    st.title("🌍 GeoWorld Studio")
    st.caption(
        "Natural-language geoscience workflows with a public client/standard layer and protected GeoWorld capabilities."
    )
    if not backend_url():
        st.error("Backend is not configured. Set `GEOWORLD_BACKEND_URL` and restart the app.")
        st.code("export GEOWORLD_BACKEND_URL=https://<official-geoworld-backend>")
        return None

    st.info("Sign in to use the official GeoWorld backend. Credentials and user data are not stored in geoworld-open.")
    mode = st.radio("Account", ["Login", "Register"], horizontal=True)
    email = st.text_input("Email", autocomplete="username")
    credential_input = st.text_input(
        "Password",
        type="password",
        autocomplete="current-password" if mode == "Login" else "new-password",
    )
    if st.button(mode, type="primary", disabled=not email.strip() or not credential_input):
        try:
            with st.spinner("Connecting to GeoWorld..."):
                auth = (
                    client().login(email.strip(), credential_input)
                    if mode == "Login"
                    else client().register(email.strip(), credential_input)
                )
            st.session_state["access_token"] = auth.access_token
            st.session_state["user_email"] = auth.user.email
            st.rerun()
        except GeoWorldClientError as exc:
            st.error(str(exc))
    return None


def poll_job(api: GeoWorldBackendClient, job_id: str, *, actual_stages=False, reference=False):
    from geoworld_open.studio_progress import progress_labels
    progress = st.empty()
    status = st.empty()
    timing = st.empty()
    for index in range(2440 if reference else 120):
        job = api.get_job(job_id)
        status.info(job.progress)
        detail = job.progress_detail
        if detail is not None:
            fraction, label, caption = progress_labels(detail, running=job.status == "running")
            progress.progress(fraction, text=label)
            timing.caption(caption)
        else:
            progress.empty()
            timing.caption("No completed-work counts reported yet; no percentage or ETA is inferred from elapsed time.")
        if job.status in {"succeeded", "failed"}:
            if job.status == "succeeded":
                progress.progress(100, text="Job finished · result saved")
                timing.empty()
                if job.result and job.result.grounding_status == "evidence_insufficient":
                    from geoworld_open.studio_qa import qa_outcome_message
                    status.warning(qa_outcome_message(job.result))
                else:
                    status.success("Result ready.")
            else:
                progress.empty()
                timing.empty()
                status.empty()
            return job
        time.sleep(3)
    raise GeoWorldClientError("Timed out while waiting for GeoWorld job completion")


def submit_and_wait(api: GeoWorldBackendClient, request: JobCreateRequest) -> None:
    created = api.submit_job(request)
    clear_last_result()
    preview = st.session_state.get("prepared_preview")
    if (
        request.geospec is not None
        and isinstance(preview, dict)
        and preview.get("geospec") == request.geospec
    ):
        # Bind the preview's evidence to this accepted job. Later edits, new
        # previews, and changes to service configuration must not relabel it.
        st.session_state["last_preparation_model"] = preparation_model_line(preview)
    # Bind presentation exports to the accepted request, not a later editor value.
    st.session_state["last_submitted_prompt"] = request.prompt
    st.session_state["last_job_id"] = created.job_id
    st.session_state["last_correlation_id"] = created.correlation_id
    st.session_state["last_result_source"] = "submitted"
    st.session_state["last_job"] = (poll_job(api, created.job_id, actual_stages=True, reference=True)
                                   if request.mode_hint == "deepwave_reference" else poll_job(api, created.job_id, actual_stages=True)
                                   if request.mode_hint == "model_rtm" else poll_job(api, created.job_id))


def load_json_artifact(
    api: GeoWorldBackendClient,
    job_id: str,
    artifacts,
    basename: str,
) -> dict[str, object] | None:
    artifact = artifact_named(artifacts, basename)
    if artifact is None:
        return None
    return decode_json_object(api.get_artifact(job_id, artifact.name))


def render_las_details(api: GeoWorldBackendClient, job_id: str, artifacts) -> None:
    """Present bounded LAS summaries returned by the protected backend."""

    try:
        inventory = load_json_artifact(api, job_id, artifacts, LAS_INVENTORY_NAME)
        qc = load_json_artifact(api, job_id, artifacts, LAS_QC_NAME)
        observation = load_json_artifact(api, job_id, artifacts, LAS_OBSERVATION_NAME)
    except (GeoWorldClientError, ValueError) as exc:
        st.warning(f"LAS details are unavailable: {exc}")
        return

    st.subheader("LAS inventory")
    wells = inventory.get("wells") if isinstance(inventory, dict) else None
    if isinstance(wells, list) and wells:
        rows = []
        for well in wells:
            if not isinstance(well, dict):
                continue
            depth = well.get("depth") if isinstance(well.get("depth"), dict) else {}
            curves = well.get("curves") if isinstance(well.get("curves"), list) else []
            rows.append(
                {
                    "Well": well.get("well_id") or well.get("well_name"),
                    "Source": well.get("source_filename"),
                    "MD unit": depth.get("converted_unit") or depth.get("unit_canonical"),
                    "Samples": depth.get("sample_count"),
                    "Curves": ", ".join(
                        str(curve.get("original_mnemonic"))
                        for curve in curves
                        if isinstance(curve, dict) and curve.get("original_mnemonic")
                    ),
                }
            )
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.info("The run did not return a readable LAS well inventory.")

    st.subheader("Quality control")
    if isinstance(qc, dict):
        metric_columns = st.columns(3)
        metric_columns[0].metric("Parsed", qc.get("files_successfully_parsed", 0))
        metric_columns[1].metric("Rejected", qc.get("files_rejected", 0))
        metric_columns[2].metric("MD unit", qc.get("common_depth_unit", "—"))
        warnings = qc.get("warnings")
        if isinstance(warnings, list) and warnings:
            with st.expander(f"QC warnings ({len(warnings)})"):
                for warning in warnings:
                    st.write(f"- {warning}")
        with st.expander("QC methods and transformations"):
            st.json(qc)
    else:
        st.info("The run did not return a readable LAS QC summary.")

    st.subheader("Observation summary")
    if isinstance(observation, dict):
        st.json(observation)
    else:
        st.info("The run did not return a readable observation summary.")


def render_las_workspace(api: GeoWorldBackendClient) -> None:
    st.subheader("LAS Quicklook")
    st.caption(
        "Upload LAS files for deterministic measured-depth inventory, QC, and multiwell quicklook plots. "
        "The protected backend performs all scientific parsing; no LLM is required."
    )

    sample_paths = [
        LAS_SAMPLE_DIR / "gw_demo_01_layered.las",
        LAS_SAMPLE_DIR / "gw_demo_02_layered.las",
    ]
    available_samples = [path for path in sample_paths if path.is_file()]
    if available_samples:
        with st.expander("Download sample LAS files"):
            columns = st.columns(len(available_samples))
            for column, path in zip(columns, available_samples):
                column.download_button(
                    f"Download {path.name}",
                    data=path.read_bytes(),
                    file_name=path.name,
                    mime="text/plain",
                    key=f"sample-{path.name}",
                    use_container_width=True,
                )

    uploaded = st.file_uploader(
        "LAS files",
        type=["las"],
        accept_multiple_files=True,
        help="Choose one or more CWLS LAS text files. Files are sent only when you run the workflow.",
    )
    las_metadata = []
    for item in uploaded or []:
        try:
            las_metadata.append(inspect_las_header(item.name, item.getvalue()))
        except ValueError as exc:
            st.warning(f"Could not inspect {item.name}: {exc}")

    if uploaded:
        metadata_by_filename = {item.filename: item for item in las_metadata}
        st.dataframe(
            [
                {
                    "Filename": item.name,
                    "Detected well": (
                        metadata_by_filename[item.name].well_name
                        if item.name in metadata_by_filename
                        else "Not detected"
                    ),
                    "Available curves": (
                        ", ".join(metadata_by_filename[item.name].curve_mnemonics)
                        if item.name in metadata_by_filename
                        else "Not detected"
                    ),
                    "Size (bytes)": len(item.getvalue()),
                }
                for item in uploaded
            ],
            width="stretch",
            hide_index=True,
        )
        for metadata in las_metadata:
            for warning in metadata.warnings:
                st.warning(f"{metadata.filename}: {warning}")

    header_signature = las_form_signature(
        [(item.name, len(item.getvalue())) for item in uploaded or []],
        {
            "headers": [
                {
                    "filename": item.filename,
                    "well_name": item.well_name,
                    "curves": list(item.curve_mnemonics),
                }
                for item in las_metadata
            ]
        },
    )
    well_label_to_name: dict[str, str] = {}
    for metadata in las_metadata:
        label = metadata.well_name
        if label in well_label_to_name:
            label = f"{metadata.well_name} — {metadata.filename}"
        well_label_to_name[label] = metadata.well_name
    available_curves = list(
        dict.fromkeys(
            curve
            for metadata in las_metadata
            for curve in metadata.curve_mnemonics
        )
    )

    with st.expander("Quicklook controls", expanded=bool(uploaded)):
        st.caption(
            "Choose from the wells and curves GeoWorld discovered in the uploaded LAS headers."
        )
        selection_columns = st.columns(2)
        selected_well_labels = selection_columns[0].multiselect(
            "Wells",
            options=list(well_label_to_name),
            default=list(well_label_to_name),
            key=f"las-wells-{header_signature[:16]}",
            help="All detected wells are selected by default.",
        )
        selected_curves = selection_columns[1].multiselect(
            "Curves",
            options=available_curves,
            default=recommended_las_curves(available_curves),
            key=f"las-curves-{header_signature[:16]}",
            help="Only curves declared by the uploaded LAS files are shown.",
        )
        selected_wells = list(
            dict.fromkeys(well_label_to_name[label] for label in selected_well_labels)
        )
        setting_columns = st.columns(3)
        depth_mode = setting_columns[0].selectbox(
            "Depth range",
            ["intersection", "union", "custom"],
        )
        target_unit_label = setting_columns[1].selectbox(
            "Display depth in",
            ["Native/common", "m", "ft"],
        )
        log_resistivity = setting_columns[2].checkbox("Log-scale resistivity", value=False)

        custom_min = None
        custom_max = None
        custom_range_valid = True
        if depth_mode == "custom":
            custom_columns = st.columns(2)
            custom_min = custom_columns[0].number_input("Custom MD minimum", value=0.0)
            custom_max = custom_columns[1].number_input("Custom MD maximum", value=1000.0)
            custom_range_valid = custom_max > custom_min
            if not custom_range_valid:
                st.warning("Custom MD maximum must be greater than the minimum.")

        resample_enabled = st.checkbox(
            "Create aligned_curves.csv by deterministic resampling",
            value=False,
        )
        resample_interval = None
        if resample_enabled:
            resample_interval = st.number_input(
                "Resample interval in the target MD unit",
                min_value=0.001,
                value=0.5,
            )

    settings = LASQuicklookSettings(
        selected_wells=selected_wells,
        selected_curves=selected_curves,
        depth_range_mode=depth_mode,
        custom_depth_min=custom_min,
        custom_depth_max=custom_max,
        target_depth_unit=(
            None if target_unit_label == "Native/common" else target_unit_label
        ),
        resample_enabled=resample_enabled,
        resample_interval=resample_interval,
        log_resistivity=log_resistivity,
    )
    signature = las_form_signature(
        [(item.name, len(item.getvalue())) for item in uploaded or []],
        settings,
    )
    if st.session_state.get("las_form_signature") != signature:
        st.session_state["las_form_signature"] = signature

    if st.button(
        "Run LAS Quicklook",
        type="primary",
        disabled=(
            not uploaded
            or not selected_wells
            or not selected_curves
            or not custom_range_valid
        ),
    ):
        try:
            uploads = [encode_las_upload(item.name, item.getvalue()) for item in uploaded]
            with st.spinner("GeoWorld is validating and plotting the LAS files..."):
                submit_and_wait(
                    api,
                    JobCreateRequest(
                        prompt="LAS Quicklook v1 measured-depth job",
                        mode_hint="las_quicklook",
                        las_files=uploads,
                        las_quicklook=settings,
                    ),
                )
        except (GeoWorldClientError, ValueError) as exc:
            st.error(f"LAS Quicklook request failed: {exc}")


def render_save_controls(api: GeoWorldBackendClient, options: DisplayOptions) -> None:
    with st.sidebar, st.expander("Save & export"):
        # Only packaged static code is executed; no prompt/result/session data is
        # interpolated into this HTML. The click never submits a Streamlit job.
        st.html(studio_export_controls(), unsafe_allow_javascript=True)
        st.caption(
            "PDF saves the visible page and selected results tab; the sidebar is excluded. "
            "Review visible content first. Choose Landscape and turn off Headers and footers "
            "in the browser's print dialog."
        )
        job = st.session_state.get("last_job")
        job_id = st.session_state.get("last_job_id")
        if not job_id or job is None or job.status != "succeeded" or job.result is None:
            st.caption("Complete a run to save an offline HTML report.")
            return
        result = job.result
        st.caption(
            "HTML is a formatted offline report, not a copy of the live interface. "
            "It contains the submitted question, answer, citations, figures, and assumptions, "
            "without account details or technical traces. Review it before sharing."
        )
        if st.button("Prepare HTML report", key=f"report-prepare-{job_id}"):
            st.session_state.pop("clean_report", None)
            try:
                figures = [
                    ReportFigure(artifact.name, api.get_artifact(job_id, artifact.name))
                    for artifact in sort_figure_artifacts(result.artifacts)
                    if artifact.kind == "image"
                ]
                html = build_clean_report(
                    prompt=st.session_state.get("last_submitted_prompt"),
                    result=result,
                    figures=figures,
                    options=options,
                )
                # Session-only: never use a shared cache for a user's report.
                st.session_state["clean_report"] = (job_id, options, html)
            except (GeoWorldClientError, ValueError) as exc:
                st.warning(f"Could not prepare the complete clean report: {exc}")
        report = st.session_state.get("clean_report")
        if report and report[:2] == (job_id, options):
            st.download_button(
                "Download HTML report",
                data=report[2],
                file_name="geoworld-clean-report.html",
                mime="text/html",
                key=f"report-download-{job_id}",
                on_click="ignore",
            )


def render_result_models(api: GeoWorldBackendClient, job_id: str, result: JobResult) -> None:
    cached = st.session_state.get("last_result_models")
    if cached and cached[0] == job_id:
        lines = cached[1]
    else:
        answer = trace = None
        preparation = st.session_state.get("last_preparation_model")
        fetch_failed = False
        deterministic = result.intent in {"las_quicklook", "csv_analysis"} or result.mode in {
            "las_quicklook_v1", "csv_summary",
        }
        if not deterministic and preparation is None:
            # Existing protected artifacts, fetched with the current user's
            # client. No extra LLM call and no shared cache of private results.
            for basename in ("answer.json", "trace.json"):
                artifact = artifact_named(result.artifacts, basename)
                if artifact is None or (artifact.size_bytes or 0) > 500_000:
                    continue
                try:
                    payload = api.get_artifact(job_id, artifact.name)
                    if len(payload) > 500_000:
                        continue
                    metadata = decode_json_object(payload)
                except (GeoWorldClientError, ValueError):
                    fetch_failed = True
                    continue
                if basename == "answer.json":
                    answer = metadata
                    if isinstance(metadata.get("llm_usage"), dict):
                        break
                else:
                    trace = metadata
        lines = result_model_lines(result, answer=answer, trace=trace, preparation=preparation)
        if fetch_failed:
            lines.append("Some model details could not be loaded; refresh to retry.")
        else:
            # Cache only the allowlisted, human-readable labels for this job.
            st.session_state["last_result_models"] = (job_id, lines)
    for line in lines:
        st.caption(line)


def reference_artifact_label(name: str) -> str:
    basename = name.rsplit("/", 1)[-1]
    labels = {
        "velocity_acquisition.png": "INPUT / PROVENANCE: true Marmousi 1 Vp, acquisition geometry, and smoothed migration velocity",
        "example_rtm_mask.jpg": "PROCESSING DIAGNOSTIC: one observed shot gather, direct-arrival mute, and masked data",
        "example_rtm.jpg": "OUTPUT: one-update Born-adjoint RTM image",
    }
    return labels.get(basename, basename)


def display_result(api: GeoWorldBackendClient, options: DisplayOptions) -> None:
    job = st.session_state.get("last_job")
    job_id = st.session_state.get("last_job_id")
    if job is None or not job_id:
        return
    active_prompt = st.session_state.get("studio_request_prompt")
    if (
        # The normal request's stale-result guard does not own manual runs.
        # Keep existing results visible in manual tools without changing jobs
        # or discarding the normal workflow's interpretation on a mode switch.
        not st.session_state.get("manual_tools", False)
        and st.session_state.get("studio_decision") is not None
        and st.session_state.get("last_result_source") != "saved_run"
        and active_prompt
        and st.session_state.get("last_submitted_prompt") != active_prompt
    ):
        return
    if job.status == "failed":
        st.error(friendly_job_error(job.error))
        return
    if job.result is None:
        st.warning("GeoWorld completed without a result payload.")
        return

    result = job.result
    submitted_prompt = st.session_state.get("last_submitted_prompt")
    if submitted_prompt:
        st.caption("Saved result for: " + str(submitted_prompt))
    correlation_id = st.session_state.get("last_correlation_id")
    images = sort_figure_artifacts(
        artifact for artifact in result.artifacts if artifact.kind == "image"
    )
    if result.intent == "deepwave_reference":
        order = {"velocity_acquisition.png": 0, "example_rtm_mask.jpg": 1, "example_rtm.jpg": 2}
        images = sorted(images, key=lambda artifact: order.get(artifact.name.rsplit("/", 1)[-1], 3))

    render_result_models(api, job_id, result)
    if result.intent == "model_rtm":
        from geoworld_open.studio_rtm import render_rtm_summary
        render_rtm_summary(result, replay=bool(st.session_state.get("rtm_replay")))
    elif result.intent == "deepwave_reference":
        from geoworld_open.studio_reference import render_reference_summary
        render_reference_summary(result)
    with st.expander("Job details"):
        st.write(f"**Job:** `{job_id}`")
        if correlation_id:
            st.write(f"**Safe request reference:** `{correlation_id}`")
            st.caption(
                "Use this identifier to connect UI, API, job, trace, and evidence records. "
                "It contains no prompt, email, or scientific data."
            )
        else:
            st.caption("This job was created before request references were exposed to Studio.")
    overview, science, provenance, artifacts, advanced = st.tabs(
        ["Overview", "Model & Figures", "State / Provenance", "Artifacts", "Advanced"]
    )

    with overview:
        if result.intent == "deepwave_reference":
            for image in images:
                st.caption(reference_artifact_label(image.name))
                st.image(api.get_artifact(job_id, image.name), width="stretch" if options.fit_figures else options.figure_px)
        elif result.intent == "model_rtm":
            for image in images[1:]:
                st.image(api.get_artifact(job_id, image.name), width="stretch" if options.fit_figures else options.figure_px)
        if images and result.intent != "deepwave_reference":
            try:
                st.image(api.get_artifact(job_id, images[0].name), width="stretch" if options.fit_figures else options.figure_px)
            except GeoWorldClientError as exc:
                st.warning(str(exc))
        st.subheader("GeoWorld result")
        st.write(result.answer)
        if result.grounding_status == "geoworld_grounded":
            st.success("Grounded in reviewed GeoWorld knowledge")
            for citation_line in human_citation_lines(result.citations):
                st.caption(citation_line)
        elif result.grounding_status == "evidence_insufficient":
            from geoworld_open.studio_qa import qa_outcome_message
            st.warning(qa_outcome_message(result))
        elif result.grounding_status == "general_model_uncited":
            st.warning("General model answer — not supported by a GeoWorld knowledge citation.")
        st.caption(f"Route: {result.intent}" + (f" · mode: {result.mode}" if result.mode else ""))
        if result.interpretation_mode:
            st.caption(
                f"Interpretation: {result.interpretation_mode}"
                + (" · degraded fallback confirmed" if result.interpretation_degraded else "")
            )
        if result.assumptions:
            st.subheader("Assumptions")
            for item in result.assumptions:
                st.markdown(f"- {item}")
        coverage_rows = output_coverage_rows(
            result.requested_outputs,
            result.produced_outputs,
            result.output_coverage,
        )
        if coverage_rows:
            st.subheader("Requested output coverage")
            st.dataframe(coverage_rows, width="stretch", hide_index=True)

    with science:
        for artifact in images:
            try:
                caption = reference_artifact_label(artifact.name) if result.intent == "deepwave_reference" else artifact.name
                st.image(api.get_artifact(job_id, artifact.name), caption=caption, width="stretch" if options.fit_figures else options.figure_px)
            except GeoWorldClientError as exc:
                st.warning(f"{artifact.name}: {exc}")
        if result.layers or result.storage:
            with st.expander("Tables & scientific details"):
                if result.layers:
                    st.subheader("Layers")
                    st.dataframe(result.layers, width="stretch")
                if result.storage:
                    st.subheader("Scientific summary")
                    st.json(result.storage)
        if result.mode == "las_quicklook_v1" or result.intent == "las_quicklook":
            render_las_details(api, job_id, result.artifacts)

    with provenance:
        summary_lines = provenance_lines(result.provenance_summary)
        if summary_lines:
            st.subheader("Reproducibility summary")
            for line in summary_lines:
                st.write(line)
        preferred = [
            artifact
            for artifact in result.artifacts
            if any(
                token in artifact.name.lower()
                for token in ("world_state", "observation", "manifest", "trace", "provenance", "state_lineage")
            )
        ]
        if not preferred:
            st.info("This workflow did not expose state/provenance artifacts through the current backend result.")
        with st.expander("Technical provenance artifacts"):
            for artifact in preferred:
                st.write(f"**{artifact.name}**")
                if artifact.kind in {"json", "text", "yaml", "csv"} and (artifact.size_bytes or 0) < 500_000:
                    try:
                        payload = api.get_artifact(job_id, artifact.name)
                        text = payload.decode("utf-8", errors="replace")
                        if artifact.kind == "json":
                            import json

                            st.json(json.loads(text))
                        else:
                            st.code(text[:30_000], language="yaml" if artifact.kind == "yaml" else None)
                    except Exception as exc:
                        st.warning(f"Could not display {artifact.name}: {exc}")

    with artifacts:
        try:
            export_bytes = api.get_export(job_id)
            st.download_button(
                "Download complete run export",
                data=export_bytes,
                file_name=f"geoworld-run-{job_id}.html",
                mime="text/html",
                type="primary",
            )
        except GeoWorldClientError as exc:
            st.caption(f"Complete export unavailable: {exc}")
        for artifact in result.artifacts:
            try:
                payload = api.get_artifact(job_id, artifact.name)
            except GeoWorldClientError as exc:
                st.warning(f"Could not load {artifact.name}: {exc}")
                continue
            st.download_button(
                f"Download {artifact.name}",
                data=payload,
                file_name=Path(artifact.name).name,
                mime=artifact.media_type,
                key=f"download-{job_id}-{artifact.name}",
            )

    with advanced:
        st.write(f"**Backend:** `{backend_url()}`")
        if result.geospec:
            st.subheader("Validated GeoSpec")
            st.code(yaml.safe_dump(result.geospec, sort_keys=False), language="yaml")
        st.subheader("Result metadata")
        st.json(result.model_dump(mode="json"))


def render_manual_workspace(api: GeoWorldBackendClient) -> None:
    """Render the existing workflow in a stable presentation-only container."""
    from geoworld_open.studio_rtm import local_rtm_ui_enabled, render_rtm_workspace
    workspaces = ["Ask or Build", "LAS Quicklook"]
    if local_rtm_ui_enabled(backend_url()):
        workspaces.append("Deepwave reference")
        workspaces.append("Marmousi models")
        workspaces.append("Model + RTM")
    workspace = st.radio(
        "Workspace",
        workspaces,
        horizontal=True,
        key="manual_workspace",
    )
    if st.session_state.get("active_workspace") != workspace:
        st.session_state["active_workspace"] = workspace

    if workspace == "LAS Quicklook":
        render_las_workspace(api)
        return
    if workspace == "Model + RTM":
        render_rtm_workspace(api, submit_and_wait)
        return
    if workspace == "Deepwave reference":
        from geoworld_open.studio_reference import render_reference_workspace
        render_reference_workspace(api, submit_and_wait)
        return
    if workspace == "Marmousi models":
        from geoworld_open.studio_marmousi import render_model_workspace
        render_model_workspace(api, submit_and_wait)
        return

    cols = st.columns(len(EXAMPLES))
    for column, (label, example) in zip(cols, EXAMPLES.items()):
        if column.button(label, use_container_width=True):
            st.session_state["prompt"] = example
            for key in (
                "prepared_geospec",
                "prepared_preview",
                "detected_intent",
                "auto_route_confirmed",
                "fallback_confirmed",
            ):
                st.session_state.pop(key, None)
            st.rerun()

    if "prompt" not in st.session_state:
        st.session_state["prompt"] = EXAMPLES["Seismic + AVO"]

    prompt = st.text_area(
        "What would you like GeoWorld to do?",
        key="prompt",
        height=130,
    )
    if st.session_state.get("runtime_prompt") != prompt:
        for key in (
            "prepared_geospec",
            "prepared_preview",
            "detected_intent",
            "auto_route_confirmed",
            "fallback_confirmed",
        ):
            st.session_state.pop(key, None)
        st.session_state["runtime_prompt"] = prompt

    intent_label = st.radio(
        "Intent",
        ["Auto", "Build Model", "Ask Question"],
        horizontal=True,
    )

    if st.session_state.get("runtime_intent_label") != intent_label:
        for key in (
            "prepared_geospec",
            "prepared_preview",
            "detected_intent",
            "auto_route_confirmed",
            "fallback_confirmed",
        ):
            st.session_state.pop(key, None)
        st.session_state["runtime_intent_label"] = intent_label

    selected_intent: str | None
    route_confirmed = True
    if intent_label == "Auto":
        if st.button("Determine route", type="primary", disabled=not prompt.strip()):
            try:
                with st.spinner("GeoWorld is classifying the request..."):
                    st.session_state["detected_intent"] = api.preview_intent(prompt)
            except GeoWorldClientError as exc:
                st.error(str(exc))
        detected = st.session_state.get("detected_intent")
        selected_intent = None
        if isinstance(detected, dict):
            selected_intent = str(detected.get("intent") or "") or None
            message = f"Detected intent: {detected.get('label', selected_intent)}. {detected.get('reason', '')}"
            if detected.get("needs_confirmation"):
                st.warning(message)
                route_confirmed = st.checkbox(
                    "Use this proposed route",
                    key="auto_route_confirmed",
                )
            else:
                st.info(message)
    else:
        selected_intent = "build_model" if intent_label == "Build Model" else "ask_question"
        st.info(f"Selected intent: {intent_label}.")

    if selected_intent == "build_model" and route_confirmed:
        st.subheader("Build model")
        if st.button("Prepare model", type="primary", disabled=not prompt.strip()):
            try:
                with st.spinner("GeoWorld is interpreting and validating the model request..."):
                    preview = api.preview_geospec(prompt=prompt)
                st.session_state["prepared_preview"] = preview
                if preview.get("valid") and isinstance(preview.get("geospec"), dict):
                    st.session_state["prepared_geospec"] = preview["geospec"]
                    if preview.get("degraded"):
                        st.warning(
                            preview.get("diagnostic")
                            or "LLM interpretation was unavailable. Review and confirm the limited deterministic interpretation."
                        )
                    else:
                        st.success(
                            "Validated GeoSpec prepared by the configured LLM path. Review it, then run the model."
                        )
                else:
                    st.session_state.pop("prepared_geospec", None)
                    st.error("GeoWorld could not prepare a valid model from this request.")
            except GeoWorldClientError as exc:
                st.error(str(exc))

        preview = st.session_state.get("prepared_preview")
        prepared = st.session_state.get("prepared_geospec")
        confirmation_required = bool(
            isinstance(preview, dict) and preview.get("confirmation_required")
        )
        confirmed = not confirmation_required
        if isinstance(preview, dict):
            interpretation_mode = preview.get("interpretation_mode") or preview.get("parser_mode")
            st.caption(
                f"Interpretation mode: {interpretation_mode or 'unknown'}"
                + (" · degraded fallback" if preview.get("degraded") else "")
            )
            st.caption(preparation_model_line(preview))
            with st.expander("Prepared model / assumptions"):
                issues = preview.get("issues")
                if isinstance(issues, list):
                    for issue in issues:
                        if isinstance(issue, dict):
                            st.write(
                                f"{str(issue.get('severity', 'info')).upper()}: "
                                f"{issue.get('message', '')}"
                            )
                geospec = preview.get("geospec")
                if isinstance(geospec, dict):
                    assumptions = geospec.get("assumptions")
                    if isinstance(assumptions, list):
                        for item in assumptions:
                            st.markdown(f"- {item}")
                    st.code(yaml.safe_dump(geospec, sort_keys=False), language="yaml")
            if confirmation_required:
                confirmed = st.checkbox(
                    "I reviewed this limited deterministic interpretation and want to run it",
                    key="fallback_confirmed",
                )

        if st.button(
            "Run model",
            disabled=not isinstance(prepared, dict) or not confirmed,
        ):
            try:
                with st.spinner("Running GeoWorld scientific workflow..."):
                    submit_and_wait(
                        api,
                        JobCreateRequest(
                            prompt=prompt,
                            mode_hint="build_model",
                            geospec=prepared,
                            interpretation_mode=(
                                str(preview.get("interpretation_mode") or preview.get("parser_mode"))
                                if isinstance(preview, dict)
                                else "user_geospec_v2"
                            ),
                            interpretation_degraded=bool(
                                isinstance(preview, dict) and preview.get("degraded")
                            ),
                            degraded_fallback_confirmed=bool(confirmed),
                        ),
                    )
            except GeoWorldClientError as exc:
                st.error(str(exc))

    elif selected_intent == "ask_question" and route_confirmed:
        st.subheader("Ask a question")
        if st.button("Ask GeoWorld", type="primary", disabled=not prompt.strip()):
            try:
                with st.spinner("GeoWorld is preparing an answer..."):
                    submit_and_wait(
                        api,
                        JobCreateRequest(prompt=prompt, mode_hint="ask_question"),
                    )
            except GeoWorldClientError as exc:
                st.error(str(exc))
    elif selected_intent and route_confirmed:
        st.warning(
            "The backend detected a specialized route that this public Ask/Build page does not expose. "
            "Choose Build Model or Ask Question to override it."
        )


def render_workspace(api: GeoWorldBackendClient) -> None:
    with st.expander("Advanced: manual tools / debugging"):
        manual = st.checkbox("Use manual tools", key="manual_tools")
        st.caption("Optional compatibility tools. Normally, describe your task below and let GeoWorld select it.")
    if manual:
        render_manual_workspace(api)
    else:
        from geoworld_open.studio_request import render_request
        render_request(api, submit_and_wait, render_las_workspace)


def render_saved_run(api):
    import json
    import re
    with st.expander("Open saved run"):
        st.caption("Reopen a job owned by this account. This does not run a model or call an LLM.")
        job_id = st.text_input("Saved job ID", key="saved_job_id")
        if st.button("Open run", disabled=not re.fullmatch(r"[0-9a-f]{32}", job_id)):
            try:
                job = api.get_job(job_id)
                if job.status != "succeeded" or job.result is None:
                    st.warning("This job has not completed successfully yet. " + job.progress)
                    return
                # Read everything before replacing visible state; failed access
                # must not destroy the previously displayed result.
                original = json.loads(api.get_artifact(job_id, "request.json"))
                prompt = original["prompt"]
                if not isinstance(prompt, str):
                    raise ValueError("Invalid recorded request")
                clear_last_result()
                st.session_state["last_job"] = job
                st.session_state["last_job_id"] = job_id
                st.session_state["last_submitted_prompt"] = prompt
                st.session_state["last_result_source"] = "saved_run"
                # Job status on older backends has no correlation field. Never
                # reuse an unrelated run's identifier or fail report recovery.
                st.session_state["last_correlation_id"] = getattr(job.result, "correlation_id", None)
            except (GeoWorldClientError, ValueError, KeyError) as exc:
                st.warning(f"Could not open that saved run: {exc}")


display_options = DisplayOptions(
    text_px=st.session_state.get("display_text_px", 18),
    figure_px=st.session_state.get("display_figure_px", 880),
    layout=st.session_state.get("display_layout", "Auto"),
    fit_figures=st.session_state.get("display_fit_figures", True),
)
st.markdown(studio_display_css(display_options), unsafe_allow_html=True)

token = render_auth()
if not token:
    st.stop()

api = client(token)

with st.sidebar:
    st.header("GeoWorld")
    st.write(st.session_state.get("user_email", "Signed in"))
    try:
        health = api.get_llm_health()
        diagnostic = health_diagnostic(health)
        if diagnostic["overall_status"] == "available":
            st.success("GeoWorld is ready")
        elif diagnostic["overall_status"] == "degraded":
            st.warning("Primary AI is unavailable; a backup is configured.")
        else:
            st.warning(
                "AI interpretation is temporarily unavailable. "
                "LAS Quicklook and deterministic tools can still run."
            )
        for line in configured_model_lines(health):
            st.caption(line)
        st.caption("Configuration only; each result shows the model recorded for that run.")
    except Exception:
        st.warning("GeoWorld service status is temporarily unavailable")
    if st.button("Log out"):
        clear_session()
        st.rerun()
    render_saved_run(api)
    st.selectbox("Page layout", ["Auto", "One column", "Two columns"], key="display_layout")
    st.caption("Auto uses two columns when there is room. Narrow screens always stack for readability.")
    with st.expander("Display settings"):
        st.slider("Text size (px)", 16, 24, 18, key="display_text_px")
        fit_figures = st.checkbox("Fit figures to column", value=True, key="display_fit_figures")
        st.slider("Figure width (px)", 480, 1200, 880, step=40, key="display_figure_px", disabled=fit_figures)
        st.caption(
            "Use browser zoom at 100% for readable text. Figures keep their proportions "
            "and fit the column by default. Turn off Fit figures to column to choose a smaller width."
        )

st.title("🌍 GeoWorld Studio")
st.caption(
    "Ask a geoscience question or describe a model. The public frontend sends validated requests to the protected GeoWorld backend."
)

with st.container(key="studio_workspace_layout"):
    with st.container(key="studio_workflow"):
        render_workspace(api)
    with st.container(key="studio_results"):
        display_result(api, display_options)

render_save_controls(api, display_options)
