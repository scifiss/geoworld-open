"""Command-line interface for the public workflow."""

from __future__ import annotations

from pathlib import Path

import typer

from geoworld_open.artifacts import write_artifacts
from geoworld_open.schema import load_scenario
from geoworld_open.workflow import run_workflow

app = typer.Typer(no_args_is_help=True, help="Run deterministic GeoWorld Open scenarios.")


@app.callback()
def main() -> None:
    """Run deterministic GeoWorld Open scenarios."""


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


if __name__ == "__main__":
    app()
