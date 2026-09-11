"""Offline UI fixture with synthetic data; no solver, account or backend."""
import streamlit as st
from geoworld_open.client.marmousi import MarmousiPreview, ModelCrop
from geoworld_open.studio_marmousi import render_model_workspace

st.set_page_config(layout="wide")


class API:
    def preview_marmousi(self, selection):
        extent = ModelCrop(x_start_m=0., x_stop_m=100., z_start_m=0., z_stop_m=50.)
        return MarmousiPreview(selection=selection, classification="benchmark_model_preview", configuration_sha256="a"*64,
            dataset_extent=extent, resolved_crop=selection.crop or extent, shape_xz=[101, 51], spacing_m=1.,
            fields=["vp", "density"], unit="m/s", x_m=[float(i) for i in range(101)], z_m=[float(i) for i in range(51)],
            values_zx=[[1500.+j*10+i for i in range(101)] for j in range(51)], provenance={"test_only": True}, warnings=["Synthetic browser fixture"])


def no_job(*_args):
    raise AssertionError("A crop must not submit a job")


render_model_workspace(API(), no_job)
