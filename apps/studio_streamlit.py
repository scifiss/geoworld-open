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

from geoworld_open.client import GeoWorldBackendClient, GeoWorldClientError, JobCreateRequest
from geoworld_open.client.backend import backend_url_from_environment
from geoworld_open.studio_runtime import (
    health_diagnostic,
    output_coverage_rows,
    provenance_lines,
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
    for key in (
        "access_token",
        "user_email",
        "prepared_geospec",
        "prepared_preview",
        "detected_intent",
        "auto_route_confirmed",
        "fallback_confirmed",
        "last_job",
        "last_job_id",
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


def poll_job(api: GeoWorldBackendClient, job_id: str):
    progress = st.progress(0)
    status = st.empty()
    for index in range(120):
        job = api.get_job(job_id)
        status.info(f"{job.status}: {job.progress}")
        progress.progress(min(95, 5 + index % 90))
        if job.status in {"succeeded", "failed"}:
            progress.progress(100)
            return job
        time.sleep(3)
    raise GeoWorldClientError("Timed out while waiting for GeoWorld job completion")


def submit_and_wait(api: GeoWorldBackendClient, request: JobCreateRequest) -> None:
    created = api.submit_job(request)
    st.session_state["last_job_id"] = created.job_id
    st.session_state["last_job"] = poll_job(api, created.job_id)


def display_result(api: GeoWorldBackendClient) -> None:
    job = st.session_state.get("last_job")
    job_id = st.session_state.get("last_job_id")
    if job is None or not job_id:
        return
    if job.status == "failed":
        st.error(job.error or "GeoWorld job failed.")
        return
    if job.result is None:
        st.warning("GeoWorld completed without a result payload.")
        return

    result = job.result
    images = sort_figure_artifacts(
        artifact for artifact in result.artifacts if artifact.kind == "image"
    )

    st.divider()
    overview, science, provenance, artifacts, advanced = st.tabs(
        ["Overview", "Model & Figures", "State / Provenance", "Artifacts", "Advanced"]
    )

    with overview:
        if images:
            try:
                st.image(api.get_artifact(job_id, images[0].name), width="stretch")
            except GeoWorldClientError as exc:
                st.warning(str(exc))
        st.subheader("GeoWorld result")
        st.write(result.answer)
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
                st.image(api.get_artifact(job_id, artifact.name), caption=artifact.name, width="stretch")
            except GeoWorldClientError as exc:
                st.warning(f"{artifact.name}: {exc}")
        if result.layers:
            st.subheader("Layers")
            st.dataframe(result.layers, width="stretch")
        if result.storage:
            st.subheader("Scientific summary")
            st.json(result.storage)

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
        st.caption(f"LLM status: {diagnostic['overall_status']}")
        if diagnostic["active_provider"]:
            st.caption(
                f"Active: {diagnostic['active_provider']} / {diagnostic['active_model']}"
            )
        else:
            st.caption("Active provider: none")
        with st.expander("Connection diagnostic"):
            st.write({
                "primary": diagnostic["primary"],
                "fallback": diagnostic["fallback"],
                "local_fallback": diagnostic["local_fallback"],
            })
    except Exception:
        st.caption("LLM status unavailable")
    if st.button("Log out"):
        clear_session()
        st.rerun()

st.title("🌍 GeoWorld Studio")
st.caption(
    "Ask a geoscience question or describe a model. The public frontend sends validated requests to the protected GeoWorld backend."
)

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

    if isinstance(preview, dict):
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

display_result(api)
