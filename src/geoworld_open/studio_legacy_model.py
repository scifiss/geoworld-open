"""PUBLIC_SDK_INFRA: one HTTP-only workspace for saved ordinary-model results."""
import json
from pathlib import PurePosixPath
import streamlit as st
from geoworld_open.client import GeoWorldClientError

LABELS={'facies':'Geological facies','porosity':'Porosity','vp':'P-wave velocity (Vp)',
    'vs':'S-wave velocity (Vs)','density':'Density','acoustic_impedance':'Acoustic impedance',
    'reflectivity':'Normal reflectivity','synthetic_seismic':'Synthetic seismic · depth domain',
    'sand_probability':'Sand lithology indicator','co2_saturation':'CO₂ saturation','fault_damage_mask':'Fault damage mask'}


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


def render_legacy_model(api, job_id, result, options):
    catalog=field_catalog(result.artifacts)
    record={}
    presentation=next((a.name for a in result.artifacts if a.name.endswith('/legacy-presentation.json')),None)
    if presentation:
        try:
            record=json.loads(api.get_artifact(job_id,presentation))
        except (GeoWorldClientError,ValueError) as exc:
            st.warning('Recorded presentation metadata could not be read: '+str(exc))
    st.subheader('Scientific Figures')
    if record.get('parameters'):
        st.markdown('**Inputs, assumptions and calculated properties**')
        st.dataframe(record['parameters'],hide_index=True,width='stretch',height=280)
    else:
        st.info('This saved job predates the structured parameter table. Original GeoSpec and scenario remain available in downloads.')
    figures,evidence,downloads=st.tabs(['Scientific Figures','Evidence / provenance','Advanced / downloads'])
    with figures:
        defaults=[key for key in ('facies','porosity','co2_saturation') if key in catalog]
        chosen=st.multiselect('Scientific fields · selection order is plot order',list(catalog),default=defaults,
            format_func=lambda key:LABELS[key],key='legacy_fields_'+job_id)
        st.caption('Suggested calculated fields: Vp, Vs, density, acoustic impedance, reflectivity and synthetic seismic.')
        available_scales=['Shared absolute m/s scale','Separate display scales'] if record.get('velocity_shared_limits_m_s') else ['Separate saved display scales']
        scales=st.radio('Vp / Vs display scales',available_scales,horizontal=True,key='legacy_velocity_scale_'+job_id)
        if 'vp' in chosen or 'vs' in chosen:
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
        for label,rows in [('Execution methods',record.get('methods',[])),('Numerical outputs and validation',record.get('outputs',[]))]:
            st.markdown('**'+label+'**')
            if rows:
                st.dataframe(rows,hide_index=True,width='stretch')
        st.markdown('**Provenance and artifact integrity**')
        provenance=result.provenance_summary
        st.dataframe([{'Record':key,'Value':str(value)} for key,value in provenance.items()],hide_index=True,width='stretch')
        manifest=next((a for a in result.artifacts if a.name=='manifest.json'),None)
        if manifest:
            try:
                value=json.loads(api.get_artifact(job_id,manifest.name))
                inventory=value.get('artifacts',value.get('files',[]))
                if isinstance(inventory,list):
                    st.dataframe([{'Artifact':entry.get('uri','Not recorded'),'Bytes':entry.get('size_bytes'),
                        'SHA-256':entry.get('checksum',{}).get('digest','Not recorded')} for entry in inventory],hide_index=True,width='stretch')
            except (ValueError,GeoWorldClientError) as exc:
                st.warning(str(exc))
        st.caption('Recorded hashes identify saved artifacts. Displaying this table does not independently recompute file verification.')
    with downloads:
        try:
            st.download_button('Download complete run export',api.get_export(job_id),file_name=f'geoworld-run-{job_id}.html',mime='text/html')
        except GeoWorldClientError as exc:
            st.caption(str(exc))
        # Fetch a selected artifact rather than every numerical CSV on each rerun.
        names=[a.name for a in result.artifacts]
        if names:
            selected=st.selectbox('Saved artifact',names,key='legacy_download_'+job_id)
            if st.button('Prepare selected download',key='legacy_prepare_download_'+job_id):
                try:
                    payload=api.get_artifact(job_id,selected)
                    st.download_button('Download selected artifact',payload,file_name=PurePosixPath(selected).name,key='legacy_download_button_'+job_id)
                except GeoWorldClientError as exc:
                    st.warning(str(exc))
        with st.expander('Raw GeoSpec and result metadata'):
            st.json(result.geospec)
            st.json(result.model_dump(mode='json'))
