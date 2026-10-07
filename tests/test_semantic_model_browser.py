"""Opt-in browser acceptance of the real single-assistant prepared-model UI."""
import os
from pathlib import Path
import socket,subprocess,sys,time
from urllib.request import urlopen
import pytest
pytestmark=pytest.mark.skipif(os.getenv('GEOWORLD_BROWSER_TESTS')!='1',reason='opt-in Chromium model preview test')

def test_prepared_geometry_edit_run_and_responsive_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOWORLD_BACKEND_URL", "http://127.0.0.1:8100")
    from playwright.sync_api import sync_playwright
    root=Path(__file__).parents[1]
    artifacts=Path(os.getenv("GEOWORLD_BROWSER_ARTIFACTS_DIR",str(tmp_path)))
    artifacts.mkdir(parents=True,exist_ok=True)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    with (tmp_path/'studio.log').open('w') as log:
        proc=subprocess.Popen([sys.executable,'-m','streamlit','run',str(root/'tests/fixtures/semantic_model_app.py'),'--server.address','127.0.0.1','--server.port',str(port),'--server.headless','true','--browser.gatherUsageStats','false'],stdout=log,stderr=log)
        try:
            for _ in range(80):
                try:
                    if urlopen(f'http://127.0.0.1:{port}/_stcore/health',timeout=.3).status==200:break
                except OSError:time.sleep(.1)
            with sync_playwright() as p:
                browser=p.chromium.launch()
                page=browser.new_page(viewport={'width':1440,'height':1100})
                page.goto(f'http://127.0.0.1:{port}')
                box=page.get_by_label('Message GeoWorld',exact=True)
                box.fill('Build a formation with shale, sand, carbonate, and shale layers. Sand has porosity of 0.2, and carbonate 0.3.')
                page.get_by_role('button',name='Send',exact=True).click()
                page.locator('.js-plotly-plot').wait_for()
                assert box.count()==1
                page.get_by_text('Fixture submissions: 0',exact=True).wait_for()
                box.fill('change carbonate porosity to 0.25')
                page.get_by_role('button',name='Send',exact=True).click()
                page.wait_for_function("document.querySelector('textarea').value === ''")
                page.locator('.js-plotly-plot').wait_for()
                page.get_by_test_id('stSidebar').hover()
                page.get_by_test_id('stSidebarCollapseButton').get_by_role('button').click()
                page.wait_for_function("document.querySelector('[data-testid=stSidebar]').getBoundingClientRect().right <= 1")
                page.screenshot(path=str(artifacts/'model-preview-wide.png'),full_page=True)
                page.set_viewport_size({'width':430,'height':2600})
                page.wait_for_function("""() => { const chat = document.querySelector('.st-key-assistant_panel'); const plot = document.querySelector('.js-plotly-plot'); return chat && plot && chat.getBoundingClientRect().top > plot.getBoundingClientRect().top; }""")
                page.screenshot(path=str(artifacts/'model-preview-narrow.png'),full_page=True)
                box.fill('run it');page.get_by_role('button',name='Send',exact=True).click()
                page.get_by_text('Fixture submissions: 1',exact=True).wait_for()
                page.get_by_text('Executed carbonate porosity: 0.25',exact=True).wait_for()
                assert page.locator('[data-testid="stException"]').count()==0
                browser.close()
        finally:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
