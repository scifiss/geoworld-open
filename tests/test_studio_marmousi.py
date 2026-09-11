"""Public typed model explorer: fake service, never private imports."""
from pathlib import Path
import pytest
from geoworld_open.client.marmousi import MarmousiPreview, MarmousiSelection, ModelCrop


def make_preview(selection):
    extent = ModelCrop(x_start_m=0., x_stop_m=100., z_start_m=0., z_stop_m=50.)
    return MarmousiPreview(selection=selection, classification="modified_benchmark_model" if selection.crop else "benchmark_model_preview",
        configuration_sha256="a"*64, dataset_extent=extent, resolved_crop=selection.crop or extent,
        shape_xz=[101, 51], spacing_m=1., fields=["vp", "density"], unit="m/s",
        x_m=[0., 50., 100.], z_m=[0., 25., 50.], values_zx=[[1500., 1500., 1500.], [2500., 2600., 2700.], [3500., 3500., 3500.]],
        provenance={"note": "synthetic UI fixture, not a scientific reproduction"}, warnings=["Preview only"])


def test_box_normalizes_depth_axis_and_rejects_empty():
    from geoworld_open.studio_marmousi import box_crop
    extent = make_preview(MarmousiSelection(dataset="marmousi1")).dataset_extent
    p = box_crop({"x": [90., 10.], "y": [40., 5.]}, extent)
    assert p.x_start_m == 10. and p.z_start_m == 5.
    with pytest.raises(ValueError):
        box_crop({"x": [10., 10.], "y": [2., 3.]}, extent)


def test_plot_orientation_and_box_selection_trace():
    pytest.importorskip("plotly")
    from geoworld_open.studio_marmousi import model_figure
    fig = model_figure(make_preview(MarmousiSelection(dataset="marmousi1")), selectable=True)
    assert fig.layout.yaxis.autorange == "reversed"
    assert fig.layout.yaxis.scaleanchor == "x" and fig.layout.dragmode == "select"
    assert fig.data[0].type == "heatmap" and fig.data[1].type == "scatter"


def test_model_ui_edit_preview_no_automatic_job(monkeypatch):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest
    from geoworld_open.client import GeoWorldBackendClient
    monkeypatch.setenv("GEOWORLD_BACKEND_URL", "http://127.0.0.1:8100")
    monkeypatch.setenv("GEOWORLD_STUDIO_LOCAL_RTM", "1")
    monkeypatch.setattr(GeoWorldBackendClient, "get_llm_health", lambda _: {"reachable": False})
    calls = []
    def preview(self, selection, **kwargs):
        calls.append(selection)
        return make_preview(selection)
    monkeypatch.setattr(GeoWorldBackendClient, "preview_marmousi", preview)
    monkeypatch.setattr(GeoWorldBackendClient, "submit_job", lambda *_: pytest.fail("No implicit job"))
    app = AppTest.from_file(str(Path(__file__).parents[1] / "apps/studio_streamlit.py"))
    app.session_state["access_token"] = "test-token"
    app.session_state["manual_tools"] = True
    app.session_state["user_email"] = "model@example.test"
    app.run(timeout=20)
    next(r for r in app.radio if r.label == "Workspace").set_value("Marmousi models").run(timeout=20)
    next(b for b in app.button if b.label == "Load selected dataset (manual)").click().run(timeout=20)
    assert not app.exception and calls
    app.number_input(key="marmousi_x_start_m").set_value(10.).run(timeout=20)
    assert not app.exception and calls[-1].crop.x_start_m == 10.
    app.checkbox(key="marmousi_enable_porosity_fraction").check().run(timeout=20)
    assert not app.exception and calls[-1].overrides.porosity_fraction == .2
    app.selectbox(key="marmousi_dataset").set_value("marmousi2").run(timeout=20)
    assert not app.exception
    assert not any(b.label == "Save model preview & provenance" for b in app.button)


def test_http_model_preview_is_authenticated():
    import json
    from geoworld_open.client import GeoWorldBackendClient
    class Transport:
        def send(self, method, url, headers, body, timeout):
            assert method == "POST" and url.endswith("/models/marmousi/preview")
            assert headers["Authorization"] == "Bearer test-token"
            payload = json.loads(body)
            assert "path" not in payload
            return 200, make_preview(MarmousiSelection.model_validate(payload["selection"])).model_dump_json().encode()
    p = GeoWorldBackendClient("http://localhost:8100", token="test-token", transport=Transport()).preview_marmousi(MarmousiSelection(dataset="marmousi2"))
    assert p.selection.dataset == "marmousi2"
