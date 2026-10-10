"""PUBLIC_SDK_INFRA: safe HTTP-only scientific result presentation."""
import json
import streamlit as st
from geoworld_open.client import GeoWorldClientError, JobCreateRequest
from geoworld_open.client.scientific_workflow import ScientificExperimentContext


def restore_working_context(old):
    st.session_state["studio_task_context"] = st.session_state.get("studio_previous_task_context", old)
    st.session_state["studio_decision"] = st.session_state.get("studio_previous_decision")
    st.session_state["studio_request_prompt"] = st.session_state.get("studio_previous_request_prompt", "")
    st.session_state["studio_active_context"] = st.session_state.get("studio_previous_context", "request")


def render_scientific_request(api, submit, decision):
    preview = decision.scientific
    if preview is None:
        return
    if not preview.execution_allowed:
        st.warning(preview.message)
        return
    seen = st.session_state.setdefault("scientific_submitted", [])
    run = False
    if not preview.automatic_execution and preview.preparation_id not in seen:
        st.write("Prepared scientific workflow")
        st.caption(" → ".join(preview.workflow))
        with st.expander("Assumptions and scientific limits"):
            for line in preview.assumptions + preview.limitations:
                st.write(line)
        run = st.button("Run scientific experiment", type="primary")
    if (preview.automatic_execution or run) and preview.preparation_id not in seen:
        # Claim before HTTP: widget rerenders cannot resubmit accepted work.
        # The backend independently deduplicates the owner/preparation pair.
        seen.append(preview.preparation_id)
        from geoworld_open.studio_context import task_context
        old = task_context()
        try:
            submit(api, JobCreateRequest(prompt=preview.request, mode_hint="scientific_workflow",
                                         scientific_preparation_id=preview.preparation_id))
            job = st.session_state.get("last_job")
            result = job.result.scientific if job and job.result else None
            if result and result.preparation_id == preview.preparation_id:
                st.session_state["studio_task_context"] = old.model_copy(update={
                    "active_task": "scientific", "scientific": ScientificExperimentContext(
                        preparation_id=preview.preparation_id, goal=preview.goal,
                        completed_job_id=st.session_state["last_job_id"]),
                })
                st.rerun()
            else:
                restore_working_context(old)
        except GeoWorldClientError as exc:
            restore_working_context(old)
            from geoworld_open.studio_assistant import append_message
            append_message("assistant", str(exc))
            st.error(str(exc))


def render_scientific_result(api, job_id, result):
    science = result.scientific
    st.subheader("Scientific workspace")
    st.caption(science.limitations[0] if science.limitations else "Scientific experiment · inspect source provenance before reuse")
    overview, models, evidence, details = st.tabs([
        "Overview", "Models & Figures", "Scientific Evidence / Provenance", "Complete Details"])
    with overview:
        try:
            section = json.loads(api.get_artifact(job_id, "scientific-section.json"))
            import plotly.graph_objects as go
            names = list(section["fields"])
            field = st.selectbox("Scientific field", names, index=names.index("sand_probability") if "sand_probability" in names else 0, key="scientific_field")
            values = section["fields"][field]
            signed = field.startswith("delta_") or field in {"near", "mid", "far"}
            import numpy as np
            array = np.asarray(values["values"])
            bound = max(float(np.abs(array).max()), 1e-12)
            limits = {"zmin": -bound, "zmax": bound} if signed else {}
            scale = st.slider("Display scale (%)", 20, 200, 100, key="scientific_display_scale") / 100
            if signed:
                limits = {"zmin": -bound*scale, "zmax": bound*scale}
            fig = go.Figure(go.Heatmap(x=np.asarray(section["distance_m"])/1000, y=section["time_s"],
                z=array, colorscale="RdBu" if signed else "Cividis", colorbar={"title": values["units"]}, **limits))
            fig.update_layout(height=540, margin=dict(l=65, r=30, t=15, b=50),
                xaxis_title="Along-line distance (km)", yaxis_title="TWT (s)", uirevision=job_id + field,
                yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig, use_container_width=True, key="scientific_section_plot")
        except GeoWorldClientError as exc:
            st.warning(str(exc))
        st.write(result.answer)
        if science.metrics:
            rows = [{key: row[key] for key in ("saturation", "max_abs_delta_vp_m_s", "max_abs_delta_near", "max_abs_delta_mid", "max_abs_delta_far") if key in row} for row in science.metrics]
            st.dataframe(rows, hide_index=True, use_container_width=True)
    with models:
        image = api.get_artifact(job_id, science.figure_artifact)
        st.image(image, caption="Actual numerical fields; matched states, not field monitoring", use_container_width=True)
        names = [science.model_artifact, science.evidence_artifact]
        available = {item.name for item in result.artifacts}
        names.extend(name for name in ("scientific-overview.svg", "scientific-overview.pdf") if name in available)
        for name in names:
            st.download_button("Download " + name, api.get_artifact(job_id, name), file_name=name, key="scientific_download_" + name)
    with evidence:
        st.write("Selected capabilities: " + " → ".join(science.workflow))
        for line in science.limitations:
            st.write(line)
        for name in ("interaction.json", "workflow-plan.json", "scientific-qc.json", "trace.json", "world.json", "verification.json", science.manifest_artifact):
            with st.expander(name):
                payload = json.loads(api.get_artifact(job_id, name))
                st.json(payload)
                st.download_button("Download evidence", api.get_artifact(job_id, name), file_name=name, key="scientific_evidence_" + name)
    with details:
        st.write("Assumptions")
        for line in result.assumptions:
            st.write(line)
        st.json(science.model_dump(mode="json"))
        with st.expander("All retained artifacts"):
            for item in result.artifacts:
                st.caption(item.name)
