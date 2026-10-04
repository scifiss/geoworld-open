from pathlib import Path

import pytest

from geoworld_open.client.horizon import HorizonTrackRequest


def test_seed_required_tracking_errors_and_section_switch_clear_result():
    pytest.importorskip("streamlit")
    pytest.importorskip("plotly")
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(Path(__file__).parent / "fixtures/horizon_explorer_app.py")).run(timeout=20)
    assert not app.exception
    assert app.button(key="horizon_track").disabled
    assert any("Synthetic benchmark" in item.value for item in app.markdown)
    assert not app.text_input
    prefix = "horizon_" + "c" * 24 + "_inline_1212"
    assert app.number_input(key=prefix + "_trace").value is None
    app.number_input(key=prefix + "_trace").set_value(16)
    app.number_input(key=prefix + "_time").set_value(.408).run(timeout=20)
    app.button(key="horizon_track").click().run(timeout=20)
    assert not app.exception
    assert app.session_state["horizon_result"].metrics["failure_rate"] == .5
    assert any("Horizon result" in item.value and "partial" in item.value for item in app.markdown)
    assert len(app.get("plotly_chart")) == 1
    assert len(app.get("download_button")) == 1
    app.number_input(key=prefix + "_time").set_value(.32).run(timeout=20)
    assert "horizon_result" not in app.session_state
    app.button(key="horizon_track").click().run(timeout=20)
    assert len(app.error) == 1
    assert "local waveform extremum" in app.error[0].value
    app.selectbox(key="horizon_direction").set_value("crossline").run(timeout=20)
    assert not app.exception
    assert "horizon_result" not in app.session_state
    assert len(app.get("plotly_chart")) == 1
    assert app.button(key="horizon_track").disabled


def test_horizon_plot_does_not_mutate_and_has_truth_picks_and_error():
    pytest.importorskip("streamlit")
    pytest.importorskip("plotly")
    from tests.fixtures.horizon_explorer_app import API
    from geoworld_open.client.seismic import SeismicViewRequest
    from geoworld_open.studio_seismic import _horizon_figure

    api = API()
    request = HorizonTrackRequest(
        dataset_id="c" * 24, view_kind="inline", section_number=1212, seed_trace=16,
        seed_time_s=.408, window_start_s=.3, window_stop_s=.5,
    )
    view = api.get_seismic_view(SeismicViewRequest(dataset_id="c" * 24, view_kind="inline", inline=1212))
    result = api.track_synthetic_horizon(request)
    original = view.model_dump_json()
    original_result = result.model_dump_json()
    figure = _horizon_figure(view, result, 99)
    assert view.model_dump_json() == original
    assert result.model_dump_json() == original_result
    assert {trace.name for trace in figure.data} >= {"Synthetic truth", "Seeded pick", "Error (ms)", "No pick"}
    pick_trace = next(trace for trace in figure.data if trace.name == "Seeded pick")
    error_trace = next(trace for trace in figure.data if trace.name == "Error (ms)")
    assert pick_trace.connectgaps is False
    assert error_trace.connectgaps is False
    assert any(value is None for value in pick_trace.y)
