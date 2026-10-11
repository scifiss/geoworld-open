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
        st.write("Validated scientific experiment")
        st.caption(" → ".join(preview.workflow))
        from geoworld_open.studio_scientific_workspace import workspace_tabs, assumption_rows
        model, results, evidence, advanced = workspace_tabs()
        with model:
            st.table(assumption_rows(preview.assumptions))
            st.caption('Independent benchmark inputs are bounded by its scientific contract; layer-table edits apply to ordinary GeoSpec models.')
            run = st.button("Run simulation", type="primary")
        with results:
            st.info('No simulation has completed for this preparation.')
        with evidence:
            st.dataframe([{'Scientific limitation':line} for line in preview.limitations],hide_index=True,width='stretch')
        with advanced:
            st.json(preview.model_dump(mode='json'), expanded=False)
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
    from geoworld_open.studio_scientific_workspace import workspace_tabs, assumption_rows, render_data_downloads, render_raw_artifacts
    model, models, evidence, details = workspace_tabs(completed=True)
    try:
        section = json.loads(api.get_artifact(job_id, "scientific-section.json"))
        from geoworld_open.studio_fields import DEFAULT_FIELDS, compose_fields, field_label
        defaults = [name for name in DEFAULT_FIELDS if name in section['fields']]
        if not defaults:
            defaults = list(section['fields'])[:4]
    except GeoWorldClientError as exc:
        st.warning(str(exc))
    with model:
        if 'section' in locals():
            background = next((name for name in ('sand_probability','porosity') if name in section['fields']), None)
            if background:
                st.plotly_chart(compose_fields(section, [background], identity=job_id+'inputs'),width='stretch',key='scientific_model_geometry')
        st.caption('Independent heterogeneous benchmark · inputs are fixed by its bounded scientific contract. Use the Assistant to prepare a supported new experiment.')
        try:
            inputs = json.loads(api.get_artifact(job_id,'validated-inputs.json'))
            st.dataframe([{'Parameter':label,'Value':str(inputs.get(key,'Not recorded'))} for key,label in
                [('seeds','Realization seed'),('saturations','CO₂ saturation states (fraction)')]],hide_index=True,width='stretch')
        except GeoWorldClientError as exc:
            st.warning(str(exc))
        st.markdown('**Recorded assumptions**')
        st.table(assumption_rows(result.assumptions))
    with models:
        st.caption('Completed numerical experiment · '+job_id[:8])
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
    with evidence:
        render_data_downloads(api,job_id,result.artifacts)
        render_evidence_tables(api, job_id, result)
    with details:
        render_raw_artifacts(api,job_id,result)


def render_evidence_tables(api, job_id, result):
    """Present recorded facts; absent records remain explicitly unavailable."""
    def record(name):
        try:
            return json.loads(api.get_artifact(job_id,name))
        except GeoWorldClientError:
            return {}
    plan, inputs, qc, world, verification = [record(name) for name in (
        'workflow-plan.json','validated-inputs.json','scientific-qc.json','world.json','verification.json')]
    st.markdown('**Scientific limitations**')
    st.dataframe([{'Recorded limitation':line} for line in result.scientific.limitations],hide_index=True,width='stretch')
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
