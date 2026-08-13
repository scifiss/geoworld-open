"""Command-line interface for public workflows, benchmarks, and conformance."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import typer
import xarray as xr

from geoworld_open.artifacts import write_artifacts
from geoworld_open.schema import load_scenario
from geoworld_open.workflow import run_workflow

app = typer.Typer(no_args_is_help=True, help="GeoWorld Open standard, SDK, and benchmarks.")


@app.callback()
def main() -> None:
    """Validate contracts and run deterministic GeoWorld Open scenarios."""


@app.command("validate-geospec")
def validate_geospec(path: Path = typer.Argument(..., exists=True, readable=True)) -> None:
    """Validate a public GeoSpec or legacy scenario without running it."""
    import yaml

    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise typer.BadParameter("GeoSpec root must be a mapping")
    if payload.get("schema_version") == "2.0":
        from geoworld_open.specs import load_geospec

        spec = load_geospec(path)
        name = spec.metadata.name
    else:
        spec = load_scenario(path)
        name = spec.name
    typer.echo(f"Valid GeoSpec: {name}")


@app.command("validate-world")
def validate_world_command(path: Path = typer.Argument(..., exists=True, readable=True)) -> None:
    """Validate a serialized World, including references and Provenance."""
    from geoworld_open.sdk import load_world, verify_provenance

    world = load_world(path)
    verify_provenance(world)
    typer.echo(f"Valid World: {world.world_id}")


@app.command("verify-manifest")
def verify_manifest_command(run_dir: Path = typer.Argument(..., exists=True, file_okay=False)) -> None:
    """Verify all artifact byte counts and SHA-256 hashes in a run manifest."""
    from geoworld_open.sdk import verify_manifest

    result = verify_manifest(run_dir)
    typer.echo(f"Verified {len(result.verified_artifacts)} artifacts")


@app.command("benchmark-list")
def benchmark_list() -> None:
    """List versioned public benchmark cases."""
    from geoworld_open.benchmarks import list_benchmarks

    for case in list_benchmarks():
        typer.echo(f"{case.benchmark_id}\t{case.title}")


@app.command("benchmark-run")
def benchmark_run(
    benchmark_id: str = typer.Argument(...),
    output: Path = typer.Option(Path("runs/benchmark"), "--output", "-o"),
) -> None:
    """Execute one packaged benchmark and verify its artifact manifest."""
    from geoworld_open.benchmarks import run_benchmark

    result = run_benchmark(benchmark_id, output)
    typer.echo(
        f"Completed benchmark {result.benchmark_id}; "
        f"verified {len(result.verified_artifacts)} artifacts"
    )


@app.command("conformance-reference")
def conformance_reference() -> None:
    """Run capability conformance against the minimal reference implementation."""
    from geoworld_open.conformance import check_capability
    from geoworld_open.reference import AcousticImpedanceReference

    dataset = xr.Dataset(
        {
            "vp_m_s": (("z", "x"), np.full((2, 3), 2500.0), {"units": "m/s"}),
            "density_kg_m3": (
                ("z", "x"),
                np.full((2, 3), 2200.0),
                {"units": "kg/m^3"},
            ),
        }
    )
    report = check_capability(AcousticImpedanceReference(), dataset)
    if not report.conforms:
        raise typer.Exit(code=1)
    typer.echo("Reference capability conforms")


@app.command()
def run(
    scenario: Path = typer.Argument(..., exists=True, readable=True, help="Public GeoSpec YAML file."),
    output: Path = typer.Option(Path("runs/demo"), "--output", "-o", help="Artifact directory."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Replace files in a non-empty output directory."),
) -> None:
    """Validate a scenario, execute the workflow, and write artifacts."""
    spec = load_scenario(scenario)
    result = run_workflow(spec)
    path = write_artifacts(result, output, overwrite=overwrite)
    typer.echo(f"Completed {spec.name}: {path.resolve()}")


@app.command("world-run")
def world_run(
    geospec: Path = typer.Argument(
        ...,
        exists=True,
        readable=True,
        help="Structural GeoSpec YAML authoring input.",
    ),
    output: Path = typer.Option(
        Path("runs/structural-world"),
        "--output",
        "-o",
        help="Semantic World artifact directory.",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Replace files in a non-empty output directory.",
    ),
) -> None:
    """Compile and run structural geology through the semantic World boundary."""
    from geoworld_open.domains.geoscience.structural import run_structural_world
    from geoworld_open.specs import load_geospec
    from geoworld_open.world_artifacts import write_world_artifacts

    spec = load_geospec(geospec)
    result = run_structural_world(spec)
    path = write_world_artifacts(result, output, overwrite=overwrite)
    typer.echo(
        f"Completed {result.structural_input.name}: {result.initial_state_id} -> "
        f"{result.final_state_id}; {path.resolve()}"
    )


@app.command("flagship-run")
def flagship_run(
    scenario: Path = typer.Argument(
        ...,
        exists=True,
        readable=True,
        help="Explicit flagship World YAML scenario.",
    ),
    output: Path = typer.Option(
        Path("runs/flagship-world"),
        "--output",
        "-o",
        help="Flagship World artifact directory.",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Replace files in a non-empty output directory.",
    ),
) -> None:
    """Run the bounded pressure-state and synthetic-observation demonstration."""
    from geoworld_open.domains.geoscience.flagship import (
        load_flagship_spec,
        run_flagship_world,
        write_flagship_artifacts,
    )

    result = run_flagship_world(load_flagship_spec(scenario))
    path = write_flagship_artifacts(result, output, overwrite=overwrite)
    typer.echo(
        f"Completed flagship World {result.world.world_id}: "
        f"{result.structural_result.final_state_id} -> state:flagship-baseline -> "
        f"state:flagship-perturbed; {path.resolve()}"
    )


if __name__ == "__main__":
    app()
