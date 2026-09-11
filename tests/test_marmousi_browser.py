"""Opt-in real Chromium drag selection, not just a mocked chart callback."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
import pytest

pytestmark = pytest.mark.skipif(os.getenv("GEOWORLD_BROWSER_TESTS") != "1", reason="opt-in Chromium crop test")


def test_rectangle_updates_crop_controls(tmp_path):
    from playwright.sync_api import sync_playwright
    root = Path(__file__).parents[1]
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with (tmp_path / "studio.log").open("w") as log:
        proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(root / "tests/fixtures/marmousi_explorer_app.py"),
            "--server.address", "127.0.0.1", "--server.port", str(port), "--server.headless", "true", "--browser.gatherUsageStats", "false"], stdout=log, stderr=log)
        try:
            for _ in range(80):
                try:
                    if urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=.3).status == 200:
                        break
                except OSError:
                    time.sleep(.1)
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={"width": 1280, "height": 1000})
                page.goto(f"http://127.0.0.1:{port}")
                page.get_by_role("button", name="Load selected dataset (manual)").click()
                plot = page.locator(".js-plotly-plot").first
                plot.wait_for()
                page.wait_for_function("document.querySelector('.js-plotly-plot')._fullLayout !== undefined")
                coords = plot.evaluate("""node => {
                    const r=node.getBoundingClientRect(), x=node._fullLayout.xaxis, y=node._fullLayout.yaxis;
                    return {x1:r.x+x._offset+x.l2p(20), y1:r.y+y._offset+y.l2p(10),
                            x2:r.x+x._offset+x.l2p(80), y2:r.y+y._offset+y.l2p(40)};
                }""")
                page.mouse.move(coords["x1"], coords["y1"])
                page.mouse.down()
                page.mouse.move(coords["x2"], coords["y2"], steps=20)
                page.mouse.up()
                page.get_by_role("button", name="Use selected rectangle").click(timeout=15000)
                xstart = page.get_by_label("X start (m)", exact=True)
                page.wait_for_function("Array.from(document.querySelectorAll('input')).some(n => Number(n.value)>18 && Number(n.value)<22)")
                assert float(xstart.input_value()) == pytest.approx(20, abs=1)
                assert float(page.get_by_label("Z stop (m)", exact=True).input_value()) == pytest.approx(40, abs=1)
                assert page.locator('[data-testid="stException"]').count() == 0
                page.screenshot(path=str(tmp_path / "marmousi-crop.png"), full_page=True)
                browser.close()
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
