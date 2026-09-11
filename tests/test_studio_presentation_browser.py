"""Opt-in offline browser check; no live account or backend is used.

Install playwright and its Chromium browser, then set GEOWORLD_BROWSER_TESTS=1.
"""
from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

import pytest
from PIL import Image

from geoworld_open.client.models import JobResult
from geoworld_open.studio_presentation import ReportFigure, build_clean_report


pytestmark = pytest.mark.skipif(
    os.getenv("GEOWORLD_BROWSER_TESTS") != "1", reason="opt-in Chromium layout test",
)
ROOT = Path(__file__).resolve().parents[1]


def test_html_export_download_and_unified_view_preserve_result(studio_server, tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(studio_server)
        page.get_by_text("Offline display test — no model has been run.", exact=True).wait_for()
        page.get_by_text("Save & export", exact=True).click()
        page.get_by_role("button", name="Prepare HTML report", exact=True).click()
        download = page.get_by_role("button", name="Download HTML report", exact=True)
        download.wait_for()
        count = page.locator("#fixture-run-count").inner_text()
        with page.expect_download() as event:
            download.click()
        path = tmp_path / "browser-report.html"
        event.value.save_as(path)
        assert "Offline display test" in path.read_text()
        assert "Build shale, high-porosity sand" in path.read_text()
        assert "private-account@example.test" not in path.read_text()
        assert page.locator("#fixture-run-count").inner_text() == count
        page.get_by_text("Advanced: manual tools / debugging", exact=True).click()
        # Streamlit's styled checkbox wraps a visually hidden input. Click the
        # visible associated label, as a user does, rather than its input box.
        page.get_by_text("Use manual tools", exact=True).click()
        page.get_by_role("button", name="Interpret request", exact=True).wait_for()
        # Streamlit briefly retains stale elements until the rerun completes.
        page.get_by_role("button", name="Determine route", exact=True).wait_for(state="hidden")
        assert page.get_by_text("Offline display test — no model has been run.", exact=True).is_visible()
        assert not page.get_by_text("Workspace", exact=True).is_visible()
        page.screenshot(path=str(tmp_path / "unified-studio-export.png"), full_page=True)
        browser.close()


def test_clean_report_browser_layout_zoom_capture_and_print(tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    html = build_clean_report(
        prompt="Build a faulted reservoir with shale and sand. Show the model and explain its assumptions.",
        result=JobResult(
            intent="build_model", reason="manual build",
            answer="A synthetic faulted-reservoir demonstration.\nThe figure below is an existing public reference artifact, not a newly executed model.",
            assumptions=["Synthetic reference example; not a calibrated field interpretation."],
        ),
        figures=[ReportFigure("flagship_world_demo.png", (ROOT / "docs/assets/flagship_world_demo.png").read_bytes())],
    )
    report = tmp_path / "report.html"
    report.write_text(html, encoding="utf-8")
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(timeout=15000)
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=2)
        page = context.new_page()
        errors, external = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        page.on("request", lambda request: external.append(request.url) if request.url.startswith(("http:", "https:")) else None)
        page.goto(report.as_uri())
        page.wait_for_function("Array.from(document.images).every(img => img.complete && img.naturalWidth > 0)")
        natural = page.locator("figure img").evaluate("img => img.naturalWidth / img.naturalHeight")
        for width in (1440, 375):
            page.set_viewport_size({"width": width, "height": 1000})
            for scale in (80, 100, 150):
                page.locator("#scale").evaluate("(node, value) => { node.value = value; }", str(scale))
                page.locator("#scale").dispatch_event("input")
                assert page.locator("#scale-value").inner_text() == f"{scale}%"
                metrics = page.evaluate("""() => {
                    const report = document.querySelector('#report');
                    const img = document.querySelector('figure img').getBoundingClientRect();
                    return {width: document.documentElement.scrollWidth, viewport: innerWidth,
                      text: parseFloat(getComputedStyle(report).fontSize) * Number(getComputedStyle(report).zoom),
                      ratio: img.width / img.height};
                }""")
                assert metrics["width"] <= metrics["viewport"], metrics
                assert metrics["text"] >= 15.99, metrics
                assert metrics["ratio"] == pytest.approx(natural, rel=.01)
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.get_by_role("button", name="Reset sizes").click()
        original_width = page.locator("figure img").bounding_box()["width"]
        page.locator("#figure").evaluate("node => { node.value = '640'; }")
        page.locator("#figure").dispatch_event("input")
        assert page.locator("figure img").bounding_box()["width"] < original_width
        page.locator("#text").evaluate("node => { node.value = '22'; }")
        page.locator("#text").dispatch_event("input")
        assert page.locator("#report").evaluate("node => getComputedStyle(node).fontSize") == "22px"
        page.get_by_role("button", name="Reset sizes").click()
        page.get_by_role("button", name="Capture view").click()
        assert not page.locator(".report-controls").is_visible()
        page.screenshot(path=str(tmp_path / "report-desktop.png"), full_page=True)
        with Image.open(tmp_path / "report-desktop.png") as screenshot:
            assert screenshot.width == 2880  # 1440 CSS pixels at 2x pixel density.
            assert screenshot.height > 2000  # The report includes below-the-fold content.
        page.keyboard.press("Escape")
        assert page.locator(".report-controls").is_visible()
        page.get_by_role("button", name="Capture view").click()
        page.locator("h1").click()
        assert page.locator(".report-controls").is_visible()
        page.emulate_media(media="print")
        assert not page.locator(".report-controls").is_visible()
        page.pdf(path=str(tmp_path / "report.pdf"), print_background=True)
        page.emulate_media(media="screen")
        page.set_viewport_size({"width": 375, "height": 812})
        page.get_by_role("button", name="Capture view").click()
        page.screenshot(path=str(tmp_path / "report-mobile.png"), full_page=True)
        assert not errors, errors
        assert not external, external
        browser.close()
    print(f"Report preview: {tmp_path / 'report-desktop.png'}")


@pytest.fixture
def studio_server(tmp_path):
    pytest.importorskip("streamlit")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    address = f"http://127.0.0.1:{port}"
    environment = os.environ | {"GEOWORLD_BACKEND_URL": "https://example.test", "PYTHONPATH": str(ROOT / "src")}
    with (tmp_path / "streamlit.log").open("w") as log:
        server = subprocess.Popen([
            sys.executable, "-m", "streamlit", "run", str(ROOT / "tests/fixtures/studio_capture_app.py"),
            "--server.address", "127.0.0.1", "--server.port", str(port),
            "--server.headless", "true", "--browser.gatherUsageStats", "false",
        ], cwd=ROOT, env=environment, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline:
                try:
                    with urlopen(address + "/_stcore/health", timeout=1) as response:
                        if response.status == 200:
                            break
                except (URLError, TimeoutError):
                    time.sleep(.2)
            else:
                pytest.fail("Offline Streamlit fixture did not start")
            yield address
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)


def test_normal_studio_layout_and_native_pdf_without_capture_mode(studio_server, tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(timeout=15000)
        try:
            page = browser.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=2)
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            page.goto(studio_server)
            page.get_by_role("tab", name="Model & Figures", exact=True).click()
            prompt = page.get_by_role("textbox", name="What would you like GeoWorld to do?")
            # Streamlit can mount a textbox before its session value hydrates.
            playwright.expect(prompt).to_have_value(
                "Build shale, high-porosity sand, and shale. Add one dipping fault.\n"
                "Generate Vp, Vs, density, impedance, reflectivity, synthetic seismic. List assumptions."
            )
            original_prompt = prompt.input_value()
            workflow = page.locator(".st-key-studio_workflow")
            results = page.locator(".st-key-studio_results")
            layout = page.get_by_role("combobox", name="Page layout", exact=True)

            def columns(expected):
                page.wait_for_function("""two => {
                    const left = document.querySelector('.st-key-studio_workflow').getBoundingClientRect();
                    const right = document.querySelector('.st-key-studio_results').getBoundingClientRect();
                    return two ? Math.abs(left.y - right.y) < 1 && left.right < right.x : left.bottom <= right.y;
                }""", arg=expected)

            def choose(value):
                layout.click()
                page.get_by_role("option", name=value, exact=True).click()

            columns(True)  # Auto responds to main content width; no screenshot mode needed.
            assert page.get_by_test_id("stSidebar").is_visible()
            playwright.expect(page.get_by_test_id("stSidebar").get_by_text(
                "Configured AI: Amazon Bedrock · us.amazon.nova-2-lite-v1:0", exact=True,
            )).to_be_visible()
            playwright.expect(results.get_by_text(
                "Model preparation: OpenAI · gpt-4.1-mini (backup used)", exact=True,
            )).to_be_visible()
            assert not page.get_by_test_id("stMain").get_by_role("button", name="Save page as PDF").count()
            assert not page.get_by_text("Screenshot / clean report", exact=True).count()
            assert not page.locator("#gw-studio-capture-toolbar").count()
            assert prompt.evaluate("node => getComputedStyle(node).fontSize") == "18px"
            page.get_by_role("button", name="Run model", exact=True).is_visible()
            main_box = page.get_by_test_id("stMain").bounding_box()
            right = results.bounding_box()
            # No fixed 1240/1600px cap or unused right column.
            assert main_box["x"] + main_box["width"] - (right["x"] + right["width"]) <= 24
            assert workflow.bounding_box()["x"] - main_box["x"] <= 24
            image = page.get_by_role("tabpanel", name="Model & Figures", exact=True).locator("img").first
            playwright.expect(image).to_be_visible()
            assert image.bounding_box()["width"] >= right["width"] - 5

            choose("One column")
            columns(False)
            assert prompt.input_value() == original_prompt
            choose("Two columns")
            columns(True)
            choose("Auto")
            columns(True)
            # Resizing is CSS-only, with no server rerun or scientific submission.
            runs = page.locator("#fixture-run-count").inner_text()
            page.set_viewport_size({"width": 1200, "height": 900})
            columns(False)
            assert page.locator("#fixture-run-count").inner_text() == runs
            choose("Two columns")  # Deliberate override where both columns still fit.
            columns(True)
            choose("Auto")
            columns(False)
            page.set_viewport_size({"width": 1900, "height": 1000})
            columns(True)
            main_box, right = page.get_by_test_id("stMain").bounding_box(), results.bounding_box()
            assert main_box["x"] + main_box["width"] - (right["x"] + right["width"]) <= 24

            # Export is a sidebar action; native print CSS changes nothing persistently.
            page.get_by_text("Save & export", exact=True).click()
            print_button = page.get_by_role("button", name="Save page as PDF", exact=True)
            runs = page.locator("#fixture-run-count").inner_text()
            page.evaluate("() => { window.fixturePrintCalls = 0; window.print = () => { window.fixturePrintCalls += 1; }; }")
            print_button.click()
            print_button.click()
            assert page.evaluate("window.fixturePrintCalls") == 2
            assert print_button.is_visible()
            assert page.get_by_test_id("stSidebar").is_visible()
            assert page.locator("#fixture-run-count").inner_text() == runs
            assert prompt.input_value() == original_prompt

            page.emulate_media(media="print")
            assert not print_button.is_visible()
            assert not page.get_by_test_id("stSidebar").is_visible()
            assert not page.get_by_test_id("stHeader").is_visible()
            assert "private-account@example.test" not in page.locator("body").inner_text()
            assert not page.get_by_role("tabpanel", name="Advanced", exact=True, include_hidden=True).is_visible()
            assert prompt.input_value() == original_prompt
            pdf = page.pdf(path=str(tmp_path / "studio-page.pdf"), print_background=True, prefer_css_page_size=True)
            assert pdf.startswith(b"%PDF-")
            reader = pytest.importorskip("pypdf").PdfReader(BytesIO(pdf))
            printed = "\n".join(item.extract_text() for item in reader.pages)
            assert "summary_0.png" in printed
            assert "private-account@example.test" not in printed
            assert "Save page as PDF" not in printed
            assert reader.pages[0].mediabox.width > reader.pages[0].mediabox.height
            page.emulate_media(media="screen")
            assert print_button.is_visible()
            assert page.get_by_test_id("stSidebar").is_visible()
            assert page.locator("#fixture-run-count").inner_text() == runs
            assert page.get_by_role("tab", name="Model & Figures", exact=True).get_attribute("aria-selected") == "true"
            page.get_by_text("Save & export", exact=True).click()
            playwright.expect(print_button).not_to_be_visible()
            page.screenshot(path=str(tmp_path / "studio-responsive-desktop.png"))

            # Explicit two columns still stack on small screens; no horizontal clipping.
            choose("Two columns")
            for width in (760, 375):
                page.set_viewport_size({"width": width, "height": 900})
                columns(False)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                main = page.get_by_test_id("stMain")
                assert main.evaluate("node => node.scrollWidth <= node.clientWidth")
            page.screenshot(path=str(tmp_path / "studio-responsive-mobile.png"))
            assert not errors, errors
        finally:
            browser.close()
    print(f"Responsive Studio preview: {tmp_path / 'studio-responsive-desktop.png'}")


def test_long_studio_results_remain_complete_in_layout_and_pdf(studio_server, tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(timeout=15000)
        try:
            page = browser.new_page(viewport={"width": 1600, "height": 1000})
            page.goto(studio_server + "?capture_figures=3")
            page.get_by_role("tab", name="Model & Figures", exact=True).click()
            figures = page.get_by_role("tabpanel", name="Model & Figures", exact=True).locator("img")
            playwright.expect(figures).to_have_count(3)
            page.wait_for_function("Array.from(document.images).every(img => img.complete && img.naturalWidth > 0)")
            page.get_by_text("Tables & scientific details", exact=True).click()
            page.get_by_role("heading", name="Scientific summary", exact=True).wait_for(state="visible")
            # Wait for the entire app run, not just the first streamed figures.
            page.locator("#gw-studio-print").wait_for(state="attached")
            for figure in figures.all():
                ratio = figure.evaluate("img => img.naturalWidth / img.naturalHeight")
                box = figure.bounding_box()
                assert box["width"] / box["height"] == pytest.approx(ratio, rel=.01)
            metrics = page.evaluate("""() => {
                const main = document.querySelector('[data-testid="stMain"]');
                const end = document.querySelector('.st-key-studio_workspace_layout').getBoundingClientRect();
                return {height: main.scrollHeight, contentBottom: end.bottom - main.getBoundingClientRect().top + main.scrollTop};
            }""")
            assert 0 <= metrics["height"] - metrics["contentBottom"] <= 24, metrics
            page.emulate_media(media="print")
            assert figures.last.evaluate("node => node.getBoundingClientRect().bottom + scrollY") <= page.evaluate("document.documentElement.scrollHeight")
            pdf = page.pdf(path=str(tmp_path / "studio-long-page.pdf"), print_background=True, prefer_css_page_size=True)
            assert pdf.startswith(b"%PDF-")
            reader = pytest.importorskip("pypdf").PdfReader(BytesIO(pdf))
            printed = "\n".join(item.extract_text() for item in reader.pages)
            assert all(f"summary_{index}.png" in printed for index in range(3))
            assert "Scientific summary" in printed
            assert "private-account@example.test" not in printed
            page.emulate_media(media="screen")
            assert page.get_by_text("Tables & scientific details", exact=True).is_visible()
        finally:
            browser.close()
