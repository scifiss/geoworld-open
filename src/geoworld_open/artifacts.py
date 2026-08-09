"""Write reproducibility artifacts and provenance."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import yaml

from geoworld_open import __version__
from geoworld_open.viz import save_summary_figure
from geoworld_open.workflow import WorkflowResult

if TYPE_CHECKING:
    from geoworld_open.engine.execution import ScientificWorkflowResult


def _json_safe(value):
    from geoworld_open.provenance import json_safe

    return json_safe(value)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _scenario_bytes(result: WorkflowResult) -> bytes:
    payload = result.scenario.model_dump(mode="json", exclude_none=True)
    return yaml.safe_dump(payload, sort_keys=False).encode("utf-8")


def write_artifacts(result: WorkflowResult, output_dir: str | Path, overwrite: bool = False) -> Path:
    """Write one complete, inspectable result directory."""
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()) and not overwrite:
        raise FileExistsError(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    arrays_dir = output / "arrays"
    arrays_dir.mkdir(exist_ok=True)

    scenario_path = output / "scenario.yaml"
    scenario_path.write_bytes(_scenario_bytes(result))
    for name, array in sorted(result.arrays.items()):
        np.save(arrays_dir / f"{name}.npy", array, allow_pickle=False)

    summary_path = output / "summary.png"
    save_summary_figure(result, summary_path)

    trace_path = output / "trace.json"
    trace_path.write_text(json.dumps(result.trace, indent=2) + "\n", encoding="utf-8")

    report_lines = [
        f"# {result.scenario.name}",
        "",
        result.scenario.description,
        "",
        "## Assumptions",
        "",
        *[f"- {item}" for item in result.scenario.assumptions],
        "",
        "## Scientific scope",
        "",
        "This output is a deterministic synthetic teaching example. Properties are explicit inputs,",
        "and the seismic response uses textbook approximations. It is not field-data inversion,",
        "history matching, uncertainty quantification, or a calibrated reservoir model.",
        "",
        "## Outputs",
        "",
        *[f"- `{name}`: shape {list(array.shape)}, dtype `{array.dtype}`" for name, array in sorted(result.arrays.items())],
    ]
    (output / "report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    artifact_paths = sorted(
        path for path in output.rglob("*") if path.is_file() and path.name != "manifest.json"
    )
    manifest = {
        "schema_version": "1.0",
        "software": {"name": "geoworld-open", "version": __version__},
        "scenario": result.scenario.name,
        "scenario_sha256": hashlib.sha256(_scenario_bytes(result)).hexdigest(),
        "seed": result.scenario.seed,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "operators": [
            {key: step[key] for key in ("operator", "version", "description")} for step in result.trace
        ],
        "limitations": [
            "Synthetic educational workflow, not field-data inversion.",
            "Layer properties and perturbation multipliers are explicit scenario inputs.",
            "AVO uses a simplified linearized Aki-Richards approximation.",
        ],
        "artifacts": [
            {
                "path": str(path.relative_to(output)),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
                "deterministic": path == scenario_path or path.parent == arrays_dir,
            }
            for path in artifact_paths
        ],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return output


def write_structural_artifacts(
    result: "ScientificWorkflowResult",
    output_dir: str | Path,
    overwrite: bool = False,
) -> Path:
    """Write a coordinate-aware Phase 2 structural result and sanitized provenance."""
    from time import perf_counter

    from geoworld_open.diagnostics import save_structural_diagnostic
    from geoworld_open.provenance import (
        canonical_json,
        dataset_metadata,
        scientific_hashes,
        sha256_bytes,
        software_provenance,
    )

    started = perf_counter()
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()) and not overwrite:
        raise FileExistsError(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    arrays_dir = output / "arrays"
    coordinates_dir = output / "coordinates"

    spec_payload = result.spec.model_dump(mode="json", exclude_none=True)
    scenario_path = output / "geospec_v2.yaml"
    scenario_path.write_text(yaml.safe_dump(spec_payload, sort_keys=False), encoding="utf-8")
    if result.spec.outputs.save_arrays:
        arrays_dir.mkdir(exist_ok=True)
        coordinates_dir.mkdir(exist_ok=True)
        for name, coordinate in sorted(result.dataset.coords.items()):
            np.save(coordinates_dir / f"{name}.npy", coordinate.values, allow_pickle=False)
        for name, variable in sorted(result.dataset.data_vars.items()):
            np.save(arrays_dir / f"{name}.npy", variable.values, allow_pickle=False)

    metadata = dataset_metadata(result.dataset)
    if result.spec.outputs.save_dataset_metadata:
        (output / "dataset_metadata.json").write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
        )
    (output / "trace.json").write_text(
        json.dumps(_json_safe(result.trace), indent=2) + "\n", encoding="utf-8"
    )
    if result.spec.outputs.save_diagnostic_figure:
        diagnostic_path = output / "structure_diagnostic.png"
        save_structural_diagnostic(result, diagnostic_path)

    report = [
        f"# {result.spec.metadata.name}",
        "",
        result.spec.metadata.description,
        "",
        "## Phase 2 scientific scope",
        "",
        "This result contains explicit structural geometry, categorical facies, porosity, and masks.",
        "It deliberately contains no inferred elastic properties, fluid substitution, seismic, or AVO.",
        "",
        "## Assumptions",
        "",
        *[f"- {assumption}" for assumption in result.spec.assumptions],
    ]
    if result.compatibility:
        report.extend(["", "## Compatibility", "", f"- Mode: `{result.compatibility['mode']}`"])
        report.extend(f"- {note}" for note in result.compatibility["notes"])
    (output / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    scientific = scientific_hashes(result.dataset)
    artifact_paths = sorted(
        path for path in output.rglob("*") if path.is_file() and path.name != "manifest.json"
    )
    manifest = {
        "manifest_schema_version": "2.0",
        "geospec_schema_version": result.spec.schema_version,
        **software_provenance(),
        "scenario": result.spec.metadata.name,
        "normalized_input_sha256": sha256_bytes(canonical_json(spec_payload)),
        "seed_lineage": result.seed_lineage,
        "compatibility": result.compatibility,
        "operators": result.trace,
        "dataset": metadata,
        "scientific_hashes": scientific,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_duration_ms": round((perf_counter() - started) * 1000.0, 3),
        "artifacts": [
            {
                "path": str(path.relative_to(output)),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
                "deterministic": path.suffix in {".npy", ".yaml", ".json"}
                and path.name not in {"trace.json"},
            }
            for path in artifact_paths
        ],
    }
    (output / "manifest.json").write_text(
        json.dumps(_json_safe(manifest), indent=2) + "\n", encoding="utf-8"
    )
    return output
