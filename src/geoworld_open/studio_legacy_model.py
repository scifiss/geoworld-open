"""PUBLIC_SDK_INFRA: one HTTP-only workspace for saved ordinary-model results."""
import json
from pathlib import PurePosixPath
import streamlit as st
from geoworld_open.client import GeoWorldClientError

LABELS={'facies':'Geological facies','porosity':'Porosity','vp':'P-wave velocity (Vp)',
    'vs':'S-wave velocity (Vs)','density':'Density','acoustic_impedance':'Acoustic impedance',
    'reflectivity':'Normal reflectivity','synthetic_seismic':'Synthetic seismic · depth domain',
    'sand_probability':'Sand lithology indicator','co2_saturation':'CO₂ saturation','fault_damage_mask':'Fault damage mask'}


def artifact_named(artifacts, basename):
    return next((artifact.name for artifact in artifacts
                 if PurePosixPath(artifact.name).name == basename), None)


def manifest_rows(value):
    inventory=value.get('artifacts',value.get('files',[]))
    if not isinstance(inventory,list):
        return []
    rows=[]
    for entry in inventory:
        checksum=entry.get('checksum') or {}
        rows.append({'Artifact':entry.get('uri') or entry.get('path') or 'Not recorded',
            'Bytes':entry.get('size_bytes') if entry.get('size_bytes') is not None else entry.get('bytes'),
            'SHA-256':checksum.get('digest') or entry.get('sha256') or 'Not recorded'})
    return rows


def field_catalog(artifacts):
    """Individual fields only: summary and AVO composites are downloadable extras."""
    result={}
    for artifact in artifacts:
        name=PurePosixPath(artifact.name).name
        if name.startswith('scientific_') and name.endswith('.png') and not name.endswith('_separate.png'):
            key=name[len('scientific_'):-4]
            if key in LABELS:
                result[key]=artifact.name
    return result


def render_legacy_model(api, job_id, result, options, *, render_inputs=None, pending=False):
    catalog=field_catalog(result.artifacts)
    record={}
    presentation=artifact_named(result.artifacts,'legacy-presentation.json')
    if presentation:
        try:
            record=json.loads(api.get_artifact(job_id,presentation))
        except (GeoWorldClientError,ValueError) as exc:
            st.warning('Recorded presentation metadata could not be read: '+str(exc))
    from geoworld_open.studio_scientific_workspace import workspace_tabs, render_data_downloads, render_raw_artifacts
    st.subheader('Scientific workspace')
    st.caption(('Previous completed experiment · new inputs await execution · ' if pending else 'Completed numerical experiment · ')+job_id[:8])
    model,figures,evidence,advanced=workspace_tabs(completed=not pending)
    with model:
        if render_inputs:
            render_inputs()
        elif record.get('parameters'):
            st.dataframe(display_parameters(record['parameters']),hide_index=True,width='stretch')
        else:
            st.info('This saved job predates the structured input table. Its original specification is available under Advanced.')
    with figures:
        defaults=[key for key in ('facies','porosity','co2_saturation') if key in catalog]
        chosen=st.multiselect('Scientific fields · selection order is plot order',list(catalog),default=defaults,
            format_func=lambda key:LABELS[key],key='legacy_fields_'+job_id)
        st.caption('Suggested calculated fields: Vp, Vs, density, acoustic impedance, reflectivity and synthetic seismic.')
        available_scales=['Shared absolute m/s scale','Separate display scales'] if record.get('velocity_shared_limits_m_s') else ['Separate saved display scales']
        scales = 'Shared absolute m/s scale' if record.get('velocity_shared_limits_m_s') else 'Separate saved display scales'
        if {'vp','vs'} <= set(chosen):
            scales=st.radio('Vp / Vs display scales',available_scales,horizontal=True,key='legacy_velocity_scale_'+job_id)
            bounds=record.get('velocity_shared_limits_m_s')
            st.caption(('Shared absolute m/s scale: '+f'{bounds[0]:g}–{bounds[1]:g} m/s.' if bounds else 'Shared scale availability is recorded for new runs.')
                if scales.startswith('Shared') else 'Separate display scales: compare absolute colorbar values, not colors across panels.')
        columns=st.columns(2)
        for index,key in enumerate(chosen):
            name=catalog[key]
            if key in {'vp','vs'} and scales.startswith('Separate'):
                alternative=name[:-4]+'_separate.png'
                if any(a.name==alternative for a in result.artifacts):
                    name=alternative
            with columns[index%2]:
                st.markdown('**'+LABELS[key]+'**')
                try:
                    if key == 'porosity' and artifact_named(result.artifacts, 'porosity.csv'):
                        render_porosity_percent(api, job_id, result)
                    else:
                        st.image(api.get_artifact(job_id,name),width='stretch' if options.fit_figures else options.figure_px)
                except GeoWorldClientError as exc:
                    st.warning(str(exc))
        if not catalog:
            aggregate=next((a.name for a in result.artifacts if PurePosixPath(a.name).name=='summary.png'),None)
            st.info('This older result contains an aggregate figure rather than selectable individual fields.')
            if aggregate:
                try:
                    st.image(api.get_artifact(job_id,aggregate),caption='Saved aggregate figure · older result',width='stretch' if options.fit_figures else options.figure_px)
                except GeoWorldClientError as exc:
                    st.warning(str(exc))
        for note in record.get('limitations',[]):
            st.caption(note)
    with evidence:
        render_data_downloads(api, job_id, result.artifacts)
        for label,rows in [('Execution methods',record.get('methods',[])),('Numerical outputs and validation',record.get('outputs',[]))]:
            st.markdown('**'+label+'**')
            if rows:
                st.dataframe(rows,hide_index=True,width='stretch')
        st.markdown('**Provenance and artifact integrity**')
        provenance=result.provenance_summary
        st.dataframe([{'Record':key,'Value':str(value)} for key,value in provenance.items()],hide_index=True,width='stretch')
        manifest=artifact_named(result.artifacts,'manifest.json')
        if manifest:
            try:
                value=json.loads(api.get_artifact(job_id,manifest))
                rows=manifest_rows(value)
                if rows:
                    st.dataframe(rows,hide_index=True,width='stretch')
            except (ValueError,GeoWorldClientError) as exc:
                st.warning(str(exc))
        st.caption('Recorded hashes identify saved artifacts. Displaying this table does not independently recompute file verification.')
    with advanced:
        if st.button('Prepare complete run export',key='workspace_prepare_export_'+job_id):
            try:
                st.session_state['workspace_run_export']=(job_id,api.get_export(job_id))
            except GeoWorldClientError as exc:
                st.caption(str(exc))
        saved=st.session_state.get('workspace_run_export')
        if saved and saved[0]==job_id:
            st.download_button('Download complete run export',saved[1],file_name=f'geoworld-run-{job_id}.html',mime='text/html',on_click='ignore')
        render_raw_artifacts(api, job_id, result)


def display_parameters(rows):
    """Human display units only; recorded artifacts retain fractional porosity."""
    output=[]
    for row in rows:
        row=dict(row)
        if 'porosity' in row['Parameter'].casefold() and row['Value'].endswith(' fraction'):
            row['Value']=f"{float(row['Value'].removesuffix(' fraction'))*100:g}%"
        output.append(row)
    return output


def render_porosity_percent(api, job_id, result):
    import io
    import numpy as np
    import plotly.graph_objects as go
    values=np.loadtxt(io.BytesIO(api.get_artifact(job_id,artifact_named(result.artifacts,'porosity.csv'))),delimiter=',')
    grid=result.geospec['grid']
    figure=go.Figure(go.Heatmap(x=np.arange(values.shape[1])*grid['dx_m'],
        y=np.arange(values.shape[0])*grid['dz_m'], z=values*100,
        colorscale='Cividis', colorbar=dict(title='Porosity (%)')))
    figure.update_layout(xaxis_title='Distance (m)',yaxis_title='Depth (m)',height=380,
        margin=dict(l=55,r=20,t=20,b=50))
    figure.update_yaxes(autorange='reversed')
    st.plotly_chart(figure,width='stretch',key='ordinary_porosity_'+job_id)
