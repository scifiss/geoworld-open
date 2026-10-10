import json
from io import BytesIO
from PIL import Image
from test_studio_request import app, button
from geoworld_open.client import GeoWorldBackendClient, GeoWorldClientError
from geoworld_open.client.models import JobCreateResponse, JobStatusResponse, JobResult
from geoworld_open.client.studio_request import StudioDecision, StudioIntent
from geoworld_open.client.scientific_workflow import ScientificGoalAction, ScientificWorkflowPreview, ScientificWorkflowResult


def fixture_result(identity='a'*32):
    return JobResult(intent='scientific_workflow',reason='test contracts',answer='Scientific results and validation are ready.',
        scientific=ScientificWorkflowResult(preparation_id=identity,objective='fluid_avo',workflow=['sage.geology','sage.fluid','sage.forward','sage.render'],
            realization_count=1,saturation_count=4,figure_artifact='overview.png',model_artifact='model.npz',evidence_artifact='comparison.npz',manifest_artifact='scientific-manifest.json',limitations=['Synthetic fixture']))


def setup(monkeypatch):
    calls=[]
    goal=ScientificGoalAction(objective='fluid_avo')
    def interpret(self,prompt,**kwargs):
        return StudioDecision(interpretation=StudioIntent(operation='scientific'),route='scientific_workflow',action='scientific_goal',
            semantic_action=goal,message='Selected the validated workflow.',scientific=ScientificWorkflowPreview(request=prompt,
                preparation_id='a'*32,goal=goal,execution_allowed=True,automatic_execution=True,workflow=['sage.geology','sage.fluid','sage.forward','sage.render'],message='Selected the validated workflow.'))
    monkeypatch.setattr(GeoWorldBackendClient,'interpret_studio',interpret)
    monkeypatch.setattr(GeoWorldBackendClient,'submit_job',lambda _,r: calls.append(r) or JobCreateResponse(job_id='b'*32,status='queued',progress='queued'))
    monkeypatch.setattr(GeoWorldBackendClient,'get_job',lambda *_:JobStatusResponse(job_id='b'*32,status='succeeded',progress='done',result=fixture_result()))
    png=BytesIO();Image.new('RGB',(3,3),'white').save(png,format='PNG')
    def artifact(_,job_id,name):
        if name.endswith('.png'):return png.getvalue()
        if name=='scientific-section.json':return json.dumps({'time_s':[2,2.004], 'distance_m':[0,25], 'fields':{'sand_probability':{'values':[[.1,.2],[.3,.8]],'units':'1'}}}).encode()
        if name.endswith('.json'): return b'{}'
        return b'fixture binary'
    monkeypatch.setattr(GeoWorldBackendClient,'get_artifact',artifact)
    return calls


def test_single_assistant_runs_science_once_clears_composer_and_preserves_selection(app,monkeypatch):
    calls=setup(monkeypatch)
    app.run(timeout=20)
    prompt='Evaluate a controlled brine/CO2 change and its AVO response.'
    app.text_area(key='assistant_prompt').set_value(prompt)
    button(app,'Send').click().run(timeout=20)
    assert not app.exception
    assert len(calls)==1
    assert app.text_area(key='assistant_prompt').value==''
    assert app.get('plotly_chart')
    assert app.session_state['studio_task_context'].scientific.completed_job_id=='b'*32
    assert [m['content'] for m in app.session_state['assistant_history']]==[prompt,'Selected the validated workflow.','Scientific results and validation are ready.']
    app.slider(key='scientific_display_scale').set_value(80).run(timeout=20)
    assert len(calls)==1 and not app.exception
    app.run(timeout=20)
    assert len(calls)==1
    assert [t.label for t in app.tabs]==['Overview','Models & Figures','Scientific Evidence / Provenance','Complete Details']


def test_provider_failure_preserves_scientific_result_and_context(app,monkeypatch):
    calls=setup(monkeypatch);app.run(timeout=20)
    app.text_area(key='assistant_prompt').set_value('evaluate fluid AVO')
    button(app,'Send').click().run(timeout=20)
    before=app.session_state['studio_task_context']
    def failed(*args,**kwargs):raise GeoWorldClientError('Provider unavailable; prior context preserved')
    monkeypatch.setattr(GeoWorldBackendClient,'interpret_studio',failed)
    app.text_area(key='assistant_prompt').set_value('change the scenarios')
    button(app,'Send').click().run(timeout=20)
    assert not app.exception and len(calls)==1 and app.get('plotly_chart')
    assert app.session_state['studio_task_context']==before
    assert 'Provider unavailable' in app.session_state['assistant_history'][-1]['content']


def test_scientific_contract_roundtrip_through_http_json():
    preview=ScientificWorkflowPreview(request='scientific request',goal=ScientificGoalAction(objective='fluid_avo',saturations=(0,.2,.65)),message='prepared',estimated_seconds=(10,90))
    assert ScientificWorkflowPreview.model_validate(json.loads(preview.model_dump_json()))==preview


def test_absent_optional_vector_exports_do_not_block_completed_science(app,monkeypatch):
    calls=setup(monkeypatch)
    original=GeoWorldBackendClient.get_artifact
    requested=[]
    def artifact(self,job_id,name):
        requested.append(name)
        if name in {'scientific-overview.svg','scientific-overview.pdf'}:
            raise GeoWorldClientError('Optional publication export is not present')
        return original(self,job_id,name)
    monkeypatch.setattr(GeoWorldBackendClient,'get_artifact',artifact)
    app.run(timeout=20)
    app.text_area(key='assistant_prompt').set_value('evaluate fluid AVO')
    button(app,'Send').click().run(timeout=20)
    app.run(timeout=20)
    assert not app.exception and len(calls)==1 and app.get('plotly_chart')
    assert app.session_state['studio_task_context'].scientific.completed_job_id=='b'*32
    assert 'scientific-overview.svg' not in requested and 'scientific-overview.pdf' not in requested


def test_general_question_keeps_active_scientific_workspace(app,monkeypatch):
    calls=setup(monkeypatch);app.run(timeout=20)
    app.text_area(key='assistant_prompt').set_value('evaluate fluid AVO')
    button(app,'Send').click().run(timeout=20)
    monkeypatch.setattr(GeoWorldBackendClient,'interpret_studio',lambda *a,**kw: StudioDecision(
        interpretation=StudioIntent(operation='question'),route='ask_question',action='general_question',message='Answer question'))
    def get_job(_,job_id):
        result=fixture_result() if job_id=='b'*32 else JobResult(intent='qa',reason='test',answer='General answer')
        return JobStatusResponse(job_id=job_id,status='succeeded',progress='done',result=result)
    monkeypatch.setattr(GeoWorldBackendClient,'get_job',get_job)
    monkeypatch.setattr(GeoWorldBackendClient,'submit_job',lambda _,r: calls.append(r) or JobCreateResponse(job_id='c'*32,status='queued',progress='queued'))
    app.text_area(key='assistant_prompt').set_value('What is an unconformity?')
    button(app,'Send').click().run(timeout=20)
    assert not app.exception and app.get('plotly_chart') and len(calls)==2
    assert app.session_state['studio_task_context'].scientific.completed_job_id=='b'*32
    assert app.session_state['assistant_history'][-1]['content']=='General answer'


def test_scientific_context_survives_next_http_request(app,monkeypatch):
    from geoworld_open.client.studio_request import StudioRequest
    setup(monkeypatch);app.run(timeout=20)
    app.text_area(key='assistant_prompt').set_value('evaluate fluid AVO')
    button(app,'Send').click().run(timeout=20)
    current=app.session_state['studio_task_context']
    encoded=StudioRequest(prompt='change scenarios',context=current).model_dump(mode='json')
    assert StudioRequest.model_validate(encoded).context.active_task=='scientific'
    assert current.specialized_route is None


def test_reopen_scientific_run_restores_typed_context(app,monkeypatch):
    setup(monkeypatch)
    from geoworld_open.client.scientific_workflow import ScientificGoalAction
    original=GeoWorldBackendClient.get_artifact
    def artifact(self,job_id,name):
        if name=='interaction.json':return b'{"request":"Original scientific goal"}'
        if name=='workflow-plan.json':return json.dumps({'goal':ScientificGoalAction(objective='fluid_avo').model_dump(mode='json')}).encode()
        return original(self,job_id,name)
    monkeypatch.setattr(GeoWorldBackendClient,'get_artifact',artifact)
    app.run(timeout=20)
    app.text_input(key='saved_job_id').set_value('b'*32).run(timeout=20)
    button(app,'Open run').click().run(timeout=20)
    assert not app.exception and app.get('plotly_chart')
    assert app.session_state['studio_task_context'].scientific.completed_job_id=='b'*32
    assert app.session_state['last_submitted_prompt']=='Original scientific goal'
