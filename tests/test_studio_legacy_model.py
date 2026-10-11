import json
from types import SimpleNamespace
import pytest
pytest.importorskip('streamlit')
from streamlit.testing.v1 import AppTest
from geoworld_open.client.models import JobResult,ArtifactInfo
from geoworld_open.studio_legacy_model import field_catalog


def test_catalog_excludes_aggregate_and_scale_variants():
    names=['run/summary.png','run/avo_summary.png','run/scientific_vp.png','run/scientific_vp_separate.png','run/scientific_facies.png']
    catalog=field_catalog([ArtifactInfo(name=n,kind='image',media_type='image/png') for n in names])
    assert list(catalog)==['vp','facies']


def test_ordinary_workspace_defaults_and_order_without_duplicate_figures(monkeypatch):
    from geoworld_open.client import GeoWorldClientError
    from pathlib import Path
    png=(Path(__file__).resolve().parents[1]/'docs/assets/flagship_world_demo.png').read_bytes()
    fetched=[]
    class Client:
        def get_artifact(self,job,name):
            fetched.append(name)
            if name.endswith('.json'):
                return json.dumps({'parameters':[{'Parameter':'Shale porosity','Value':'0.08','Source':'Assumed'}], 'velocity_shared_limits_m_s':[1000,5000]}).encode()
            return png
        def get_export(self,*args):
            raise GeoWorldClientError('Export unavailable in this test')
    names=['scientific_facies.png','scientific_porosity.png','scientific_vp.png','scientific_vs.png','summary.png','avo_summary.png','legacy-presentation.json']
    result=JobResult(intent='build_model',reason='',answer='done',geospec={},artifacts=[ArtifactInfo(name='run/'+n,kind='json' if n.endswith('.json') else 'image',media_type='application/json' if n.endswith('.json') else 'image/png') for n in names])
    def page(api,result):
        from geoworld_open.studio_legacy_model import render_legacy_model
        from types import SimpleNamespace
        render_legacy_model(api,'j',result,SimpleNamespace(fit_figures=True,figure_px=700))
    app=AppTest.from_function(page,args=(Client(),result)).run(timeout=15)
    assert not app.exception
    assert [t.label for t in app.tabs]==['Scientific Figures','Evidence / provenance','Advanced / downloads']
    assert fetched.count('run/scientific_facies.png')==1 and fetched.count('run/scientific_porosity.png')==1
    assert 'run/summary.png' not in fetched and 'run/avo_summary.png' not in fetched
    fetched.clear()
    app.multiselect[0].set_value(['vs','vp']).run()
    assert fetched.index('run/scientific_vs.png')<fetched.index('run/scientific_vp.png')


def test_build_context_keeps_original_action_through_a_patch():
    from geoworld_open.client.semantic_action import NewBuild,RequestedLayer
    def page(action):
        import streamlit as st
        from geoworld_open.studio_context import commit_build,task_context
        commit_build({'geospec':{'geology':{'layers':[{'lithology':'sand','porosity':.2}]}},'valid':True},['original'],source_action=action)
        commit_build({'geospec':{'geology':{'layers':[{'lithology':'sand','porosity':.25}]}},'valid':True},['original','change sand'])
        value=task_context()
        assert value.build.source_prompt=='original'
        assert value.build.source_action.layers[0].porosity==.2
        assert value.build.geospec['geology']['layers'][0]['porosity']==.25
    app=AppTest.from_function(page,args=(NewBuild(layers=[RequestedLayer(lithology='sand',porosity=.2)]),)).run()
    assert not app.exception
