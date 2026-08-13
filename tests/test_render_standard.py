import pytest
from pydantic import ValidationError

from geoworld_open.benchmarks import load_render_benchmark
from geoworld_open.standard import RenderDimension, RenderSpec


@pytest.mark.parametrize(
    ("dimension", "expected"),
    [("2d", RenderDimension.TWO_D), ("3d", RenderDimension.THREE_D), ("4d", RenderDimension.FOUR_D)],
)
def test_packaged_render_requests_validate(dimension: str, expected: RenderDimension) -> None:
    request = load_render_benchmark(dimension)
    assert request.spec.dimension == expected


def test_render_spec_rejects_missing_dimension_controls() -> None:
    payload = load_render_benchmark("3d").spec.model_dump(mode="python")
    payload["camera_3d"] = None
    with pytest.raises(ValidationError, match="3D rendering requires"):
        RenderSpec.model_validate(payload)


def test_render_spec_rejects_non_animation_output_for_4d() -> None:
    payload = load_render_benchmark("4d").spec.model_dump(mode="python")
    payload["output"] = {**payload["output"], "format": "png"}
    with pytest.raises(ValidationError, match="4D output"):
        RenderSpec.model_validate(payload)
