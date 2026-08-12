"""Inspectable artifacts for the semantic structural World workflow."""

from __future__ import annotations

import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr
import yaml

from geoworld_open import __version__
from geoworld_open.domains.geoscience.structural import StructuralWorldResult
from geoworld_open.world import dataset_content_sha256
from geoworld_open.world_diagnostics import save_structural_world_diagnostic


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _normalized_spec_bytes(result: StructuralWorldResult) -> bytes:
    payload = result.structural_input.model_dump(mode="json", exclude_none=True)
    return yaml.safe_dump(payload, sort_keys=False).encode("utf-8")


def _dataset_metadata(result: StructuralWorldResult) -> dict[str, Any]:
    dataset = result.dataset
    return {
        "dimensions": {name: int(size) for name, size in dataset.sizes.items()},
        "coordinates": {
            name: {
                "dimensions": list(value.dims),
                "shape": list(value.shape),
                "dtype": str(value.dtype),
                "attributes": dict(value.attrs),
            }
            for name, value in dataset.coords.items()
        },
        "variables": {
            name: {
                "dimensions": list(value.dims),
                "shape": list(value.shape),
                "dtype": str(value.dtype),
                "attributes": dict(value.attrs),
            }
            for name, value in dataset.data_vars.items()
        },
        "content_sha256": dataset_content_sha256(dataset),
    }


def _canonical_bundles(result: StructuralWorldResult):
    return (result.geometry_bundle, result.stratigraphy_bundle)


def artifact_relative_path(uri: str) -> Path:
    prefix = "artifact://"
    if not uri.startswith(prefix):
        raise ValueError(f"Representation does not have a portable artifact URI: {uri!r}")
    path = Path(uri[len(prefix) :])
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe artifact URI: {uri!r}")
    return path


def write_representation_bundle(output: Path, bundle) -> None:
    dataset = bundle.to_dataset()
    representation = bundle.representation
    actual_hash = dataset_content_sha256(dataset)
    if actual_hash != representation.content_sha256:
        raise ValueError(
            f"canonical content for {representation.representation_id!r} "
            "does not match its Representation hash"
        )

    descriptor_path = output / artifact_relative_path(representation.artifact_uri)
    descriptor_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor: dict[str, Any] = {
        "schema_version": "1.0",
        "representation_id": representation.representation_id,
        "version": representation.version,
        "content_sha256": representation.content_sha256,
        "dataset_attributes": dict(dataset.attrs),
        "coordinates": {},
        "variables": {},
    }
    for category, values in (
        ("coordinates", dataset.coords),
        ("variables", dataset.data_vars),
    ):
        for name, value in sorted(values.items()):
            filename = f"{category}/{name}.npy"
            path = descriptor_path.parent / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            np.save(path, value.values, allow_pickle=False)
            descriptor[category][name] = {
                "path": filename,
                "dimensions": list(value.dims),
                "attributes": dict(value.attrs),
            }
    _write_json(descriptor_path, descriptor)


def load_representation_dataset(
    output: Path,
    descriptor_path: Path,
) -> tuple[dict[str, Any], xr.Dataset]:
    descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
    coordinates: dict[str, Any] = {}
    variables: dict[str, Any] = {}
    for category, destination in (
        ("coordinates", coordinates),
        ("variables", variables),
    ):
        for name, item in descriptor[category].items():
            path = descriptor_path.parent / item["path"]
            try:
                path.relative_to(output)
            except ValueError as error:
                raise ValueError("Representation descriptor escapes the run directory") from error
            values = np.load(path, allow_pickle=False)
            destination[name] = (
                tuple(item["dimensions"]),
                values,
                item["attributes"],
            )
    dataset = xr.Dataset(
        data_vars=variables,
        coords=coordinates,
        attrs=descriptor["dataset_attributes"],
    )
    return descriptor, dataset


def _world_summary(result: StructuralWorldResult) -> dict[str, Any]:
    world = result.world
    return {
        "world_id": world.world_id,
        "origin": world.origin.value,
        "initial_state_id": result.initial_state_id,
        "final_state_id": result.final_state_id,
        "state_lineage": {
            result.final_state_id: world.state(result.final_state_id).parent_state_id,
        },
        "entities": [
            {
                "entity_id": item.entity_id,
                "entity_type": item.entity_type,
                "label": item.label,
            }
            for item in world.entities
        ],
        "relations": [item.model_dump(mode="json") for item in world.relations],
        "field_definitions": [
            item.model_dump(mode="json") for item in world.field_definitions
        ],
        "field_bindings": [item.model_dump(mode="json") for item in world.field_bindings],
        "representations": [
            item.model_dump(mode="json") for item in world.representations
        ],
    }


def write_world_artifacts(
    result: StructuralWorldResult,
    output_dir: str | Path,
    overwrite: bool = False,
) -> Path:
    """Write a complete semantic World run without private paths or user data."""
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()) and not overwrite:
        raise FileExistsError(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    arrays_dir = output / "arrays"
    coordinates_dir = output / "coordinates"
    arrays_dir.mkdir(exist_ok=True)
    coordinates_dir.mkdir(exist_ok=True)

    normalized_spec = _normalized_spec_bytes(result)
    normalized_input = result.normalized_input_bytes
    inputs_dir = output / "inputs"
    inputs_dir.mkdir(exist_ok=True)
    (inputs_dir / "structural-input.json").write_bytes(normalized_input)
    (inputs_dir / "structural-input.yaml").write_bytes(normalized_spec)
    dataset = result.dataset
    for bundle in _canonical_bundles(result):
        write_representation_bundle(output, bundle)
    if result.structural_input.outputs.save_arrays:
        for name, value in sorted(dataset.coords.items()):
            np.save(coordinates_dir / f"{name}.npy", value.values, allow_pickle=False)
        for name, value in sorted(dataset.data_vars.items()):
            np.save(arrays_dir / f"{name}.npy", value.values, allow_pickle=False)
    else:
        arrays_dir.rmdir()
        coordinates_dir.rmdir()

    _write_json(output / "world.json", result.world.model_dump(mode="json"))
    _write_json(output / "world_summary.json", _world_summary(result))
    if result.structural_input.outputs.save_dataset_metadata:
        _write_json(output / "dataset_metadata.json", _dataset_metadata(result))
    _write_json(
        output / "execution_plan.json",
        {
            "capability_order": list(result.plan.capability_ids),
            "capabilities": list(result.numerical.trace),
            "root_seed": result.structural_input.root_seed,
            "seed_lineage": result.numerical.seed_lineage,
        },
    )
    _write_json(output / "trace.json", list(result.numerical.trace))
    _write_json(output / "diagnostics.json", result.numerical.diagnostics)
    _write_json(
        output / "provenance.json",
        [item.model_dump(mode="json") for item in result.world.provenance],
    )

    if result.structural_input.outputs.save_diagnostic_figure:
        save_structural_world_diagnostic(result, output / "structure_diagnostic.png")

    report = [
        f"# {result.structural_input.name}",
        "",
        result.structural_input.description,
        "",
        "## Semantic result",
        "",
        f"- World: `{result.world.world_id}`",
        f"- Initial state: `{result.initial_state_id}`",
        f"- Final state: `{result.final_state_id}`",
        f"- Formation entities: {sum(item.entity_type == 'geoscience:formation' for item in result.world.entities)}",
        f"- Fault entities: {sum(item.entity_type == 'geoscience:fault' for item in result.world.entities)}",
        "",
        "## Assumptions",
        "",
        *[f"- {item}" for item in result.structural_input.assumptions],
        "",
        "## Scope",
        "",
        "This deterministic structural result contains formations, faults, categorical facies,",
        "explicit porosity, reservoir-role selection, source-depth mapping, and diagnostics.",
        "It contains no inferred elastic properties, fluids, seismic, AVO, or uncertainty model.",
    ]
    (output / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    artifact_paths = sorted(
        item for item in output.rglob("*") if item.is_file() and item.name != "manifest.json"
    )
    representations = {
        f"{item.representation_id}@{item.version}": item.content_sha256
        for item in result.world.representations
    }
    manifest = {
        "manifest_schema_version": "3.0",
        "software": {
            "name": "geoworld-open",
            "version": __version__,
            "python_version": platform.python_version(),
        },
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "workflow": "structural-world",
        "structural_input_sha256": hashlib.sha256(normalized_input).hexdigest(),
        "structural_input_representation": {
            "representation_id": "representation:structural-input",
            "version": "v1",
            "artifact_uri": "artifact://inputs/structural-input.json",
        },
        "world_id": result.world.world_id,
        "initial_state_id": result.initial_state_id,
        "final_state_id": result.final_state_id,
        "root_seed": result.structural_input.root_seed,
        "seed_lineage": result.numerical.seed_lineage,
        "capabilities": list(result.numerical.trace),
        "representation_hashes": representations,
        "numerical_dataset_sha256": dataset_content_sha256(dataset),
        "diagnostics": result.numerical.diagnostics,
        "limitations": [
            "Synthetic structural geology for education and research, not field interpretation.",
            "Formation properties and structural geometry are explicit input assumptions.",
            "External artifact immutability depends on independently verified checksums.",
        ],
        "artifacts": [
            {
                "path": str(item.relative_to(output)),
                "bytes": item.stat().st_size,
                "sha256": file_sha256(item),
            }
            for item in artifact_paths
        ],
    }
    _write_json(output / "manifest.json", manifest)
    return output


def verify_world_artifact_checksums(output_dir: str | Path) -> None:
    """Verify independent file checksums and semantic Representation content."""
    output = Path(output_dir)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    for item in manifest["artifacts"]:
        path = output / item["path"]
        if not path.is_file():
            raise ValueError(f"manifest artifact is missing: {item['path']}")
        if file_sha256(path) != item["sha256"]:
            raise ValueError(f"manifest checksum mismatch: {item['path']}")

    world = json.loads((output / "world.json").read_text(encoding="utf-8"))
    representations = {
        (item["representation_id"], item["version"]): item
        for item in world["representations"]
    }
    input_representation = representations[("representation:structural-input", "v1")]
    input_path = output / artifact_relative_path(input_representation["artifact_uri"])
    if hashlib.sha256(input_path.read_bytes()).hexdigest() != input_representation["content_sha256"]:
        raise ValueError("structural input artifact does not match its Representation hash")

    for key, representation in representations.items():
        if key == ("representation:structural-input", "v1"):
            continue
        descriptor_path = output / artifact_relative_path(representation["artifact_uri"])
        descriptor, dataset = load_representation_dataset(output, descriptor_path)
        actual_hash = dataset_content_sha256(dataset)
        if descriptor["content_sha256"] != representation["content_sha256"]:
            raise ValueError(
                f"Representation descriptor hash mismatch: {representation['representation_id']}"
            )
        if actual_hash != representation["content_sha256"]:
            raise ValueError(
                f"Representation content hash mismatch: {representation['representation_id']}"
            )
