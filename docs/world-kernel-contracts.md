# Gate 2 World-Kernel Contract Prototype

## Status and scope

This document describes the executable Gate 2 contract prototype. It implements
the eight approved kernel concepts without adding domain physics or changing the
frozen Phase 2 branch.

```text
World
Entity
Relation
Representation
Field
WorldState
Observation
Provenance
```

`ReferenceFrame`, `Support`, and the transition Protocol are thin layered
contracts needed to exercise spatial numerical values and state lineage. They do
not become kernel concepts.

## Package structure

```text
geoworld_open.world
├── models.py          immutable kernel and minimal spatial records
├── registry.py        World aggregate and reference-integrity validation
├── xarray_adapter.py  bounded numerical Representation adapter
└── transition.py      generic append-only state-transition boundary
```

The kernel imports no geoscience package and contains no Formation, Fault,
reservoir, medical, or robotics classes. Domain labels used by the tests are
opaque strings interpreted only by their fixtures.

## Contract map

| Approved concept | Implementation |
|---|---|
| World | Frozen `World` aggregate containing semantic registries and immutable state history |
| Entity | Frozen stable identity with type ID, optional label, and Provenance references |
| Relation | Frozen typed Entity edge; core validates endpoints, domain code validates scientific meaning |
| Representation | Frozen immutable version descriptor with typed subjects, content hash, artifact reference, and lineage |
| Field | `FieldDefinition` plus supporting `FieldBinding` records |
| WorldState | Frozen role-aware state record referencing bindings and exact Representation versions |
| Observation | Frozen acquired/synthetic evidence with typed subjects and evidence Representation |
| Provenance | Frozen derivation record with typed inputs/outputs and parent lineage |

## FieldDefinition and FieldBinding

`FieldDefinition` is reusable semantic authority for canonical name, unit, value
kind, physical rank, missingness, admissible Support kinds, and domain constraint
references. It has no subject, state, or array values.

`FieldBinding` associates one FieldDefinition with a typed subject, WorldState,
Support, optional scale label, exact Representation version, validity, and
Provenance. It is a supporting record beneath Field and WorldState, not a ninth
kernel concept. Tests bind one definition to different subjects and states.

## Typed subjects and reference integrity

`SubjectRef` is a discriminated reference limited to Entity, Relation,
FieldDefinition, FieldBinding, WorldState, Support, exact Representation version,
and Observation. Representation refs require both stable ID and version.

The World validates:

- unique IDs and Representation `(ID, version)` pairs;
- Relation endpoints and optional state validity;
- all typed subjects and Provenance references;
- FieldDefinition, FieldBinding, state, Support, and Representation consistency;
- exact Representation versions used by each WorldState;
- Observation subjects and evidence Representation;
- parent-state existence and acyclic lineage;
- acyclic Representation derivation and Provenance parent lineages;
- Support/frame, Representation/Support, and FieldBinding/Representation consistency;
- synthetic-only `ground_truth` states.

The core intentionally does not decide whether a relation such as `INTERSECTS`
is scientifically valid for particular Entity types.

## Representation versions

A Representation record describes one immutable version. Its content SHA-256,
artifact URI, typed subjects, dimensions, Support/frame references, parent
Representation versions, and Provenance are fixed. A second version is a new
record and may identify the first through `derived_from`.

No storage or version-control service is implemented. The invariant is that any
content used by scientific state or lineage is immutable or uniquely
version-addressable. The in-memory xarray adapter verifies content against the
Representation hash. For an external artifact URI, the descriptor and checksum
are contract-immutable, but storage-level immutability requires the artifact
layer to content-address or independently verify the referenced bytes.

## WorldState roles

WorldState roles are:

- `asserted`: a state adopted for a study without claiming objective truth;
- `hypothetical`: an alternative scenario;
- `simulated`: output of a model or transition;
- `ground_truth`: truth known by construction in a synthetic World only.

The World rejects `ground_truth` in a field-origin World. Inversion and posterior
concepts remain future epistemic-layer records rather than WorldState roles.

## Bounded temporal values

`TemporalValue` is a supporting value record, not a ninth kernel concept. It
represents exactly one of:

- an absolute, timezone-aware timestamp; or
- finite relative/model time with an explicit nonempty unit.

There is no implicit conversion between absolute and relative time, and relative
interval bounds must use the same unit. WorldState and FieldBinding validity use
this record. Observation acquisition and valid times use it as well; acquired
Observations require acquisition time, while synthetic evidence may carry
relative/model time associated with a simulated state.

## Observation versus state

Observation is immutable evidence, not WorldState. It targets one or more typed
semantic subjects and references a separate immutable evidence Representation.
Synthetic observations remain observations. Gate 2 includes no acquisition,
noise-generation, inversion, or interpretation framework.

## xarray authority boundary

xarray is a numerical Representation adapter and never the World or WorldState.
The adapter can bundle several FieldBindings in one Dataset.

| Concern | Authoritative layer | xarray role |
|---|---|---|
| Entity and state identity | Pydantic kernel records | Mirrored read-only IDs in adapter attrs |
| FieldDefinition and binding identity | Pydantic Field records | Variable-to-binding lookup metadata |
| Canonical units and physical rank | FieldDefinition | Mirrored variable attrs; conflicting input units are rejected |
| Dimension order, shape, Support, frame | Support/ReferenceFrame and Representation | Validated dimensions and mirrored IDs |
| Numerical values | Immutable Representation version content | Dataset payload hashed into Representation SHA-256 |

Reserved semantic attrs supplied by callers are rejected. The adapter deep-copies
input data, hashes normalized coordinates/values/metadata, stores a private copy,
and returns deep copies so callers cannot mutate versioned content. Array rank
does not determine physical tensor rank.

Canonical metadata permits JSON-safe values and string mapping keys; arbitrary
Python objects and non-string keys are rejected rather than stringified. Hashing
normalizes numerical byte order while preserving dtype kind and precision, so
equivalent big- and little-endian values hash equally but float32 and float64 do
not. Variable ordering is canonical. `Missingness.FORBID` rejects NaN, NaT, and
infinity. `Missingness.ALLOW` permits NaN/NaT but still rejects infinity.
`Missingness.MASK` requires a separate explicit mask Representation and is
therefore rejected by this bounded Gate-2 adapter.

ReferenceFrame and Support records are authoritative for coordinate axis order,
direction, and units. A Support may use an ordered subset of frame axes. The
adapter mirrors absent coordinate units, rejects conflicting units, and enforces
strict monotonicity for numeric `INCREASING` and `DECREASING` coordinates. `UP`
and `DOWN` remain semantic orientation declarations and do not invent a universal
array-ordering rule. Extra array dimensions are allowed for components or other
representation axes; physical tensor rank remains explicit in FieldDefinition.

## State transitions

`StateTransition` is a Protocol outside the kernel. `apply_transition` consumes
one WorldState and atomically appends a new state, FieldBindings, Representation
versions, and Provenance to a newly validated World. It rejects in-place state
IDs, missing parent lineage, missing Provenance, cross-World output, and bindings
owned by another state. Transition Provenance must name the input WorldState and
every appended state, FieldBinding, and exact Representation version; each output
must cite one of those transition Provenance records. Persistent Entity identity
is preserved, and failures leave the original immutable World unchanged.

The test transition is deterministic metadata-only contract evidence, not a
scientific Process or domain model.

## Cross-domain fixtures

Reservoir, heart, and robot fixtures use exactly the same public classes. They
vary only opaque Entity/relation type labels, Field definitions, and evidence
labels. Each includes a small xarray-backed Field and synthetic Observation.
No medicine or robotics implementation is included.

## Private compatibility assessment

The private `geoworld/world/**` interfaces were inspected read-only.

| Private concept | Gate 2 mapping | Assessment |
|---|---|---|
| `GeoEntity` | Entity | Direct ID/type/name mapping; attributes require reviewed domain components rather than kernel copying |
| `GeoRelationship` | Relation | Direct ID/type/source/target mapping; private attributes and scientific validity rules remain private |
| `GeoState(dataset)` | WorldState plus xarray Representation bundle and FieldBindings | Structurally compatible; relative time is representable, but an adapter must separate identity/time metadata from Dataset values and make version immutability explicit |
| Observation metadata and `GeoObservation(dataset)` | Observation plus evidence Representation | Structurally compatible; acquisition/noise/context still require layered adapter mapping |
| `ProvenanceRecord` | Provenance and Representation artifact references | Compatible for source lineage; richer typed derivation edges require adapter construction |
| State/observation lineage | WorldState parent, Observation subjects, Provenance | Core IDs and relative/absolute time map structurally; production context and capability details still require explicit adapter policy |
| `RunManifest` and capability-use records | Provenance plus existing artifact/run records outside the kernel | Compatible; run status/timestamps remain execution metadata, not World semantics |

No cross-domain contradiction was found. Gate 2 does not claim complete or
lossless production migration. Adapter work remains necessary for mutable private
xarray containers, geometry references, broad context dictionaries, acquisition
details, capability records, and run-centric manifests. Full private migration is
not required for public release and is not initiated by Gate 2.

## Public/private boundary

Public code contains generic contracts, transparent validation, deterministic
fixtures, and a bounded adapter. It does not contain private ontology registries,
aliases, relation rules, causal graphs, applicability logic, calibrated defaults,
prompts, planning, RAG, memory, evaluations, production telemetry, or user data.

## Deferred beyond Gate 2

- Phase 2 scientific adaptation and GeoSpec/DAG/execution-context placement;
- geometry and coordinate transforms beyond a small regular-grid Support;
- persistent storage and external artifact management;
- deep geology, petrophysics, reservoir, geophysics, or other domain science;
- Interpretation, EstimatedState, BeliefState, uncertainty algorithms, and agents;
- broad private production migration.
