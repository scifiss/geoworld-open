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
            from geoworld_open.studio_fields import DEFAULT_FIELDS, compose_fields, field_label
            defaults = [name for name in DEFAULT_FIELDS if name in section['fields']]
            if not defaults:
                defaults = list(section['fields'])[:4]
            st.plotly_chart(compose_fields(section, defaults, identity=job_id+'overview'),
                use_container_width=True, key="scientific_section_plot")
        except GeoWorldClientError as exc:
            st.warning(str(exc))
        if science.metrics:
            labels = {'saturation': 'CO₂ saturation (fraction)',
                'max_abs_delta_vp_m_s': 'Maximum |ΔVp| (m/s)',
                'max_abs_delta_far': 'Maximum |Δfar PP| (dimensionless)'}
            rows = [{label: row[key] for key, label in labels.items() if key in row} for row in science.metrics]
            st.dataframe(rows, hide_index=True, use_container_width=True)
    with models:
        if 'section' in locals():
            names = list(section['fields'])
            if st.session_state.get('studio_scientific_view_job') != job_id:
                restored=[name for name in st.session_state.pop('studio_restored_fields',[]) if name in names]
                initial=restored or defaults
                st.session_state.update(studio_scientific_view_job=job_id,
                    scientific_selected_fields=initial, scientific_panel_order=initial.copy())
            selected = st.multiselect('Fields to display (up to four)', names,
                format_func=field_label, max_selections=4, key='scientific_selected_fields')
            order = [name for name in st.session_state['scientific_panel_order'] if name in selected]
            order += [name for name in selected if name not in order]
            st.session_state['scientific_panel_order'] = order
            if order:
                move = st.selectbox('Field to reorder', order, format_func=field_label, key='scientific_reorder_field')
                earlier, later = st.columns(2)
                index = order.index(move)
                if earlier.button('Move earlier', disabled=index==0):
                    order[index-1],order[index]=order[index],order[index-1]
                    st.rerun()
                if later.button('Move later', disabled=index==len(order)-1):
                    order[index+1],order[index]=order[index],order[index+1]
                    st.rerun()
                st.caption('Panel order: ' + ' → '.join(field_label(name) for name in order))
                scale = st.slider("Display scale (%)", 20, 200, 100, key="scientific_display_scale")/100
                st.plotly_chart(compose_fields(section, order, scale=scale, identity=job_id+'selected'),
                    use_container_width=True, key='scientific_selected_plot')
                from geoworld_open.client.studio_session import ScientificFigureRequest
                request = ScientificFigureRequest(fields=tuple(order),display_scale=scale)
                signature = (job_id, request.model_dump_json())
                if st.button('Generate selected scientific figure', key='scientific_generate_figure'):
                    try:
                        st.session_state['studio_selected_figure'] = (signature, api.scientific_figure(job_id, request))
                    except GeoWorldClientError as exc:
                        st.warning(str(exc))
                saved = st.session_state.get('studio_selected_figure')
                if saved and saved[0]==signature:
                    st.download_button('Download selected figure (PNG)',saved[1],file_name='scientific-selected.png')
                st.caption('Saved fields only · one to four panels · PNG up to 200 dpi · no new scientific computation')
        names = [science.model_artifact, science.evidence_artifact]
        available = {item.name for item in result.artifacts}
        names.extend(name for name in ("scientific-overview.svg", "scientific-overview.pdf") if name in available)
        for name in names:
            label = 'Numerical model (NPZ)' if name==science.model_artifact else 'Numerical comparison (NPZ)' if name==science.evidence_artifact else 'Optional scientific figure'
            st.download_button(label, api.get_artifact(job_id, name), file_name=name, key="scientific_download_" + name)
    with evidence:
        render_evidence_tables(api, job_id, result)
    with details:
        st.dataframe([{'Assumption': line} for line in result.assumptions],hide_index=True,use_container_width=True)
        st.dataframe([{'Scientific limitation': line} for line in science.limitations],hide_index=True,use_container_width=True)
        with st.expander("Advanced / raw evidence and downloads"):
            for name in ("interaction.json", "validated-inputs.json", "workflow-plan.json", "scientific-qc.json", "trace.json", "world.json", "verification.json", science.manifest_artifact):
                try:
                    content = api.get_artifact(job_id, name)
                    st.json(json.loads(content),expanded=False)
                    st.download_button('Download raw evidence',content,file_name=name,key='scientific_evidence_'+name)
                except GeoWorldClientError:
                    st.caption('This evidence record is unavailable.')
            for item in result.artifacts:
                st.caption(item.name)


def render_evidence_tables(api, job_id, result):
    """Present recorded facts; absent records remain explicitly unavailable."""
    def record(name):
        try:
            return json.loads(api.get_artifact(job_id,name))
        except GeoWorldClientError:
            return {}
    plan, inputs, qc, world, verification = [record(name) for name in (
        'workflow-plan.json','validated-inputs.json','scientific-qc.json','world.json','verification.json')]
    st.markdown('**Scientific assumptions and limitations**')
    st.dataframe([{'Type':kind,'Recorded statement':line} for kind,lines in (
        ('Assumption',plan.get('assumptions',result.assumptions)),('Limitation',result.scientific.limitations))
        for line in lines],hide_index=True,use_container_width=True)
    st.markdown('**Selected scientific capabilities · execution order**')
    contracts = {row['contract']['capability_id']:row['contract'] for row in plan.get('contracts',[]) if 'contract' in row}
    st.dataframe([{'Order':i+1,'Method':contracts.get(name,{}).get('law_name',name),
        'Version':contracts.get(name,{}).get('version','Not recorded')} for i,name in enumerate(plan.get('steps',result.scientific.workflow))],hide_index=True,use_container_width=True)
    st.markdown('**Input parameters and units**')
    parameters=[{'Parameter':label,'Value':str(inputs.get('fluid_parameters',{}).get(key,'Not recorded')),'Unit':unit}
        for key,label,unit in [('pressure_mpa','Pore-fluid pressure','MPa'),('temperature_c','Fluid temperature','°C'),('salinity_mass_fraction','NaCl mass fraction','fraction')]]
    parameters += [{'Parameter':label,'Value':str(inputs.get(key,'Not recorded')),'Unit':unit}
        for key,label,unit in [('seeds','Realization seed','integer'),('saturations','CO₂ saturation states','fraction')]]
    st.dataframe(parameters,hide_index=True,use_container_width=True)
    st.markdown('**Numerical validation and controls**')
    labels={'saturation':'CO₂ saturation (fraction)','max_abs_delta_vp_m_s':'Maximum |ΔVp| (m/s)',
        'max_abs_delta_far':'Maximum |Δfar PP| (dimensionless)', 'maximum_outside_plume_change':'Outside-support change',
        'maximum_fixed_shear_error_pa':'Fixed-shear closure error (Pa)'}
    st.dataframe([{label:row[key] for key,label in labels.items() if key in row}
        for row in qc.get('metrics',result.scientific.metrics)],hide_index=True,use_container_width=True)
    st.markdown('**Scientific state lineage**')
    st.dataframe([{'State':row.get('state_id'),'Parent':row.get('parent_state_id') or 'Initial state',
        'Role':row.get('role'),'Representations':len(row.get('representation_refs',[]))}
        for row in world.get('states',[])],hide_index=True,use_container_width=True)
    st.markdown('**Recorded derivations and provenance inputs**')
    st.dataframe([{'Method':row.get('method','Not recorded'),
        'Input representations':', '.join(ref.get('subject_id','') for ref in row.get('inputs',[])) or 'Initial inputs',
        'Output representations':', '.join(ref.get('subject_id','') for ref in row.get('outputs',[]))}
        for row in world.get('provenance',[])],hide_index=True,use_container_width=True)
    st.markdown('**Source versions and artifact verification**')
    source=qc.get('source',{})
    st.dataframe([{'Evidence':key,'Recorded value':str(value)} for key,value in [
        ('Upstream algorithm commit',source.get('commit','Not recorded')),
        ('World validation',verification.get('world_valid','Not recorded')),
        ('Verified artifact entries',verification.get('verified_files','Not recorded'))]],hide_index=True,use_container_width=True)
