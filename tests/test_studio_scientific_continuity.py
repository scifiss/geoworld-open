"""Conversation stays distinct from the active scientific workspace."""
from test_studio_request import app,button
from test_studio_scientific import setup
from geoworld_open.client import GeoWorldBackendClient
from geoworld_open.client.studio_request import EvidenceAssessmentReceipt,StudioDecision,StudioIntent
from geoworld_open.studio_fields import compose_fields


def test_three_saved_evidence_questions_share_one_job_and_single_chat_answers(app,monkeypatch):
    calls=setup(monkeypatch)
    app.run(timeout=20)
    app.text_area(key='assistant_prompt').set_value('Evaluate an independent synthetic fluid experiment')
    button(app,'Send').click().run(timeout=20)
    active=app.session_state['studio_task_context'].scientific
    received=[]
    def assess(self,prompt,**kwargs):
        assert kwargs['context'].scientific.completed_job_id==active.completed_job_id
        received.append(prompt)
        receipt=EvidenceAssessmentReceipt(record_id='d'*64,source_job_id=active.completed_job_id,
            objective='fluid_pp_causality',answer='Saved evidence answer '+str(len(received)),
            conclusion='Synthetic only',evidence_count=14,gaps=['observations'])
        return StudioDecision(interpretation=StudioIntent(operation='question'),route='ask_question',
            message=receipt.answer,evidence_assessment=receipt)
    monkeypatch.setattr(GeoWorldBackendClient,'interpret_studio',assess)
    questions=['Why did the seismic response change?','Explain the changed seismic amplitudes and assumptions.',
        'Why do the reflected waveforms differ after replacing brine?']
    for i,question in enumerate(questions):
        app.text_area(key='assistant_prompt').set_value(question)
        button(app,'Send').click().run(timeout=20)
        app.run(timeout=20)
        assert not app.exception and app.get('plotly_chart')
        assert app.session_state['studio_task_context'].scientific==active
        messages=app.session_state['assistant_history']
        assert sum(m['content']==question for m in messages)==1
        assert sum(m['content']=='Saved evidence answer '+str(i+1) for m in messages)==1
        # No duplicate answer is rendered in the scientific workspace.
        assert sum('Saved evidence answer '+str(i+1)==m.value for m in app.markdown)==1
    assert len(calls)==1 and received==questions


def test_composition_matches_saved_arrays_units_coordinates_and_requested_order():
    fields={name:{'values':[[i,i+1],[i+2,i+3]],'units':unit} for i,(name,unit) in enumerate([
        ('porosity','1'),('co2_saturation','1'),('delta_vp','m/s'),('delta_far','1')])}
    section={'fields':fields,'time_s':[0.,.0025],'distance_m':[0.,30.]}
    order=['delta_far','porosity','delta_vp','co2_saturation']
    fig=compose_fields(section,order,identity='owned-job')
    for trace,name in zip(fig.data,order):
        assert trace.z.tolist()==fields[name]['values']
        assert list(trace.x)==[0.,.03] and list(trace.y)==section['time_s']
        assert trace.colorbar.title.text==fields[name]['units']
    assert [a.text for a in fig.layout.annotations][0]=='Far-angle PP response change'


def test_selected_fields_reorder_survives_rerender_without_numerical_job(app,monkeypatch):
    import json
    calls=setup(monkeypatch)
    original=GeoWorldBackendClient.get_artifact
    names=['porosity','co2_saturation','delta_vp','delta_far']
    def artifact(self,job,name):
        if name=='scientific-section.json':
            return json.dumps({'time_s':[0,.0025],'distance_m':[0,30],
                'fields':{n:{'values':[[0,1],[2,3]],'units':'m/s' if n=='delta_vp' else '1'} for n in names}}).encode()
        return original(self,job,name)
    monkeypatch.setattr(GeoWorldBackendClient,'get_artifact',artifact)
    app.run(timeout=20)
    app.text_area(key='assistant_prompt').set_value('Evaluate a synthetic fluid experiment')
    button(app,'Send').click().run(timeout=20)
    app.multiselect(key='scientific_selected_fields').set_value(['porosity','delta_vp','delta_far']).run(timeout=20)
    app.selectbox(key='scientific_reorder_field').select('delta_far').run(timeout=20)
    button(app,'Move earlier').click().run(timeout=20)
    assert app.session_state['scientific_panel_order']==['porosity','delta_far','delta_vp']
    app.run(timeout=20)
    assert not app.exception and app.session_state['scientific_panel_order']==['porosity','delta_far','delta_vp']
    assert len(calls)==1


def test_restore_keeps_full_history_active_science_and_owner_session_cleanup(app,monkeypatch):
    from uuid import uuid4
    from geoworld_open.client.studio_session import StudioConversation
    from geoworld_open.client.scientific_workflow import ScientificExperimentContext, ScientificGoalAction
    calls=setup(monkeypatch)
    history=[{'role':'user','content':'Original scientific goal'},
        {'role':'assistant','content':'Completed numerical science'},
        {'role':'user','content':'Why did the response change?'},
        {'role':'assistant','content':'Saved evidence explains the conditional response'}]
    record=StudioConversation(conversation_id=uuid4().hex,revision=3,messages=history,
        active_scientific_job_id='b'*32,updated_at='2026-10-10T12:00:00+00:00',
        expires_at='2026-10-10T15:00:00+00:00',selected_fields=['sand_probability'],
        scientific_context=ScientificExperimentContext(preparation_id='a'*32,
            completed_job_id='b'*32,goal=ScientificGoalAction(objective='fluid_avo')))
    monkeypatch.setattr(GeoWorldBackendClient,'recent_studio_conversations',lambda _: [record])
    monkeypatch.setattr(GeoWorldBackendClient,'restore_studio_conversation',lambda *_: record)
    monkeypatch.setattr(GeoWorldBackendClient,'save_studio_conversation',
        lambda _,identity,request:record.model_copy(update={'revision':request.revision+1}))
    app.run(timeout=20)
    button(app,'Restore conversation and results').click().run(timeout=20)
    assert not app.exception and app.get('plotly_chart')
    assert app.session_state['assistant_history']==history
    assert app.session_state['studio_task_context'].scientific==record.scientific_context
    assert app.session_state['scientific_panel_order']==['sand_probability']
    app.run(timeout=20)
    assert app.session_state['assistant_history']==history and calls==[]
    button(app,'Log out').click().run(timeout=20)
    for key in ('scientific_panel_order','scientific_selected_fields','scientific_reorder_field',
                'studio_task_context','studio_conversation_id','assistant_history','assistant_job_seen'):
        assert key not in app.session_state
