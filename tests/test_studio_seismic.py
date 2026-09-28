from pathlib import Path

import pytest


def test_seismic_explorer_renders_and_switching_dataset_clears_stale_view():
    pytest.importorskip("streamlit")
    pytest.importorskip("plotly")
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(
        str(Path(__file__).parents[1] / "tests/fixtures/seismic_explorer_app.py")
    ).run(timeout=20)
    assert not app.exception
    assert any("2D RSF" in item.value for item in app.markdown)
    next(button for button in app.button if button.label == "Open dataset").click().run(timeout=20)
    assert not app.exception
    assert any("Current view" in item.value and "Line A" in item.value for item in app.markdown)
    assert len(app.get("plotly_chart")) == 1

    app.selectbox(key="seismic_dataset_id").set_value("b" * 24).run(timeout=20)
    assert not app.exception
    assert len(app.get("plotly_chart")) == 0
    assert "seismic_conversation_id" not in app.session_state

    next(button for button in app.button if button.label == "Open dataset").click().run(timeout=20)
    assert any("Current view" in item.value and "Line B" in item.value for item in app.markdown)
    assert len(app.get("plotly_chart")) == 1


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
