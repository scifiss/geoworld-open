import json

from geoworld_open.client.backend import GeoWorldBackendClient
from geoworld_open.client.horizon import HorizonTrackRequest, HorizonTrackResult


class FakeTransport:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def send(self, method, url, headers, body, timeout):
        self.calls.append((method, url, headers, body, timeout))
        return 200, json.dumps(self.payload).encode()


def test_horizon_client_is_authenticated_http_and_preserves_selected_seed():
    request = HorizonTrackRequest(
        dataset_id="c" * 24, view_kind="inline", section_number=1212, seed_trace=0,
        seed_time_s=.408, window_start_s=.3, window_stop_s=.5, max_jump_samples=2,
    )
    expected = HorizonTrackResult(
        request=request, status="partial", horizontal_coordinates=[300, 301],
        picked_time_s=[.408, None], confidence=[1., 0.],
        failure_reasons=[None, "jump_limit_or_weak_waveform"],
        truth_time_s=[.408, .408], errors_ms=[0., None],
        metrics={"mae_ms": 0., "failure_rate": .5}, provenance={"source_unchanged": True},
    )
    transport = FakeTransport(expected.model_dump(mode="json"))
    client = GeoWorldBackendClient("https://example.test", token="test-token", transport=transport)
    assert client.track_synthetic_horizon(request) == expected
    assert transport.calls[0][:2] == ("POST", "https://example.test/seismic/horizons/track")
    assert json.loads(transport.calls[0][3]) == request.model_dump(mode="json")
    assert transport.calls[0][2]["Authorization"] == "Bearer test-token"
    transport.payload = {"datasets": [], "warnings": []}
    assert client.list_horizon_benchmarks().datasets == []
    assert transport.calls[1][:2] == ("GET", "https://example.test/seismic/horizons/benchmarks")
