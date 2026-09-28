import json

from geoworld_open.client import GeoWorldBackendClient
from geoworld_open.client.seismic import SeismicDatasetCatalog, SeismicViewRequest
from tests.fixtures.seismic_explorer_app import DATASETS, view


class FakeTransport:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def send(self, method, url, headers, body, timeout):
        self.calls.append((method, url, headers, body, timeout))
        return 200, json.dumps(self.payloads.pop(0)).encode()


def test_seismic_client_uses_opaque_ids_and_authenticated_http_only():
    request = SeismicViewRequest(dataset_id=DATASETS[0].dataset_id)
    transport = FakeTransport([
        SeismicDatasetCatalog(datasets=DATASETS).model_dump(mode="json"),
        view(request).model_dump(mode="json"),
    ])
    client = GeoWorldBackendClient(
        "https://example.test", token="not-a-real-secret", transport=transport,
    )

    catalog = client.list_seismic_datasets()
    result = client.get_seismic_view(request)

    assert len(catalog.datasets) == 2
    assert result.dataset.dataset_id == DATASETS[0].dataset_id
    assert transport.calls[0][0:2] == ("GET", "https://example.test/seismic/datasets")
    assert transport.calls[1][0:2] == ("POST", "https://example.test/seismic/view")
    assert transport.calls[1][2]["Authorization"] == "Bearer not-a-real-secret"
    payload = json.loads(transport.calls[1][3])
    assert payload["dataset_id"] == DATASETS[0].dataset_id
    assert "path" not in payload
