"""Offline HTTP boundary fixture; runs the production Studio UI."""
from pathlib import Path
from copy import deepcopy
import runpy
import streamlit as st
from geoworld_open.client import GeoWorldBackendClient, GeoWorldClientError
from geoworld_open.client.models import JobCreateResponse,JobStatusResponse,JobResult
from geoworld_open.client.studio_request import StudioDecision,StudioIntent

st.session_state.setdefault('access_token','test-only-token')
st.session_state.setdefault('user_email','fixture@example.test')

def interpret(_self,prompt,**kwargs):
    if prompt.casefold()=='run it':
        return StudioDecision(interpretation=StudioIntent(operation='build'),route='build_model',action='run_prepared_build',message='Run the reviewed GeoSpec.')
    existing=kwargs['context'].build
    spec=deepcopy(existing.geospec) if existing else {'geology':{'layers':[{'lithology':'shale'},{'lithology':'sand','porosity':.2},{'lithology':'carbonate','porosity':.3},{'lithology':'shale'}]}}
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
GeoWorldBackendClient.get_job=lambda *_:JobStatusResponse(job_id='a'*32,status='succeeded',progress='done',result=JobResult(intent='build_model',reason='offline fixture',answer='Submitted exact reviewed GeoSpec.'))
GeoWorldBackendClient.get_llm_health=lambda *_:{'reachable':True,'details':{}}
GeoWorldBackendClient.get_export=lambda *_: (_ for _ in ()).throw(GeoWorldClientError('Offline fixture'))
runpy.run_path(str(Path(__file__).parents[2]/'apps/studio_streamlit.py'),run_name='__main__')
st.caption('Fixture submissions: '+str(st.session_state.get('fixture_submissions',0)))
if st.session_state.get('fixture_submitted_spec'):
    st.caption('Executed carbonate porosity: '+str(st.session_state['fixture_submitted_spec']['geology']['layers'][2]['porosity']))
