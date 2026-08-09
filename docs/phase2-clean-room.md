# Phase 2 Clean-Room Record

Phase 2 was implemented from the approved public design, the pre-existing
`geoworld-open` source, NumPy/xarray/Pydantic public APIs, and general mathematical
concepts. Private GeoWorld source, fixtures, outputs, prompts, and runtime
abstractions were not consulted or copied to implement this phase.

| Component | Scientific or numerical basis | Related private capability may exist | Independence and tests |
|---|---|---|---|
| Cell-centered coordinates | Regular Cartesian finite-cell convention | Yes | Independently defined; monotonicity and unit tests |
| Layer assignment | Cumulative explicit interval boundaries and search | Yes | Direct NumPy interval lookup; exact horizontal-layer test |
| Sinusoidal fold | Explicit analytic vertical coordinate displacement | Yes | General trigonometry; identity and deterministic tests |
| Planar faults | Explicit line geometry and signed source-depth translation | Yes | Independently specified sign conventions; known-throw tests |
| Multiple structures | Sequential composition of explicit coordinate transforms | Yes | Declared list order; deterministic multifault tests |
| Facies/reservoir masks | Explicit categorical lookup and Boolean classification | Yes | No inferred lithology; integrity and dtype tests |
| Typed DAG | Topological sort over declared scientific contracts | Yes | Independent lightweight design; cycle/producer/contract tests |
| RNG lineage | NumPy `SeedSequence` plus SHA-256 namespace-derived spawn keys | Yes | No private seed policy; order and global-state tests |
| xarray data boundary | Named dimensions, coordinates, and variable metadata | Yes | Public xarray API; alignment/metadata tests |
| Provenance | Canonical input, scientific dataset, and artifact hashing | Yes | Sanitized independent manifest; repeatability tests |

## Explicit exclusions

Phase 2 includes no geological inference, calibrated deformation, damage zones,
field-derived priors, rock-frame models, fluid behavior, elastic physics, seismic,
AVA, uncertainty, model selection, private evaluation, or production orchestration.

The analytic methods are reference-oriented synthetic geometry. They are not
claimed to model mechanically balanced restoration or field-scale structural history.
