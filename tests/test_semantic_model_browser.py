"""Opt-in browser acceptance of the real single-assistant prepared-model UI."""
import os
import json
from pathlib import Path
import socket,subprocess,sys,time
from urllib.request import urlopen
import pytest
pytestmark=pytest.mark.skipif(os.getenv('GEOWORLD_BROWSER_TESTS')!='1',reason='opt-in Chromium model preview test')

@pytest.mark.parametrize('cpu_rate',[1,4])
def test_prepared_geometry_edit_run_and_responsive_workspace(tmp_path, monkeypatch,cpu_rate):
    monkeypatch.setenv("GEOWORLD_BACKEND_URL", "http://127.0.0.1:8100")
    from playwright.sync_api import sync_playwright
    root=Path(__file__).parents[1]
    artifacts=Path(os.getenv("GEOWORLD_BROWSER_ARTIFACTS_DIR",str(tmp_path)))/f'cpu-{cpu_rate}'
    artifacts.mkdir(parents=True,exist_ok=True)
    def capture(page,name):
        original=page.viewport_size
        height=page.get_by_test_id('stMain').evaluate('(element)=>element.scrollHeight')
        page.set_viewport_size({'width':original['width'],'height':max(original['height'],height+100)})
        page.get_by_test_id('stMain').evaluate('(element)=>{element.scrollTop=0}')
        page.screenshot(path=str(artifacts/(name+'.png')),full_page=True)
        page.set_viewport_size(original)
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
                page.context.new_cdp_session(page).send('Emulation.setCPUThrottlingRate',{'rate':cpu_rate})
                page.goto(f'http://127.0.0.1:{port}')
                box=page.get_by_label('Message GeoWorld',exact=True)
                box.fill('Build a formation with shale, sand, carbonate, and shale layers. Sand has porosity of 0.2, and carbonate 0.3.')
                page.get_by_role('button',name='Send',exact=True).click()
                page.locator('.js-plotly-plot').wait_for()
                assert box.count()==1
                page.get_by_text('Fixture submissions: 0',exact=True).wait_for()
                page.wait_for_function("()=>Number(document.querySelector('[data-testid=stForm] [data-testid=glide-cell-3-2]')?.textContent)===30")
                capture(page,'01-request-preview')
                box.fill('change carbonate porosity to 0.25')
                page.get_by_role('button',name='Send',exact=True).click()
                page.wait_for_function("document.querySelector('textarea').value === ''")
                # The composer clears before preparation finishes; the old plot
                # may still be visible. Wait for the new editor's actual value.
                page.wait_for_function("()=>Number(document.querySelector('[data-testid=stForm] [data-testid=glide-cell-3-2]')?.textContent)===25")
                capture(page,'02-carbonate-followup-preview')
                from geoworld_open.workspace_browser import edit_porosity, select_workspace, select_fields, settled
                try:
                    edit_porosity(page,row=1,percent=22.)
                except Exception:
                    page.screenshot(path=str(artifacts/'editor-failure.png'),full_page=True)
                    (artifacts/'editor-failure.html').write_text(page.content())
                    (artifacts/'editor-failure.json').write_text(json.dumps(page.evaluate("""() => ({
                        scriptState:document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state'),
                        focus:document.activeElement?.outerHTML,
                        selectedCells:Array.from(document.querySelectorAll('[role=gridcell][aria-selected=true]')).map(e=>e.outerHTML),
                        inputs:Array.from(document.querySelectorAll('input')).map(e=>e.outerHTML)
                    })"""),indent=2))
                    raise
                page.get_by_text('Fixture submissions: 0',exact=True).wait_for()
                (artifacts/'edited-grid-state.json').write_text(json.dumps(page.get_by_test_id('stForm').evaluate("""form =>
                    Array.from(form.querySelectorAll('[role=gridcell]')).map(cell=>({
                        cell:cell.dataset.testid,value:cell.textContent,readOnly:cell.getAttribute('aria-readonly')
                    }))"""),indent=2))
                page.get_by_test_id('stSidebar').hover()
                page.get_by_test_id('stSidebarCollapseButton').get_by_role('button').click()
                page.wait_for_function("document.querySelector('[data-testid=stSidebar]').getBoundingClientRect().right <= 1")
                capture(page,'model-preview-wide')
                page.set_viewport_size({'width':430,'height':2600})
                page.wait_for_function("""() => { const chat = document.querySelector('.st-key-assistant_panel'); const plot = document.querySelector('.js-plotly-plot'); return chat && plot && chat.getBoundingClientRect().top > plot.getBoundingClientRect().top; }""")
                capture(page,'model-preview-narrow')
                page.set_viewport_size({'width':1440,'height':1100})
                page.get_by_role('button',name='Run simulation',exact=True).click()
                page.get_by_text('Fixture submissions: 1',exact=True).wait_for()
                page.get_by_text('Executed carbonate porosity: 0.25',exact=True).wait_for()
                page.get_by_text('Executed sand porosity: 0.22',exact=True).wait_for()
                select_workspace(page,'Scientific Results')
                capture(page,'03-completed-results')
                select_fields(page,['P-wave velocity (Vp)','S-wave velocity (Vs)'])
                capture(page,'04-selected-scientific-fields')
                select_workspace(page,'Evidence & Data')
                page.get_by_role('button',name='Prepare data download',exact=True).click()
                settled(page)
                with page.expect_download() as download:
                    page.get_by_role('button',name='Download numerical data',exact=True).click()
                download.value.save_as(artifacts/'downloaded-data.csv')
                assert (artifacts/'downloaded-data.csv').read_bytes().startswith(b'.08')
                page.get_by_role('button',name='Prepare numerical data package (ZIP)',exact=True).click()
                page.get_by_role('button',name='Download data package (ZIP)',exact=True).wait_for()
                with page.expect_download() as package:
                    page.get_by_role('button',name='Download data package (ZIP)',exact=True).click()
                package.value.save_as(artifacts/'downloaded-data.zip')
                import zipfile
                with zipfile.ZipFile(artifacts/'downloaded-data.zip') as archive:
                    assert archive.read('porosity.csv')==(artifacts/'downloaded-data.csv').read_bytes()
                capture(page,'05-numerical-downloads')
                page.get_by_text('Fixture submissions: 1',exact=True).wait_for()
                assert page.get_by_role('button',name='Run simulation',exact=True).count()==0
                assert page.locator('[data-testid="stException"]').count()==0
                browser.close()
        finally:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
