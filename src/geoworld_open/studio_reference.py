"""PUBLIC_SDK_INFRA: HTTP-only presentation of a pinned scientific reference."""
from __future__ import annotations

import streamlit as st

from geoworld_open.client import GeoWorldClientError
from geoworld_open.client.models import JobCreateRequest
from geoworld_open.client.reference_experiment import ReferenceSelection
from geoworld_open.studio_llm import execution_model_line


def render_reference_workspace(api, submit, *, prompt=None, auto_prepare=False):
    st.subheader("Deepwave · Marmousi 1 reference")
    st.caption("Reference forward data → tapered direct-arrival mute → batched, one-update RTM.")
    debug, action = False, "prepare"
    if prompt is None:
        prompt = st.text_area("Describe the reference experiment", value="Reproduce the official Deepwave Marmousi RTM example using its documented settings.", key="reference_prompt", height=110)
        with st.expander("Advanced: structured selection / debugging"):
            debug = st.checkbox("Use a structured reference selection (no LLM)", key="reference_debug")
            action = st.selectbox("Structured action", ["prepare", "run"], key="reference_action", disabled=not debug)
            st.caption("The reference supplies geometry and numerical defaults. This control cannot introduce arbitrary models or coordinates.")
    st.caption("Calculation runs on the backend computer—not in your browser. GPU choice does not change the reference geometry or physics.")
    with st.expander('Advanced: execution preference'):
        device = st.selectbox('Reference execution device', ['auto', 'cpu', 'cuda'], key='reference_device')
    signature = (prompt, debug, action, device)
    if st.session_state.get("reference_signature") != signature:
        st.session_state.pop("reference_preview", None)
        st.session_state["reference_signature"] = signature
    if st.button("Interpret & validate reference", type="primary", disabled=not prompt.strip()) or auto_prepare:
        st.session_state.pop("reference_preview", None)
        try:
            with st.spinner("Resolving the pinned reference; no numerical execution…"):
                preview = api.preview_reference(selection=ReferenceSelection(action=action) if debug else None, prompt=None if debug else prompt, device=device)
            st.session_state["reference_preview"] = preview
        except GeoWorldClientError as exc:
            st.error(str(exc))
    preview = st.session_state.get("reference_preview")
    if preview is None:
        return
    labels = {"unchanged_reference": "Unchanged reference", "modified_reference": "Modified reference — not an exact reproduction",
              "unsupported": "Unsupported request", "inconsistent": "Conflicting instructions"}
    st.write("**Validation:** " + labels[preview.classification] + (" · prepare-only" if preview.prepare_only else ""))
    st.caption(execution_model_line(preview.llm, purpose="Request interpretation") if preview.llm
               else "Request interpretation: structured selection; no LLM call.")
    st.caption("Numerical execution: Deepwave 0.0.26. The LLM does not calculate wavefields or choose acquisition coordinates.")
    st.caption("Selected execution device: " + preview.device.upper())
    if preview.model_preview:
        import plotly.graph_objects as go
        model = preview.model_preview
        field = st.selectbox('Reference input view', ['true_velocity','migration_velocity'],
                             format_func=lambda key: key.replace('_',' ').capitalize())
        fig = go.Figure(go.Heatmap(x=model['x_m'], y=model['z_m'], z=model[field],
                                  zmin=1500,zmax=5500,colorbar=dict(title='Vp (m/s)')))
        for key, marker, color in [('receivers_m','circle','white'),('sources_m','star','red')]:
            points = model[key]
            fig.add_scatter(x=[p[0] for p in points], y=[p[1] for p in points], mode='markers',
                marker=dict(symbol=marker, color=color, size=5), name=key.replace('_m',''))
        fig.update_layout(title='INPUT: '+field.replace('_',' ')+' + acquisition', xaxis_title='x (m)', yaxis_title='Depth (m)')
        fig.update_yaxes(autorange='reversed', scaleanchor='x')
        st.caption(model['label'])
        st.plotly_chart(fig, width='stretch')
    else:
        st.caption('Verified reference input preview is unavailable on this backend; no synthetic replacement is generated.')
    from geoworld_open.studio_execution import render_preflight
    feasible = render_preflight(preview.execution_plan)
    for conflict in preview.unresolved_conflicts:
        st.warning(conflict)
    for suggestion in preview.suggestions:
        st.info(suggestion)
    st.write("**Inherited reference:** Marmousi 1 · 115 shots · 384 receivers · 25 Hz Ricker · 750 samples at 4 ms.")
    st.write("Migration velocity: smooth slowness (σ = 160 m), then use the official 8 m grid. One SGD update after accumulated Born gradients.")
    if preview.proposed_modifications:
        for change in preview.proposed_modifications:
            st.write(f"Proposed change: **{change.parameter} = {change.value:g}** — {change.user_text}")
    with st.expander("Interpreted structured request"):
        st.code(preview.selection.model_dump_json(indent=2), language="json")
    with st.expander("Resolved reference / inherited settings / provenance"):
        st.caption("Reference: " + preview.selection.reference_id + " · configuration " + preview.configuration_sha256[:16])
        st.json(preview.resolved_configuration or preview.inherited_reference_values)
        st.markdown("[Official forward example](https://ausargeo.com/deepwave/example_forward_model) · [Official RTM example](https://ausargeo.com/deepwave/example_rtm)")
    st.caption("Execution requires completed standalone reference gates on the local backend. CPU runs can take tens of minutes; this is not enabled on Render.")
    if st.button("Run verified reference", disabled=not preview.runnable or not feasible):
        try:
            submit(api, JobCreateRequest(prompt=prompt, mode_hint="deepwave_reference", reference_preparation_id=preview.preparation_id))
        except GeoWorldClientError as exc:
            st.error(str(exc))


def render_reference_summary(result):
    evidence = result.reference
    if evidence is None:
        return
    st.success(f"Unchanged reference RTM recomputed · {evidence.runtime_seconds / 60:.1f} minutes · raw comparison passed")
    st.caption(evidence.numerical_executor)
    st.caption("Recorded execution device: " + evidence.device.upper())
    st.caption(execution_model_line(evidence.llm, purpose="Request interpretation") if evidence.llm
               else "Structured selection; no LLM interpretation occurred for this run.")
    st.caption("Forward observations reused from the checksummed standalone reference. This run recomputed RTM, not forward data or FWI. Display clipping is the upstream 5–95% convention; raw arrays are preserved.")
    st.caption("Original upstream RTM plot axes are grid indices (8 m/cell). Gather/mask axes are receiver and time indices (24 m receiver spacing, 4 ms sampling). The extra velocity view uses metres.")
