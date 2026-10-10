"""Generic receipt presentation preserves the one Assistant and saved workspace."""
from test_studio_request import app, button
from test_studio_scientific import setup
from geoworld_open.client import GeoWorldBackendClient
from geoworld_open.client.studio_request import EvidenceAssessmentReceipt, StudioDecision, StudioIntent


def test_completed_assessment_creates_no_job_and_preserves_science_across_reruns(app,monkeypatch):
    calls=setup(monkeypatch)
    app.run(timeout=20)
    app.text_area(key='assistant_prompt').set_value('evaluate fluid AVO')
    button(app,'Send').click().run(timeout=20)
    before=app.session_state['studio_task_context'].scientific
    receipt=EvidenceAssessmentReceipt(record_id='d'*64,source_job_id=before.completed_job_id,
        objective='fluid_pp_causality',answer='Saved evidence supports a conditional synthetic response, not field CO2 attribution.',
        conclusion='Synthetic only.',evidence_count=14,gaps=['observations','calibration','uniqueness'])
    monkeypatch.setattr(GeoWorldBackendClient,'interpret_studio',lambda *_,**kw:StudioDecision(
        interpretation=StudioIntent(operation='question'),route='ask_question',action='general_question',
        message=receipt.answer,evidence_assessment=receipt))
    question='Why does the far-angle PP response change?'
    app.text_area(key='assistant_prompt').set_value(question)
    button(app,'Send').click().run(timeout=20)
    assert not app.exception and len(calls)==1
    assert app.text_area(key='assistant_prompt').value==''
    assert app.get('plotly_chart')
    assert app.session_state['studio_task_context'].scientific==before
    assert [m['content'] for m in app.session_state['assistant_history']][-2:]==[question,receipt.answer]
    app.run(timeout=20)
    assert not app.exception and len(calls)==1 and app.get('plotly_chart')
