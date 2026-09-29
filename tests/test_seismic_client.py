import json
from io import BytesIO

from geoworld_open.client import GeoWorldBackendClient
from geoworld_open.client.backend import UPLOAD_CHUNK_BYTES
from geoworld_open.client.seismic import (
    SeismicDatasetCatalog, SeismicUploadRecord, SeismicViewRequest,
)
from tests.fixtures.seismic_explorer_app import DATASETS, view


class FakeTransport:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def send(self, method, url, headers, body, timeout):
        self.calls.append((method, url, headers, body, timeout))
        return 200, json.dumps(self.payloads.pop(0)).encode()


class ConsumingTransport(FakeTransport):
    def __init__(self, payloads):
        super().__init__(payloads)
        self.chunk_lengths = []
        self.reads_before_send = None

    def send(self, method, url, headers, body, timeout):
        self.reads_before_send = list(getattr(self.source, "read_sizes", []))
        assert not isinstance(body, bytes)
        self.chunk_lengths = [len(chunk) for chunk in body]
        return super().send(method, url, headers, body, timeout)


class BoundedReader:
    def __init__(self, content):
        self._stream = BytesIO(content)
        self.read_sizes = []

    def read(self, size=-1):
        self.read_sizes.append(size)
        return self._stream.read(size)


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


def test_seismic_client_uploads_binary_with_encoded_display_filename():
    record = SeismicUploadRecord(
        upload_id="c" * 32, display_filename="line one.sgy", status="ready",
        created_at="2026-09-28T12:00:00+00:00", dataset=DATASETS[0],
        validation_message="Validated regular post-stack SEG-Y.",
    )
    transport = FakeTransport([record.model_dump(mode="json")])
    client = GeoWorldBackendClient(
        "https://example.test", token="not-a-real-secret", transport=transport,
    )

    result = client.upload_seismic("line one.sgy", b"segy-bytes")

    assert result.upload_id == "c" * 32
    method, url, headers, body, _ = transport.calls[0]
    assert (method, url, body) == (
        "POST", "https://example.test/seismic/uploads", b"segy-bytes",
    )
    assert headers["X-GeoWorld-Filename"] == "line%20one.sgy"
    assert headers["Authorization"] == "Bearer not-a-real-secret"


def test_seismic_client_consumes_file_like_upload_in_bounded_lazy_chunks():
    record = SeismicUploadRecord(
        upload_id="d" * 32, display_filename="large.sgy", status="ready",
        created_at="2026-09-28T12:00:00+00:00", dataset=DATASETS[0],
    )
    source = BoundedReader(b"x" * (2 * UPLOAD_CHUNK_BYTES + 17))
    transport = ConsumingTransport([record.model_dump(mode="json")])
    transport.source = source
    client = GeoWorldBackendClient("https://example.test", token="token", transport=transport)

    result = client.upload_seismic("large.sgy", source)

    assert result.status == "ready"
    assert transport.reads_before_send == []
    assert transport.chunk_lengths == [UPLOAD_CHUNK_BYTES, UPLOAD_CHUNK_BYTES, 17]
    assert source.read_sizes == [
        UPLOAD_CHUNK_BYTES, UPLOAD_CHUNK_BYTES, UPLOAD_CHUNK_BYTES,
        UPLOAD_CHUNK_BYTES,
    ]
