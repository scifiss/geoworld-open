# Architecture

GeoWorld Open retains its GeoSpec V1 regression path and adds a coordinate-aware
GeoSpec V2 scientific path:

```text
GeoSpec V1 -> legacy ordered operators -> legacy artifacts

GeoSpec V2 -> scientific validation -> typed DAG -> xarray Dataset
           -> structural diagnostics + expanded provenance artifacts
```

The V1 path remains identifiable and does not silently acquire V2 scientific
meaning. V1 scenarios may also be migrated into a labeled `v1_structural_only`
view that deliberately omits their legacy elastic and seismic fields.

## Package map

- `schema.py` defines the preserved GeoSpec V1 contract.
- `specs/` defines GeoSpec V2 and the explicit V1 structural migration.
- `data.py` defines xarray dimensions, coordinates, units, and metadata conventions.
- `engine/` defines typed variables, scientific operators, graph validation, execution,
  and namespace-derived random generators.
- `science/geology.py` implements the independent public structural operators.
- `operators/base.py` remains the V1 operator protocol.
- `operators/geology.py` creates layer indices from analytic geometry.
- `operators/properties.py` maps explicit scenario values into 2D arrays.
- `operators/seismic.py` computes acoustic impedance, reflectivity, and convolution.
- `operators/avo.py` computes linearized angle reflectivity and named stacks.
- `workflow.py` executes only the preserved V1 operator sequence.
- `artifacts.py` writes arrays, report, trace, figure, and a hash manifest.
- `cli.py` and `apps/streamlit_app.py` call the same workflow.

There is no service-to-service architecture in this repository. The Streamlit demo runs locally in the same process and does not call the production GeoWorld platform.

## GeoSpec V2 operator extension

A V2 operator declares an ID, version, scientific method ID, required and
produced variables, dimensions, units, dependencies, assumptions, references,
and determinism. The graph compiler rejects cycles, missing dependencies and
producers, conflicting producers, and contract mismatches before execution.

Each operator receives a stable namespace-specific `numpy.random.Generator`.
It returns an xarray dataset fragment and diagnostics. Undeclared variable
overwrites are rejected.

## GeoSpec V1 operator extension

An operator exposes immutable metadata and a deterministic `run(arrays, context)` method. `MockScaleOperator` demonstrates the contract without reproducing production plugin logic. Extensions should add outputs instead of mutating existing arrays, declare their assumptions, and include tests.

## Reproducibility

The normalized scenario and seed define scientific inputs. V2 provenance records
the Git revision and dirty state, dependency versions, root and child seed lineage,
operator methods, references, input/output hashes, dataset metadata, and artifacts.
Scientific hashes are separated from timestamps and elapsed durations.
