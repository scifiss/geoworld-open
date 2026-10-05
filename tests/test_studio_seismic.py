from pathlib import Path
import inspect

import pytest


def test_seismic_explorer_renders_and_switching_dataset_clears_stale_view():
    pytest.importorskip("streamlit")
    pytest.importorskip("plotly")
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(
        str(Path(__file__).parents[1] / "tests/fixtures/seismic_explorer_app.py")
    ).run(timeout=20)
    assert not app.exception
    assert len(app.get("file_uploader")) == 1
    assert not any(button.label == "Track selected synthetic horizon" for button in app.button)
    assert any(button.label == "Upload and attach" for button in app.button)
    assert any("2D RSF" in item.value for item in app.caption)
    assert not app.exception
    assert any("Current view" in item.value and "Line A" in item.value for item in app.markdown)
    assert len(app.get("plotly_chart")) == 1
    assert any("GeoWorld Assistant" in item.value for item in app.markdown)
    assert any(button.label == "Send" for button in app.button)

    app.selectbox(key="seismic_context_choice").set_value("b" * 24).run(timeout=20)
    app.button(key="seismic_switch").click().run(timeout=20)
    assert not app.exception
    assert len(app.get("plotly_chart")) == 1
    assert "seismic_conversation_id" not in app.session_state
    assert any("Current view" in item.value and "Line B" in item.value for item in app.markdown)


def test_deterministic_chat_renders_separated_history_and_keeps_view_on_turn():
    pytest.importorskip("streamlit")
    pytest.importorskip("plotly")
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(
        str(Path(__file__).parents[1] / "tests/fixtures/seismic_explorer_app.py")
    ).run(timeout=20)
    app.text_area(key="assistant_prompt").set_value("Show the amplitude statistics").run(timeout=20)
    next(button for button in app.button if button.label == "Send").click().run(timeout=20)
    assert not app.exception
    assert len(app.get("chat_message")) == 2
    assert any("Show the amplitude statistics" in item.value for item in app.markdown)
    assert any("Applied deterministic" in item.value for item in app.markdown)
    assert len(app.get("plotly_chart")) == 1
    assert app.session_state["seismic_conversation_id"]


def test_workspace_css_has_responsive_stack_and_sticky_chat_composer():
    from geoworld_open import studio_assistant

    source = inspect.getsource(studio_assistant.render_assistant_studio)
    assert "@media (max-width: 900px)" in source
    assert "min-width: 100%" in source
    assert "position: sticky" in source


def test_display_clip_is_explicitly_non_destructive():
    from tests.fixtures.seismic_explorer_app import DATASETS, view
    from geoworld_open.client.seismic import SeismicViewRequest
    from geoworld_open.studio_seismic import _figure

    data = view(SeismicViewRequest(dataset_id=DATASETS[0].dataset_id))
    original = [row[:] for row in data.values]
    figure = _figure(data, 95.)
    assert data.values == original
    assert figure.data[0].zmin == -figure.data[0].zmax
    assert "do not alter source samples" in data.display_note


def test_studio_passes_uploaded_file_without_materializing_full_content():
    from geoworld_open.studio_assistant import attach_seismic

    source = inspect.getsource(attach_seismic)
    assert "uploaded.getvalue()" not in source
    assert "api.upload_seismic(uploaded.name, uploaded)" in source
