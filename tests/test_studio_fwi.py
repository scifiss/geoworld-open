from pathlib import Path
import pytest
from test_execution_contracts import example_plan


def test_fwi_preflight_preview_and_prepare_only_never_run(monkeypatch):
    pytest.importorskip('streamlit')
    from streamlit.testing.v1 import AppTest
    from geoworld_open.client import GeoWorldBackendClient
    from geoworld_open.client.fwi import FWIPreview,FWISelection
    from geoworld_open.client.studio_request import StudioDecision,StudioIntent
    monkeypatch.setenv('GEOWORLD_BACKEND_URL','http://127.0.0.1:8100')
    monkeypatch.setenv('GEOWORLD_STUDIO_LOCAL_RTM','1')
    monkeypatch.setattr(GeoWorldBackendClient,'get_llm_health',lambda _: {'reachable':True})
    monkeypatch.setattr(GeoWorldBackendClient,'interpret_studio',lambda *_:StudioDecision(
        interpretation=StudioIntent(operation='fwi',dataset='marmousi1'),route='bounded_fwi',message='Bounded FWI'))
    monkeypatch.setattr(GeoWorldBackendClient,'preview_fwi',lambda *_a,**_k:FWIPreview(
        selection=FWISelection(action='prepare'),preparation_id='a'*32,runnable=False,settings={},execution_plan=example_plan(),
        model_preview=dict(x_m=[0,4],z_m=[0,4],initial_velocity=[[1500,1500],[1800,1800]],label='INPUT only')))
    monkeypatch.setattr(GeoWorldBackendClient,'submit_job',lambda *_:pytest.fail('Prepare-only must not execute'))
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'apps/studio_streamlit.py'))
    app.session_state['access_token']='test-only-token'
    app.session_state['user_email']='test@example.test'
    app.run(timeout=20)
    next(t for t in app.text_area if t.label=='What would you like GeoWorld to do?').set_value('Prepare bounded Marmousi 1 FWI').run(timeout=20)
    next(b for b in app.button if b.label=='Interpret request').click().run(timeout=20)
    assert not app.exception
    assert next(b for b in app.button if b.label=='Run bounded FWI').disabled
    assert any('Expected time' in text.value for text in app.markdown)
    assert len(app.get('plotly_chart'))==1


def test_fwi_actual_model_attribution():
    from geoworld_open.client.models import JobResult
    from geoworld_open.studio_llm import result_model_lines
    result=JobResult(intent='bounded_fwi',reason='test',answer='test')
    lines=result_model_lines(result,trace={'capability_uses':[{'capability_name':'bounded_fwi','diagnostics':{
        'llm':{'provider':'bedrock','model':'us.amazon.nova-2-lite-v1:0','success':True}}}]})
    assert 'Amazon Bedrock' in lines[0] and 'FWI' in lines[1]
