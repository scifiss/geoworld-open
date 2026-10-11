"""State and unit regressions using real Streamlit reruns at the HTTP boundary."""
import io
import json
from copy import deepcopy
from hashlib import sha256
import zipfile
import pytest
from test_studio_request import app, button
from geoworld_open.client import GeoWorldBackendClient
from geoworld_open.client.models import ArtifactInfo, JobResult, JobStatusResponse, JobCreateResponse
from geoworld_open.client.semantic_action import NewBuild, RequestedLayer
from geoworld_open.client.studio_request import StudioDecision, StudioIntent
from geoworld_open.studio_model_preview import apply_primary_edits, primary_rows
from geoworld_open.studio_scientific_workspace import build_data_package, package_inventory, WORKSPACE_TABS


def setup(monkeypatch, *, automatic=False):
    spec={'grid':{'dimension':'2d','nx':100,'nz':100,'dx_m':10,'dz_m':5},
          'geology':{'layers':[{'lithology':'shale','porosity':None,'thickness_m':None},
                               {'lithology':'sand','porosity':.2,'thickness_m':None}]}}
    previews, jobs=[], []
    action=NewBuild(layers=[RequestedLayer(lithology='shale'),RequestedLayer(lithology='sand',porosity=.2)])
    monkeypatch.setattr(GeoWorldBackendClient,'interpret_studio',lambda *a,**k: StudioDecision(
        interpretation=StudioIntent(operation='build',prepare_only=not automatic),route='build_model',
        action='new_task',build_spec=spec,semantic_action=action,message='Prepared'))
    def preview(_,**kwargs):
        payload=deepcopy(kwargs['geospec']);previews.append(payload)
        valid=all(layer.get('porosity') is None or layer['porosity']<=.4 for layer in payload['geology']['layers'])
        rows=[{'index':i,'lithology':layer['lithology'],'porosity':layer['porosity'] or .08,
            'thickness_m':layer.get('thickness_m') or 200.,'vp':3000.,'vs':1500.,'density':2300.,
            'sources':{'porosity':'user' if layer['porosity'] else 'default'}} for i,layer in enumerate(payload['geology']['layers'])]
        return {'valid':valid,'geospec':payload,'issues':[] if valid else [{'severity':'error','message':'Porosity exceeds policy'}],
            'assumptions':['Documented defaults','Documented defaults'], 'model_preview':{'layers':rows,
                'layer_indices':[[1,1],[2,2]],'x_m':[0,100],'z_m':[0,200],
                'co2_enabled':False,'fault_count':0,'note':'Geometry preview'}}
    monkeypatch.setattr(GeoWorldBackendClient,'preview_geospec',preview)
    monkeypatch.setattr(GeoWorldBackendClient,'submit_job',lambda _,request: jobs.append(request) or
        JobCreateResponse(job_id=str(len(jobs))*32,status='queued',progress='queued'))
    monkeypatch.setattr(GeoWorldBackendClient,'get_job',lambda _,job_id: JobStatusResponse(job_id=job_id,
        status='succeeded',progress='done',result=JobResult(intent='build_model',reason='test',answer='done',
            geospec=jobs[int(job_id[0])-1].geospec)))
    return previews,jobs


def edit(app, value):
    spec=app.session_state['studio_task_context'].build.geospec
    revision=sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest()[:12]
    app.session_state['model_layer_editor_'+revision]={'edited_rows':{1:value},'added_rows':[],'deleted_rows':[]}
    button(app,'Apply layer edits').click().run(timeout=20)


def test_prepare_edit_execute_then_new_experiment_preserves_previous_result(app,monkeypatch):
    previews,jobs=setup(monkeypatch)
    app.run(timeout=20)
    app.text_area(key='assistant_prompt').set_value('Prepare shale and sand, porosity .20')
    button(app,'Send').click().run(timeout=20)
    assert len(previews)==1 and not jobs and not app.exception
    assert [t.label for t in app.tabs]==list(WORKSPACE_TABS)
    assert not any(b.label=='Prepare model' for b in app.button)
    edit(app,{'Porosity (%)':22.,'Thickness (m)':150.,'Lithology':'carbonate'})
    assert not jobs and not app.exception and len(previews)==2
    current=app.session_state['studio_task_context'].build.geospec['geology']['layers'][1]
    assert current['porosity']==.22 and current['thickness_m']==150 and current['lithology']=='carbonate'
    button(app,'Run simulation').click().run(timeout=20)
    assert len(jobs)==1 and not app.exception
    assert not any(b.label=='Run simulation' for b in app.button)
    prior=app.session_state['studio_build_completed_job']
    app.run(timeout=20)
    assert len(jobs)==1 and len(previews)==2
    edit(app,{'Porosity (%)':24.})
    assert len(jobs)==1 and app.session_state['studio_build_completed_job']==prior
    assert any('Previous completed experiment' in c.value for c in app.caption)
    button(app,'Run simulation').click().run(timeout=20)
    assert len(jobs)==2 and jobs[0].geospec!=jobs[1].geospec
    assert app.session_state['last_job_id']!=prior.job_id


def test_automatic_completion_has_no_second_run_controls_and_edits_do_not_autorun(app,monkeypatch):
    previews,jobs=setup(monkeypatch,automatic=True)
    app.run(timeout=20)
    app.text_area(key='assistant_prompt').set_value('Build shale and sand, porosity .20')
    button(app,'Send').click().run(timeout=20)
    assert len(jobs)==len(previews)==1 and not app.exception
    assert not any(b.label in {'Run simulation','Prepare model','Run model'} for b in app.button)
    edit(app,{'Porosity (%)':23.})
    app.run(timeout=20)
    assert len(jobs)==1 and len(previews)==2
    assert not button(app,'Run simulation').disabled


def test_rejected_edit_keeps_valid_spec_and_completed_result(app,monkeypatch):
    previews,jobs=setup(monkeypatch,automatic=True)
    app.run(timeout=20)
    app.text_area(key='assistant_prompt').set_value('Build shale sand .20')
    button(app,'Send').click().run(timeout=20)
    prior=deepcopy(app.session_state['studio_task_context'].build.geospec)
    edit(app,{'Porosity (%)':90.})
    assert not app.exception and len(jobs)==1
    assert app.session_state['studio_task_context'].build.geospec==prior
    assert any('Porosity exceeds policy' in w.value for w in app.warning)


def test_percent_display_does_not_change_fractional_data_or_derived_values():
    row={'index':0,'lithology':'sand','porosity':.2,'thickness_m':100,'vp':3000,'vs':1500,'density':2300}
    original={'geology':{'layers':[{'lithology':'sand','porosity':.2,'thickness_m':100,'porosity_range':None}]}}
    edits=primary_rows([row]); assert edits[0]['Porosity (%)']==20
    edits[0]['Porosity (%)']=25; edits[0]['Vp (m/s)']=999
    changed=apply_primary_edits(original,[row],edits)
    assert changed['geology']['layers'][0]['porosity']==.25
    assert 'vp' not in changed['geology']['layers'][0] and original['geology']['layers'][0]['porosity']==.2


def test_data_package_preserves_bytes_and_rejects_unbounded_or_unsafe_inventory():
    data=b'.20,.30\n'
    artifact=ArtifactInfo(name='run/porosity.csv',size_bytes=len(data))
    class API:
        def get_artifact(self,*args): return data
    package=build_data_package(API(),'job',[artifact])
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        assert archive.read(artifact.name)==data
        manifest=json.loads(archive.read('download-manifest.json'))
        assert manifest['artifacts'][0]['sha256']==sha256(data).hexdigest()
    assert not package_inventory([artifact.model_copy(update={'size_bytes':None})])
    assert not package_inventory([artifact.model_copy(update={'size_bytes':33*1024**2})])
    with pytest.raises(ValueError,match='Unsafe'):
        build_data_package(API(),'job',[artifact.model_copy(update={'name':'../porosity.csv'})])
    with pytest.raises(ValueError,match='size'):
        build_data_package(API(),'job',[artifact.model_copy(update={'size_bytes':1})])
