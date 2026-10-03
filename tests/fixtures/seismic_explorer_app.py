"""Synthetic public Seismic Explorer UI fixture; no backend or solver."""
import uuid

from geoworld_open.client.seismic import (
    SeismicAxis, SeismicDatasetCatalog, SeismicDatasetSummary,
    SeismicExplorerResponse, SeismicExplorerState, SeismicViewData,
    SeismicViewRequest,
)
from geoworld_open.studio_seismic import render_seismic_explorer


def summary(dataset_id, name):
    return SeismicDatasetSummary(
        dataset_id=dataset_id, display_name=name, format="rsf", dimensionality="2d",
        vertical_domain="time", sample_interval=.004, sample_unit="s", shape=[4, 5],
        axes=[
            SeismicAxis(name="trace", count=4, unit="index", start=0, stop=3, step=1),
            SeismicAxis(name="time", count=5, unit="s", start=0, stop=.016, step=.004),
        ], geometry_status="established", amplitude_min=-1, amplitude_max=1,
        amplitude_scope="synthetic fixture", source=f"configured://{name}.rsf",
        provenance={"test_only": True},
    )


DATASETS = [summary("a"*24, "Line A"), summary("b"*24, "Line B")]


def view(request):
    dataset = next(item for item in DATASETS if item.dataset_id == request.dataset_id)
    return SeismicViewData(
        dataset=dataset, request=request.model_copy(update={"view_kind": "section"}),
        title=f"{dataset.display_name} · full section", shape=[5, 4],
        horizontal_label="Trace", horizontal_unit="index", horizontal_coordinates=[0, 1, 2, 3],
        vertical_label="Time", vertical_unit="s", vertical_coordinates=[0, .004, .008, .012, .016],
        values=[[0, 1, 0, -1], [1, 0, -1, 0], [0, -1, 0, 1], [-1, 0, 1, 0], [0, 1, 0, -1]],
        amplitude_min=-1, amplitude_max=1, selection_summary=f"{dataset.display_name} full section",
        provenance={"solver_launched": False},
    )


class API:
    def list_seismic_datasets(self):
        return SeismicDatasetCatalog(datasets=DATASETS)

    def get_seismic_view(self, request):
        return view(SeismicViewRequest.model_validate(request))

    def continue_seismic_explorer(self, prompt, *, dataset_id=None, conversation_id=None):
        current = view(SeismicViewRequest(dataset_id=dataset_id))
        state = SeismicExplorerState(
            conversation_id=conversation_id or uuid.uuid4().hex,
            active_dataset_id=dataset_id, current_view=current.request, status="ready",
        )
        return SeismicExplorerResponse(state=state, view=current)


render_seismic_explorer(API())
