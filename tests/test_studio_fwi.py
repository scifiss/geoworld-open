from pathlib import Path
import pytest
from test_execution_contracts import example_plan


@pytest.mark.parametrize('variant',['bounded','simple250','progressive','progressive_final'])
def test_fwi_preflight_preview_and_prepare_only_never_run(monkeypatch,variant):
    pytest.importorskip('streamlit')
    from streamlit.testing.v1 import AppTest
    from geoworld_open.client import GeoWorldBackendClient
    from geoworld_open.client.fwi import FWIPreview,FWISelection,FWI_REFERENCE_ID,FWI_SIMPLE_250_ID,FWI_PROGRESSIVE_ID
    reference={'bounded':FWI_REFERENCE_ID,'simple250':FWI_SIMPLE_250_ID,'progressive':FWI_PROGRESSIVE_ID,'progressive_final':FWI_PROGRESSIVE_ID}[variant]
    snapshots={'bounded':[10],'simple250':[50,100,150,200,250],'progressive':[2,4,6,8,10],'progressive_final':[10]}[variant]
    from geoworld_open.client.studio_request import StudioDecision,StudioIntent
    monkeypatch.setenv('GEOWORLD_BACKEND_URL','http://127.0.0.1:8100')
    monkeypatch.setenv('GEOWORLD_STUDIO_LOCAL_RTM','1')
    monkeypatch.setattr(GeoWorldBackendClient,'get_llm_health',lambda _: {'reachable':True})
    monkeypatch.setattr(GeoWorldBackendClient,'interpret_studio',lambda *_:StudioDecision(
        interpretation=StudioIntent(operation='fwi',dataset='marmousi1'),route='bounded_fwi',message='Bounded FWI'))
    monkeypatch.setattr(GeoWorldBackendClient,'preview_fwi',lambda *_a,**_k:FWIPreview(
        selection=FWISelection(reference_id=reference,action='prepare'),preparation_id='a'*32,runnable=False,
        settings={},execution_plan=example_plan(),snapshot_schedule=snapshots,
        model_preview=dict(x_m=[0,4],z_m=[0,4],initial_velocity=[[1500,1500],[1800,1800]],label='INPUT only')))
    monkeypatch.setattr(GeoWorldBackendClient,'submit_job',lambda *_:pytest.fail('Prepare-only must not execute'))
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'apps/studio_streamlit.py'))
    app.session_state['access_token']='test-only-token'
    app.session_state['user_email']='test@example.test'
    app.run(timeout=20)
    next(t for t in app.text_area if t.label=='What would you like GeoWorld to do?').set_value('Prepare bounded Marmousi 1 FWI').run(timeout=20)
    next(b for b in app.button if b.label=='Interpret request').click().run(timeout=20)
    assert not app.exception
    assert next(b for b in app.button if b.label==('Run bounded FWI' if variant=='bounded' else 'Run FWI')).disabled
    assert any('Expected time' in text.value for text in app.markdown)
    assert len(app.get('plotly_chart'))==1
    assert any('Display snapshots: '+', '.join(map(str,snapshots)) in c.value for c in app.caption)
    if variant.startswith('progressive'):
        assert any('cycle skipping' in c.value for c in app.caption)
        snapshot_caption=next(c.value for c in app.caption if c.value.startswith('Display snapshots:'))
        assert ('one per frequency stage' in snapshot_caption)==(variant=='progressive')


def test_fwi_actual_model_attribution():
    from geoworld_open.client.models import JobResult
    from geoworld_open.studio_llm import result_model_lines
    result=JobResult(intent='bounded_fwi',reason='test',answer='test')
    lines=result_model_lines(result,trace={'capability_uses':[{'capability_name':'bounded_fwi','diagnostics':{
        'llm':{'provider':'bedrock','model':'us.amazon.nova-2-lite-v1:0','success':True}}}]})
    assert 'Amazon Bedrock' in lines[0] and 'FWI' in lines[1]
