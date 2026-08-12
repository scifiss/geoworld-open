# Gate 3: Scientific Foundation Integration

## Scope

Gate 3 selectively adapts the public scientific prototype at frozen commit
`10b43f00abd456ccbb85653898250bfdfd748fcb` to the approved eight-concept World
Kernel. It does not merge that branch and does not add elastic, fluid, seismic,
AVO, uncertainty, AI, or production behavior.

The authoritative flow is:

```text
GeoSpec authoring input
  -> one-time immutable CompiledStructuralInput
  -> canonical JSON + exact structural-input Representation
  -> semantic World bootstrap (persistent Entities and Relations)
  -> immutable initial WorldState
  -> ExecutionPlan of structural capabilities
  -> pure NumPy/xarray numerical kernels
  -> immutable Representations and FieldBindings
  -> immutable final WorldState
  -> typed Provenance, diagnostics, and checksummed artifacts
```

GeoSpec, the execution plan, and xarray are not alternate World models. **GeoSpec
is consumed only at compile/bootstrap time.** Structural execution is driven by
an immutable, content-bound scientific input associated with the World and
initial WorldState. The plan is a dependency-checked execution mechanism below
World semantics, and xarray is an in-memory numerical Representation.

`CompiledStructuralInput` contains only the structural values currently used:
grid semantics, ordered formations and properties, the bounded facies catalog,
ordered fold/fault parameters, method configuration, root seed, assumptions,
and output options. Its finite, sorted, compact JSON serialization is hashed
without Python repr or fallback conversion. Equivalent input has the same hash;
any changed scientific parameter has a different hash.

## Phase 2 inventory

| Phase 2 component | Decision | Gate 3 treatment |
|---|---|---|
| `specs/models.py` | ADAPT | Preserve strict structural inputs as `GeoSpec` with serialized `schema_version`; remove architectural `GeoSpecV2` naming. |
| `specs/compatibility.py` | DEFER | Legacy `run` remains unchanged; no elastic or fluid properties are reinterpreted as structural semantics. |
| `engine/contracts.py` | REPOSITION | Retain typed variable and capability contracts below the semantic World. |
| `engine/graph.py` | REPOSITION | Retain deterministic dependency compilation as `ExecutionPlan`, never as World authority. |
| `engine/execution.py` | REPLACE | Dataset-first execution is replaced by a World transition wrapper around independently testable numerical capabilities. |
| `engine/random.py` | KEEP/ADAPT | Preserve SHA-256 namespace-derived `SeedSequence`/`Generator` behavior and expose lineage. |
| `science/geology.py` | ADAPT | Preserve analytic fold, fault, source-depth, clipping, facies, porosity, and selection equations in pure structural numerics. |
| `data.py` | ADAPT | Preserve cell-centered `depth,x` coordinates in the authoritative Gate 2 frame/support contracts. |
| `diagnostics.py` | ADAPT | Keep a bounded four-panel scientific correctness diagnostic. |
| `provenance.py` | REPLACE | Scientific derivation uses Gate 2 `Provenance`; only a lightweight run manifest remains outside the kernel. |
| Phase 2 artifact writer | ADAPT | Write semantic summaries, arrays, representation hashes, diagnostics, and checksums without private paths. |
| Phase 2 structural tests | KEEP/ADAPT | Preserve geometry/value assertions and add identity, binding, state, provenance, and regression tests. |
| Phase 2 clean-room documents | KEEP AS EVIDENCE | The frozen branch remains the historical implementation record; this document records adaptation decisions. |

## Semantic geology

- Each explicit layer is a persistent `geoscience:formation` Entity. Formation
  identity is independent of layer-index, facies, porosity, and grid arrays.
- Each explicit fault is a persistent `geoscience:fault` Entity. A fold is a
  bounded `geoscience:fold` Entity because it is an explicit named structure.
- `facies` is a categorical Field. Its category codes and meanings originate in
  the exact content-bound facies catalog; xarray attributes only mirror them.
- `porosity` is a continuous dimensionless Field represented by a
  FieldDefinition and output-state FieldBinding; it is not Entity metadata.
- A Formation relation qualifier records its explicit reservoir role.
  `reservoir_selection` is a derived Boolean Field selecting cells whose source
  material belongs to such a Formation; it is not Reservoir identity.
- `fault_selection(fault, depth, x)` is a derived Boolean Field. Its `fault`
  coordinate stores persistent `fault:<id>` Entity IDs, and true means that a
  cell lies on that Fault's explicitly selected displaced side. The array does
  not create or define Fault identity.

## Structural Field classification

| Field | Classification |
|---|---|
| `source_depth_m` | computational Field |
| `structural_displacement_m` | derived scientific Field |
| `fold_displacement_m` | derived scientific Field |
| `fault_displacement_m` | derived scientific Field |
| `fault_selection` | derived scientific Field |
| `boundary_clipped_mask` | diagnostic Field |
| `layer_index` | computational Field |
| `facies` | scientific state Field |
| `porosity` | scientific state Field |
| `reservoir_selection` | derived scientific Field |

The classification is carried as a public domain constraint reference on each
FieldDefinition and mirrored as descriptive xarray metadata.

## State transition and provenance

The compiler creates Formation, Fault, and Fold identity, structural relations,
FieldDefinitions, one local depth/x ReferenceFrame, one regular-grid Support,
and `state:structural-initial`. The initial state references
`representation:structural-input@v1`, whose content hash covers the exact
canonical structural input. Before any capability executes,
`StructuralTransition` recalculates the compiled-input hash and rejects it if it
does not match that World-bound Representation. It then executes the validated
plan and calls the Gate 2 atomic `apply_transition()` boundary.

The output has two immutable xarray Representations: structural geometry and
stratigraphic fields. Every numerical variable has one FieldBinding in
`state:structural-final`. Typed Provenance references the exact input
Representation. Geometry provenance also cites the input state and explicit
Fault/Fold Entities. Stratigraphic provenance cites the input state, geometry
Representation, and Formation Entities. Transition provenance cites the input
state, exact input, relevant Formation/Fault/Fold Entities, and emits both
numerical Representations, every FieldBinding, and the final state. The
original World and initial state remain unchanged on success or failure.

Numerical artifact export is sourced from immutable Representation-backed
bundles rather than mutable Dataset copies. Each portable `artifact://` package
contains a descriptor and `.npy` payloads from which the canonical xarray
content is reconstructed and checked against the Representation hash. The run
manifest separately records file SHA-256 checksums. The input artifact is the
exact canonical JSON whose checksum equals the input Representation hash.
External storage immutability remains a storage-layer boundary.

## Numerical regression against frozen Phase 2

The frozen example `structural_multifault_v2.yaml` was executed from detached
worktree commit `10b43f0`. Gate 3 ran the exact equivalent input. Floating arrays
used `rtol=0`, `atol=1e-12`; integral, categorical, and Boolean arrays used exact
equality.

| Frozen quantity | Gate 3 quantity | Comparison | Maximum/count difference | Tolerance | Result |
|---|---|---:|---:|---:|---|
| `source_depth_m` | `source_depth_m` | allclose | 0.0 | 1e-12 | PASS |
| `structural_displacement_m` | same | allclose | 0.0 | 1e-12 | PASS |
| `fold_displacement_m` | same | allclose | 0.0 | 1e-12 | PASS |
| `fault_displacement_m` | same | allclose | 0.0 | 1e-12 | PASS |
| `fault_mask` | `fault_selection` | exact | 0 cells | 0 | PASS |
| `boundary_clipped_mask` | same | exact | 0 cells | 0 | PASS |
| `layer_index` | same | exact | 0 cells | 0 | PASS |
| `facies` | same | exact | 0 cells | 0 | PASS |
| `porosity` | same | allclose | 0.0 | 1e-12 | PASS |
| `reservoir_mask` | `reservoir_selection` | exact | 0 cells | 0 | PASS |

The only intentional coordinate-semantic change is from Phase 2 fault labels
(`east_normal_fault`) to explicit Entity references
(`fault:east_normal_fault`). The values are unchanged.

## Runnable paths and compatibility

The legacy command remains:

```bash
geoworld-open run examples/scenarios/layered_reservoir.yaml
```

The semantic structural path is separate:

```bash
geoworld-open world-run examples/scenarios/structural_multifault.yaml \
  --output runs/structural-world
```

This separation prevents the structural World work from silently changing the
legacy educational seismic workflow. Structural V1 migration is deferred rather
than guessing that sand means reservoir or mapping Vp, Vs, density, CO2, or
elastic inputs into the new World.

## Deferred, dropped, and remodeled concepts

- **DEFER:** V1 structural migration, broader GeoSpec decomposition, uncertainty,
  observations, property inference, and additional geoscience domains.
- **DROP from Gate 3:** Phase 2 elapsed-time hashes and competing scientific
  provenance classes. Execution timing may exist in future telemetry but is not
  semantic provenance.
- **REMODEL:** `fault_mask` and `reservoir_mask` become explicit selection Fields;
  Dataset-first execution becomes an atomic semantic World transition; GeoSpec
  becomes a one-time compiled input whose canonical Representation is bound to
  the initial WorldState.

No private GeoWorld implementation, ontology, prompt, planner, knowledge asset,
evaluation, or calibrated scientific recipe was copied into this integration.
