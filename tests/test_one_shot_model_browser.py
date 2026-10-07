"""Opt-in browser acceptance of one-message modeling and result presentation."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

import pytest


pytestmark = pytest.mark.skipif(os.getenv("GEOWORLD_BROWSER_TESTS") != "1",
                                reason="opt-in Chromium one-shot model test")


def test_one_message_shows_completed_image_without_duplicate_job(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOWORLD_BACKEND_URL", "http://127.0.0.1:8100")
    from playwright.sync_api import sync_playwright

    root = Path(__file__).parents[1]
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with (tmp_path / "studio.log").open("w") as log:
        proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run",
            str(root / "tests/fixtures/one_shot_model_app.py"),
            "--server.address", "127.0.0.1", "--server.port", str(port),
            "--server.headless", "true", "--browser.gatherUsageStats", "false"],
            stdout=log, stderr=log)
        try:
            for _ in range(80):
                try:
                    if urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=.3).status == 200:
                        break
                except OSError:
                    time.sleep(.1)
            with sync_playwright() as browser_runtime:
                browser = browser_runtime.chromium.launch()
                page = browser.new_page(viewport={"width": 1440, "height": 1100})
                page.goto(f"http://127.0.0.1:{port}")
                composer = page.get_by_label("Message GeoWorld", exact=True)
                composer.fill("build shale sand carbonate, co2 in sand carbonate very porous")
                page.get_by_role("button", name="Send", exact=True).click()
                page.get_by_text("Fixture submissions: 1", exact=True).wait_for()
                page.get_by_role("button", name="Download publication figure (PNG)").wait_for()
                page.get_by_text("Edit model", exact=True).wait_for()
                assert page.get_by_label("Chat message from assistant").get_by_text(
                    "Generated 3-layer synthetic model.", exact=False).count() == 1
                assert page.get_by_test_id("stImage").count() >= 1
                page.get_by_text("Edit model", exact=True).click()
                assert page.get_by_text("Fixture submissions: 1", exact=True).count() == 1
                assert page.get_by_test_id("stException").count() == 0
                browser.close()
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
