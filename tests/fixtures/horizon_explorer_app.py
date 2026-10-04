"""In-process synthetic reference double for testing the HTTP-only Studio UI."""
from geoworld_open.benchmarks.horizon import DT_S, evaluate, generate_benchmark
from geoworld_open.client.horizon import HorizonTrackResult
from geoworld_open.client.seismic import (
    SeismicAxis, SeismicDatasetCatalog, SeismicDatasetSummary, SeismicViewData,
)
from geoworld_open.reference.horizon import track_section
from geoworld_open.studio_seismic import render_seismic_explorer


class API:
    def __init__(self):
        self.benchmark = generate_benchmark("fault")
        self.dataset = SeismicDatasetSummary(
            dataset_id="c" * 24, display_name="Synthetic horizon fixture", format="synthetic",
            dimensionality="3d", vertical_domain="time", sample_interval=DT_S, sample_unit="s",
            shape=[24, 64, 256], geometry_status="established", amplitude_min=-1, amplitude_max=1,
            amplitude_scope="synthetic test", source="synthetic://test",
            axes=[SeismicAxis(name="inline", count=24, start=1200, stop=1223, unit="number"),
                  SeismicAxis(name="crossline", count=64, start=300, stop=363, unit="number"),
                  SeismicAxis(name="time", count=256, start=0, stop=1.02, unit="s")],
            provenance={"horizon_tracking_scope": "geoworld_generated_synthetic_only"},
        )

    def list_seismic_datasets(self):
        return SeismicDatasetCatalog()

    def list_horizon_benchmarks(self):
        return SeismicDatasetCatalog(datasets=[self.dataset])

    def get_seismic_view(self, request):
        number = request.inline if request.view_kind == "inline" else request.crossline
        section, _, horizontal = self.benchmark.section(request.view_kind, number)
        return SeismicViewData(
            dataset=self.dataset, request=request, title="Synthetic test", shape=list(section.shape),
            horizontal_label="Crossline" if request.view_kind == "inline" else "Inline",
            horizontal_unit="number", horizontal_coordinates=horizontal.tolist(),
            vertical_label="Time", vertical_unit="s", vertical_coordinates=[i * DT_S for i in range(256)],
            values=section.tolist(), amplitude_min=float(section.min()), amplitude_max=float(section.max()),
            selection_summary=f"Synthetic {request.view_kind} {number}",
        )

    def track_synthetic_horizon(self, request):
        section, truth, horizontal = self.benchmark.section(request.view_kind, request.section_number)
        tracked = track_section(section, DT_S, request)
        return HorizonTrackResult(
            request=request, **tracked, horizontal_coordinates=horizontal.tolist(), truth_time_s=truth.tolist(),
            errors_ms=[None if value is None else float((value - actual) * 1000)
                       for value, actual in zip(tracked["picked_time_s"], truth)],
            metrics=evaluate(tracked["picked_time_s"], truth), provenance={"benchmark": self.benchmark.parameters},
        )


if __name__ == "__main__":
    api = API()
    render_seismic_explorer(api, dataset=api.dataset)
