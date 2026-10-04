"""Deterministic screenshot fixture for the professional Seismic Explorer workspace."""
import streamlit as st

from geoworld_open.client.horizon import HorizonTrackRequest
from geoworld_open.client.seismic import SeismicViewRequest
from geoworld_open.studio_seismic import render_seismic_explorer
from horizon_explorer_app import API


api = API()
identity = "c" * 24
prefix = f"horizon_{identity}_inline_1212"
defaults = {
    "seismic_dataset_id": identity,
    "seismic_active_dataset": identity,
    "horizon_direction": "inline",
    f"{prefix}_trace": 16,
    f"{prefix}_time": .408,
    f"{prefix}_start": .30,
    f"{prefix}_stop": .50,
    f"{prefix}_jump": 2,
}
for key, value in defaults.items():
    st.session_state.setdefault(key, value)
request = HorizonTrackRequest(
    dataset_id=identity, view_kind="inline", section_number=1212,
    seed_trace=16, seed_time_s=.408, window_start_s=.30,
    window_stop_s=.50, max_jump_samples=2,
)
st.session_state.setdefault("horizon_result", api.track_synthetic_horizon(request))
st.session_state.setdefault(
    "horizon_configuration", (identity, "inline", 1212, 16, .408, .30, .50, 2),
)
st.session_state.setdefault(
    "seismic_response",
    {
        "view": api.get_seismic_view(
            SeismicViewRequest(dataset_id=identity, view_kind="inline", inline=1212)
        ),
        "analysis": None,
        "state": None,
    },
)

st.set_page_config(page_title="Seismic Explorer workspace", layout="wide")
render_seismic_explorer(api, dataset=api.dataset)
