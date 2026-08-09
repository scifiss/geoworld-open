# Architecture

GeoWorld Open has one bounded execution path:

```text
YAML -> ScenarioSpec -> ordered scientific operators -> WorkflowResult -> artifacts
```

## Package map

- `schema.py` defines strict, versioned, explicit public inputs.
- `operators/base.py` defines the small operator protocol and metadata contract.
- `operators/geology.py` creates layer indices from analytic geometry.
- `operators/properties.py` maps explicit scenario values into 2D arrays.
- `operators/seismic.py` computes acoustic impedance, reflectivity, and convolution.
- `operators/avo.py` computes linearized angle reflectivity and named stacks.
- `workflow.py` executes the operators in a fixed order and records a trace.
- `artifacts.py` writes arrays, report, trace, figure, and a hash manifest.
- `cli.py` and `apps/streamlit_app.py` call the same workflow.

There is no service-to-service architecture in this repository. The Streamlit demo runs locally in the same process and does not call the production GeoWorld platform.

## Operator extension

An operator exposes immutable metadata and a deterministic `run(arrays, context)` method. `MockScaleOperator` demonstrates the contract without reproducing production plugin logic. Extensions should add outputs instead of mutating existing arrays, declare their assumptions, and include tests.

## Reproducibility

The normalized scenario and seed define scientific inputs. The manifest records the software version, operator versions, scenario hash, output hashes, and creation timestamp. Scientific arrays are deterministic for the same code and scenario; wall-clock timing and artifact timestamps naturally vary.

