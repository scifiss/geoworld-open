"""Compact pre-run evidence; no client-side hardware detection or policy."""
import streamlit as st


def render_preflight(plan):
    if plan is None:
        st.warning('No execution estimate returned. Update the local backend before running.')
        return False
    low, high = plan.estimate.runtime_seconds
    def duration(seconds):
        return f'{seconds / 60:.0f} min' if seconds >= 120 else f'{seconds:.0f} s'
    st.markdown('#### GeoWorld recommends')
    st.write(f"Execution: local backend {'GPU' if plan.resolved_device == 'cuda' else 'CPU'} · "
             f'Expected time: {duration(low)}–{duration(high)}')
    st.write(f'Expected RAM: {plan.estimated_ram_bytes / 1024**3:.2f} GiB · '
             f'VRAM: {plan.estimated_vram_bytes / 1024**3:.2f} GiB · '
             f'Scientific mode: {plan.scientific_mode.replace("_", " ")} · '
             f'Confidence: {plan.estimate.confidence}')
    st.caption('Pre-run estimate, not live ETA. This preview has not run the numerical experiment.')
    with st.expander('Advanced: execution plan and estimate evidence'):
        for reason in plan.reasons:
            st.caption(reason)
        st.json(plan.model_dump(mode='json'))
    if not plan.feasible:
        st.error('Resources are insufficient under the reserve policy. Nothing will run.')
    return plan.feasible
