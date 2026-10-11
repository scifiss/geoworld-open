"""Transport loss retains accepted identity and prior results across rerenders."""
import pytest
from geoworld_open.client.backend import GeoWorldBackendClient,GeoWorldClientError
from geoworld_open.client.models import JobCreateResponse,JobStatusResponse,JobResult
from geoworld_open.client.studio_request import StudioDecision,StudioIntent
from test_studio_request import app,completed,button


@pytest.mark.parametrize('status',[502,503,504])
def test_gateway_failure_does_not_claim_scientific_failure(status):
    message=GeoWorldBackendClient._error_message(status,b'<html>upstream unavailable</html>')
    assert str(status) in message and 'does not confirm a scientific failure' in message
    assert '<html>' not in message and 'before resubmitting' in message


def test_lost_accepted_job_reconnects_without_resubmission_or_result_loss(app,monkeypatch):
    submitted=[]
    def submit(_,request):
        submitted.append(request)
        return JobCreateResponse(job_id='b'*32,status='queued',progress='accepted')
    monkeypatch.setattr(GeoWorldBackendClient,'submit_job',submit)
    monkeypatch.setattr(GeoWorldBackendClient,'interpret_studio',lambda *a,**kw:
        StudioDecision(interpretation=StudioIntent(operation='question'),route='ask_question',message='Answer selected'))
    monkeypatch.setattr(GeoWorldBackendClient,'get_job',lambda *a:
        (_ for _ in ()).throw(GeoWorldClientError('Connection lost (HTTP 502); outcome unconfirmed')))
    completed(app)
    app.run(timeout=20)
    app.text_area(key='assistant_prompt').set_value('Explain this experiment').run()
    button(app,'Send').click().run(timeout=20)
    assert not app.exception and len(submitted)==1
    assert app.session_state['last_job_id']=='a'*32
    assert app.session_state['studio_interrupted_submission']['job_id']=='b'*32
    app.run(timeout=20)
    assert len(submitted)==1
    assert any('outcome is unconfirmed' in warning.value for warning in app.warning)
    recovered=JobStatusResponse(job_id='b'*32,status='succeeded',progress='complete',
        result=JobResult(intent='qa',reason='saved answer',answer='Recovered existing answer'))
    monkeypatch.setattr(GeoWorldBackendClient,'get_job',lambda *a:recovered)
    button(app,'Reconnect to submitted job').click().run(timeout=20)
    assert not app.exception and len(submitted)==1
    assert app.session_state['last_job_id']=='b'*32
    assert app.session_state['last_job'].result.answer=='Recovered existing answer'
    assert 'studio_interrupted_submission' not in app.session_state
