"""Offline HTTP boundary fixture; runs the production Studio UI."""
from pathlib import Path
from copy import deepcopy
import runpy
import streamlit as st
from geoworld_open.client import GeoWorldBackendClient, GeoWorldClientError
from geoworld_open.client.models import JobCreateResponse,JobStatusResponse,JobResult
from geoworld_open.client.studio_request import StudioDecision,StudioIntent
import json

st.session_state.setdefault('access_token','test-only-token')
st.session_state.setdefault('user_email','fixture@example.test')

def interpret(_self,prompt,**kwargs):
    if prompt.casefold()=='run it':
        return StudioDecision(interpretation=StudioIntent(operation='build'),route='build_model',action='run_prepared_build',message='Run the reviewed GeoSpec.')
    existing=kwargs['context'].build
    spec=deepcopy(existing.geospec) if existing else {'grid':{'nx':2,'nz':4,'dx_m':1000,'dz_m':200},'geology':{'layers':[{'lithology':'shale'},{'lithology':'sand','porosity':.2},{'lithology':'carbonate','porosity':.3},{'lithology':'shale'}]}}
    if existing:
        spec['geology']['layers'][2]['porosity']=.25
    return StudioDecision(interpretation=StudioIntent(operation='build'),route='build_model',action='patch_build' if existing else 'new_task',continues_build=existing is not None,build_spec=spec,message='Review the prepared model.')

def preview(_self,**kwargs):
    spec=kwargs['geospec']
    rows=[{'index':index,'lithology':layer['lithology'],'thickness_m':200,'porosity':layer.get('porosity',.08),'vp':3000,'vs':1500,'density':2300,'sources':{'lithology':'user','porosity':'user' if layer.get('porosity') else 'default','vp':'derived','vs':'derived','density':'derived','thickness_m':'default'}} for index,layer in enumerate(spec['geology']['layers'])]
    return {'valid':True,'geospec':spec,'assumptions':['Offline fixture policy values; no field interpretation.'],'model_preview':{'layers':rows,'x_m':[0,1000],'z_m':[0,200,400,600],'layer_indices':[[1,1],[2,2],[3,3],[4,4]],'co2_enabled':False,'fault_count':0,'note':'Prepared geometry; no numerical execution yet.'}}

def submit(_self,request):
    st.session_state['fixture_submissions']=st.session_state.get('fixture_submissions',0)+1
    st.session_state['fixture_submitted_spec']=request.geospec
    return JobCreateResponse(job_id='a'*32,status='queued',progress='queued')

GeoWorldBackendClient.interpret_studio=interpret
GeoWorldBackendClient.preview_geospec=preview
GeoWorldBackendClient.submit_job=submit
def result(*_):
    from geoworld_open.client.models import ArtifactInfo
    names=['scientific_facies.png','scientific_porosity.png','scientific_vp.png','scientific_vs.png','porosity.csv','legacy-presentation.json']
    return JobStatusResponse(job_id='a'*32,status='succeeded',progress='done',result=JobResult(intent='build_model',reason='offline fixture',
        answer='Submitted exact reviewed GeoSpec.',geospec=st.session_state.get('fixture_submitted_spec'),
        artifacts=[ArtifactInfo(name=name,kind='file',size_bytes=len(artifact(None,None,name))) for name in names]))

def artifact(_self,job_id,name):
    if name.endswith('.png'):
        # Transparent fixture fields, not an unrelated demonstration dashboard.
        import io
        import numpy as np
        from matplotlib.figure import Figure
        spec=st.session_state['fixture_submitted_spec']
        field=name.removeprefix('scientific_').removesuffix('.png')
        values={'facies':[0,1,2,0],
            'porosity':[layer.get('porosity',.08) for layer in spec['geology']['layers']],
            'vp':[3000]*4,'vs':[1500]*4}[field]
        units={'facies':'category','porosity':'fraction','vp':'m/s','vs':'m/s'}
        figure=Figure(figsize=(6,3),layout='constrained')
        axis=figure.subplots()
        limits={'vmin':1000,'vmax':5000} if field in {'vp','vs'} else {}
        image=axis.imshow(np.repeat(np.array(values)[:,None],2,axis=1),extent=(-500,1500,700,-100),aspect='auto',**limits)
        axis.set(xlabel='Distance (m)',ylabel='Depth (m)',title=f'{field} · offline fixture')
        bar=figure.colorbar(image,ax=axis,label=units[field])
        if field=='facies':
            bar.set_ticks([0,1,2],labels=['shale','sand','carbonate'])
        output=io.BytesIO();figure.savefig(output,format='png',dpi=100)
        return output.getvalue()
    if name.endswith('.csv'):
        return b'.08,.08\n.22,.22\n.25,.25\n.08,.08\n'
    return json.dumps({'parameters':[{'Parameter':'Grid','Value':'2 x 4','Source':'Fixture'}],
        'velocity_shared_limits_m_s':[1000,5000]}).encode()
GeoWorldBackendClient.get_job=result
GeoWorldBackendClient.get_artifact=artifact
GeoWorldBackendClient.get_llm_health=lambda *_:{'reachable':True,'details':{}}
GeoWorldBackendClient.get_export=lambda *_: (_ for _ in ()).throw(GeoWorldClientError('Offline fixture'))
runpy.run_path(str(Path(__file__).parents[2]/'apps/studio_streamlit.py'),run_name='__main__')
st.caption('Fixture submissions: '+str(st.session_state.get('fixture_submissions',0)))
if st.session_state.get('fixture_submitted_spec'):
    st.caption('Executed carbonate porosity: '+str(st.session_state['fixture_submitted_spec']['geology']['layers'][2]['porosity']))
    st.caption('Executed sand porosity: '+str(st.session_state['fixture_submitted_spec']['geology']['layers'][1]['porosity']))
