# Release Gate 1: World-Kernel Architecture Decision

## Decision status

**Status:** **APPROVED / FROZEN** for Gate 2 implementation. Gate 2 has not
started in this closeout.

This is the canonical Gate 1 decision record. The earlier
[world-kernel architecture](world-kernel-architecture.md) and
[migration boundary](world-kernel-migration-boundary.md) documents remain
supporting analysis. This decision is governed by:

> **Small universal foundation. Deep domain implementation.**

> **Expose the architecture. Protect the intelligence.**

The kernel represents what exists, identity through change, state, numerical
representation, evidence, and derivation. Optional generic layers add space,
dynamics, epistemics, physics, scale, and planning. Domain packages supply all
scientific meaning, rules, methods, and calibrated intelligence.

The eight concept meanings, major semantic boundaries, and dependency direction
are frozen. Method signatures and serialization details remain implementation
decisions. Changing the minimal kernel requires an implementation-discovered
cross-domain contradiction, not convenience or speculative completeness.

## A. Final minimal kernel

The universal kernel contains exactly eight major concepts.

| Concept | Meaning | Universal? | Persistent? | Time-varying? | Numerical representation | Why needed |
|---|---|---:|---:|---:|---|---|
| `World` | Registry/graph boundary for identities and state history | Yes | Yes | Its referenced state history evolves | None required | Without it, identities, relations, and states have no coherent scope |
| `Entity` | Stable semantic subject that can persist through change | Yes | Yes | Its existence/validity can be time-scoped | May reference zero or more representations | Without it, a fault, heart, or robot collapses into whichever array currently depicts it |
| `Relation` | Typed, directed or undirected edge between subjects | Yes | Usually; validity may be scoped | Yes, through validity/state bindings | Optional topology representation | Without it, many-to-many structure and qualified occupancy become ad hoc fields |
| `Representation` | Version-addressable computational depiction of a subject, relation, Field, or evidence item | Yes | Stable identity plus immutable versions | Version applicability may be state-scoped | Array, grid, mesh, graph, image, point cloud, table, or latent form | Without it, semantic identity becomes coupled to one data structure and lineage can silently change |
| `Field` | Reusable `FieldDefinition` plus state/subject-specific `FieldBinding` records | Yes | Definition is persistent | Bindings/values may vary | Binding identifies an immutable Representation version | Without it, quantity semantics and actual values collapse into anonymous arrays or entity attributes |
| `WorldState` | Immutable, time-scoped asserted, hypothetical, simulated, or synthetic-ground-truth state with lineage | Yes | State record is persistent/immutable | It describes a time or interval | References scalar values and exact Field/Representation versions | Without it, persistent identity and changing conditions cannot be separated |
| `Observation` | Evidence acquired or generated about an explicitly typed semantic subject | Yes | Evidence record is immutable | Acquisition and valid times are explicit | Has its own immutable/versioned Representation | Without it, measurements and synthetic responses are mistaken for physical truth |
| `Provenance` | Source and derivation lineage for states, evidence, representations, and estimates | Yes | Append-only records | Events have time; records do not mutate | References methods, inputs, outputs, and artifacts | Without it, reproducibility and epistemic distinctions cannot be audited |

### Minimalism decisions

The following are important but are not minimal-kernel concepts:

| Candidate | Decision | Layer | What breaks if omitted from the kernel? |
|---|---|---|---|
| `ReferenceFrame` | Reposition | Spatial | Only spatial worlds lose a shared coordinate contract; non-spatial kernel identity remains sound |
| `SpatialSupport` | Reposition as spatial `Support` | Spatial | Spatial field placement becomes ambiguous, but identity/state/evidence remain coherent |
| `Process` | Reposition | Dynamics | State transitions lose a generic execution contract, not identity semantics |
| `Action` | Reposition | Dynamics | Interventions become domain-specific calls, not a kernel failure |
| `Interpretation` | Reposition | Epistemic | Semantic claims about evidence become less explicit, but observations remain evidence |
| `BeliefState` | Reposition | Epistemic | Partial knowledge cannot be represented richly, but the asserted World remains valid |
| `Agent`, `Goal`, `Plan` | Reposition | Planning | Autonomous planning is unavailable; the physical World remains independent |
| `Constraint` | Reposition | Dynamics/science | Domain validation becomes less composable, but kernel identity is unchanged |
| `PhysicsModel` | Reposition | Science | The kernel can record externally derived states but cannot calculate transitions |
| `Scale` | Reposition | Spatial/representation | Cross-scale comparisons become unsafe; non-spatial identity remains valid |
| `Uncertainty` | Reposition | Epistemic metadata/representation | Confidence cannot be expressed; it is not part of physical identity |
| `BalanceLaw` | Reposition | Physics | Physics descriptions become less structured; world semantics do not break |
| `ConstitutiveLaw` | Reposition | Physics | Material closure models become opaque capabilities |
| `BoundaryCondition`, `InterfaceCondition` | Reposition | Physics | Model setup becomes opaque configuration |
| `Coupling` | Reposition | Physics | Multi-model exchange becomes opaque orchestration |
| `ValidityDomain` | Reposition | Science | Applicability cannot be checked explicitly |

`Component` is a composition mechanism, not a ninth universal concept or a
universal taxonomy. An Entity may be associated with typed components defined by
generic or domain layers. The kernel does not define universal geometry,
material, mechanics, transport, or thermodynamics component classes.

## B. Canonical architecture diagram

```mermaid
flowchart LR
    W[World] --> WS[WorldState t0 with explicit epistemic role]
    WS --> OM[Observation model]
    OM --> O[Observation]
    O --> IN[Interpretation / inference]
    IN --> BS[BeliefState]
    BS --> AG[Agent / human / optimizer]
    G[Goal] --> AG
    AG --> PL[Plan logic]
    PL --> A[Proposed Action]
    A --> AV[Constraint and validity checks]
    AV --> PR[Process implemented by PhysicsModel or capability]
    WS --> PR
    PR --> NS[WorldState t1]
    NS --> W
    PV[Provenance] -. records .-> WS
    PV -. records .-> O
    PV -. records .-> BS
    PV -. records .-> A
    PV -. records .-> NS
```

The World does not depend on an Agent, LLM, xarray, or PhysicsModel. Those layers
consume or produce references to kernel records through explicit contracts.

## C. Semantic object graph

```mermaid
flowchart TD
    W[World] --> ER[Entity registry]
    W --> RG[Relation graph]
    W --> SH[WorldState history]
    ER --> E[Entity]
    RG --> R[Relation]
    R --> E
    SH --> S[WorldState]
    S --> FB[FieldBinding]
    FB --> FD[FieldDefinition]
    FB --> RV[RepresentationVersion]
    RI[Representation identity] --> RV
    RI --> SR[SubjectRef]
    O[Observation] --> SR
    OR[Evidence RepresentationVersion] --> SR
    O --> OR
    SR -. typed reference .-> E
    SR -. typed reference .-> R
    SR -. typed reference .-> FD
    SR -. typed reference .-> S
    SR -. typed reference .-> SP[Support]
    P[Provenance] --> S
    P --> RV
    P --> O
    P --> SR
```

Canonical invariants:

1. `Fault F1` is not its triangulated surface, voxel mask, or simulator faces.
2. `Formation A` is an Entity; porosity and pressure are Fields.
3. Entity and relation IDs survive representation replacement and state change.
4. A WorldState references `FieldBinding` records and exact Representation
   versions; it is not exactly one dataset.
5. An Observation has evidence data and acquisition semantics; it is not state.
6. Interpretations and beliefs retain links to observations, methods, uncertainty,
   and provenance and cannot silently become observations or asserted truth.

### Typed semantic subject references

`SubjectRef` is a small discriminated reference record, not a ninth kernel
concept and not a new universal graph. It contains a `subject_kind` and exactly
one stable identifier, such as:

```text
entity_id
relation_id
field_definition_id
world_state_id
support_id
representation_version_id
process_or_event_result_id
```

Observation, Representation, Provenance, and Interpretation use this mechanism
to identify what they concern while preserving reference integrity. Supported
subject kinds are explicit and extensible by reviewed contracts; arbitrary
record-to-record edges are not allowed.

Examples:

- a pressure gauge observes a pressure Field at a well Support;
- a seismic survey provides evidence about a WorldState and its spatial Support;
- a fault interpretation concerns a Fault Entity and a surface Representation
  version;
- a production measurement observes a rate Field associated with a Well.

### Representation identity and immutable versions

A Representation has a stable semantic identity and one or more immutable,
uniquely addressable versions. Once a Representation version participates in a
WorldState or Provenance record, its content and content identity cannot change.

```text
fault_surface
    version 1
    version 2
        derived_from version 1
```

Each version records or references its content identity/checksum, format, subject,
Support, ReferenceFrame, Scale, validity, and Provenance. A WorldState and every
derivation identify the exact version used. This applies equally to grids,
meshes, surfaces, point sets, xarray-backed arrays, images, tables, and learned
latent representations. The contract requires addressability and immutability,
not a heavyweight version-control system.

### Relation mechanics

A generic Relation record contains:

```text
relation_id
source_entity_id
relation_type_id
target_entity_id
directionality
valid_time_or_state_scope
qualifiers_or_component_references
uncertainty_reference
provenance_reference
```

The kernel enforces reference integrity and declared directionality. Geoscience
defines whether `INTERSECTS`, `PENETRATES`, `PART_OF`, or `OCCUPIES` is valid for
particular types. Those rules and inference chains remain domain intelligence.

### Material identity and occupancy

Material composition does not imply location. A geoscience domain may define:

```text
FluidMaterial(CO2)
FluidOccupancy(
    material = CO2,
    host = ReservoirRegion_A,
    support = PlumeRegion_t1,
    saturation = FieldBinding(...),
)
```

Rock/mineral/fluid material describes substance. Formation, reservoir region, and
plume region describe spatial bodies or roles. `FluidOccupancy` is a qualified
domain relation or state component, not a universal Entity subtype.

## D. Spatial architecture

Location lives in a Representation on a Support in a ReferenceFrame, not as
universal `x`, `y`, and `z` attributes on Entity.

```text
Entity or Field
    -> Representation
        -> Geometry or value structure
        -> Support
        -> ReferenceFrame
        -> optional CoordinateTransform references
        -> Scale
```

| Concept | Decision and responsibility |
|---|---|
| `ReferenceFrame` | First-class spatial-layer identity defining dimensions, axes, units, order, origin/datum, handedness/orientation, vertical convention, optional time reference, and parent/transform references |
| `CoordinateTransform` | Versioned directed mapping between frames with domain, invertibility, accuracy/uncertainty, validity, method, and provenance |
| `Support` | Domain on which geometry or values are defined: point set, curve, surface, volume, cells, mesh elements, voxel region, time interval, or categories |
| `SpatialSupport` | Spatial specialization of Support; not a separate universal root abstraction |
| `Geometry` | Shape and position payload/semantics carried by a Representation; not Entity identity |
| `Representation` | Stable identity whose immutable versions bind geometry or Field values to subject/support/frame/scale and exact data/artifact content |

Geometry is not promoted to the minimal kernel because not every Entity needs
geometry and because geometry always arrives through a representation. Support
and ReferenceFrame remain first-class in the optional spatial layer because
Fields, observations, and geometries must share coordinate meaning independently
of any one data structure.

Examples:

- A Fault may have a global-XYZ surface, fault-local strike/dip/normal surface,
  voxel mask, and simulator-face representation concurrently.
- A Well may have a global trajectory, measured-depth coordinate support, and
  true-vertical-depth transform without changing well identity.
- A Formation may have boundary surfaces and volume/grid representations.
- A FluidMaterial may have no spatial representation until an occupancy binding
  relates it to a host and support.

## E. State architecture

Persistent identity includes World, Entity, durable Relation, FieldDefinition,
ReferenceFrame, and Representation identity/version records. Time-scoped content
includes entity/relation validity, Field values, occupancy, pressure, saturation,
temperature, stress, pose, velocity, and production conditions.

A WorldState contains or references:

```text
state_id and world_id
valid time or interval
parent and derivation state IDs
epistemic role: asserted, hypothetical, simulated, or synthetic ground_truth
active entity/relation validity
scalar values and FieldBinding records
exact immutable Representation versions
constraints and residuals
uncertainty/epistemic status references
assumptions and Provenance
```

`WorldState(t0) -> Process/Action -> WorldState(t1)` preserves entity identity and
records transition lineage. Static and dynamic properties use the same Field
abstraction: static bindings have broad validity; dynamic bindings have narrower
validity or multiple versions. Separate static/dynamic classes would duplicate
semantics and make properties difficult to reclassify.

A WorldState is the structured state being reasoned about; it does not
automatically claim objectively known physical truth. Its explicit role prevents
epistemic promotion by accident:

| Situation | Correct record/role |
|---|---|
| Synthetic experiment with known constructed state | WorldState with `ground_truth` role |
| Forward-simulated scenario | WorldState with `simulated` role |
| Field reservoir model adopted for a study | WorldState with `asserted` role |
| Alternative field scenario | WorldState with `hypothetical` role |
| Seismic inversion result | `EstimatedState` linked to evidence and method |
| Ensemble posterior | `BeliefState` over estimates/hypotheses |

`ground_truth` is valid only where truth exists by construction. Field subsurface
models must not be named or treated as `TrueWorldState`. An estimate may be used
to construct a later asserted scenario only through an explicit, provenance-
recorded decision; its original inferential identity remains intact.

### FieldDefinition and FieldBinding

The approved `Field` concept has two underlying records. `FieldDefinition`
declares reusable quantity or classification semantics independently of any one
subject, time, support, or array:

```text
FieldDefinition
    field_id
    quantity or classification semantics
    canonical unit
    value kind
    physical rank
    admissible supports
    missingness semantics
    domain constraint references
```

For example, pressure may be continuous, scalar, and canonically measured in Pa.
That definition does not mean pressure in one formation at one time.

`FieldBinding` associates a definition with an actual state occurrence and exact
data:

```text
FieldBinding
    field_definition reference
    typed subject reference
    WorldState reference
    Support reference
    Scale reference
    immutable Representation version reference
    validity
    Provenance reference
```

For example, a binding can associate pressure with `Formation_A`, state `t1`, a
reservoir-grid Support, and `pressure_array_r17`. One FieldDefinition can be
reused across many subjects, states, supports, scales, and representations.
`FieldBinding` is a record/mechanism beneath Field and WorldState, not a ninth
major kernel concept.

### Field and xarray decision

The strong hypothesis is **approved**:

> xarray is one numerical representation/storage mechanism for Fields and State,
> not the semantic World itself.

An xarray Dataset can efficiently bundle compatible Field values for computation.
It cannot replace entity/relation identity, multiple representations, observation
status, frame transforms, or world history.

Physical tensor semantics are distinct from array dimensionality. Stress,
strain, and permeability may declare rank, basis/frame, component transformation,
and symmetry. `seismic[x, y, time, angle, vintage]` is a multidimensional array,
not automatically a physical tensor.

## F. Observation and belief architecture

Four concepts are required across the kernel and epistemic layer:

| Concept | Meaning | Layer |
|---|---|---|
| `Observation` | Acquired or generated evidence with typed SubjectRef targets, acquisition time, support, immutable Representation version, noise/quality, and provenance | Kernel |
| `Interpretation` | A semantic claim connecting evidence to an entity, region, event, or hypothesis | Epistemic |
| `EstimatedState` | A state estimate derived from evidence/model with method, uncertainty, and validation lineage | Epistemic |
| `BeliefState` | Distribution or alternatives over estimates/hypotheses | Epistemic |

An ensemble is one BeliefState representation, not the definition of belief.
Parametric distributions, particles, intervals, possibility sets, or learned
posteriors may also represent belief.

Examples retain distinct status:

```text
physical/as-asserted porosity FieldBinding in a WorldState
neutron-log Observation
log-derived porosity Interpretation or Estimated Field
seismic-inverted porosity EstimatedState
tensor-completed porosity Estimated Field with observed/estimated masks
```

Inference and tensor completion must preserve source observations, observed and
estimated masks, method, uncertainty, validation metrics, and provenance.

## G. Physics architecture

`PhysicsModel` is a generic science-layer contract, not a kernel concept. It may
describe state variables, supports, equations/model references, conditions,
sources, couplings, assumptions, scale, validity, solver/evaluator, diagnostics,
and residuals. It supports analytical evaluators, numerical solvers, external
simulators, surrogates, and learned effective models without claiming scientific
equivalence.

| Candidate | Decision | First-class contract? | Reason |
|---|---|---:|---|
| `PhysicsModel` | Science layer | Yes | Common applicability and state-transition boundary |
| `BalanceLaw` | Physics layer | Yes, as an optional descriptor | Captures conserved quantities and residuals without forcing one scalar PDE form |
| `ConstitutiveLaw` | Physics/domain layer | Yes | Separates material closure from balance principles |
| `BoundaryCondition` | Physics layer | Yes | Applies a typed condition to model/support boundaries |
| `InterfaceCondition` | Physics layer | Yes | Represents behavior across contacts/faults/interfaces distinctly from exterior boundaries |
| `Coupling` | Physics/execution layer | Yes | Declares exchanged quantities, direction, temporal semantics, and consistency strategy |
| `Constraint` | Generic science/dynamics layer | Yes | Unifies validation, residuals, inference checks, and action preconditions |
| `ValidityDomain` | Generic science layer | Yes | Makes assumptions, parameter/support/scale ranges, exclusions, and applicability explicit |
| Initial conditions and source/sink terms | PhysicsModel configuration | No separate universal type initially | Promote only if multiple implementations need shared behavior |
| Governing equations | Referenced model content/metadata | No universal equation AST | Avoid modeling all mathematics in the architecture |

BalanceLaw permits differential, integral, algebraic, vector, tensor, and
discrete formulations. Mass, species, energy, momentum, and charge are domain
implementations. Darcy flow, elasticity, friction, relative permeability,
capillary pressure, equations of state, and reaction kinetics remain domain
constitutive models. No fundamental-theory hierarchy is introduced.

Detailed applicability reasoning, coupling selection, calibrated parameters, and
scientific causal knowledge remain private intelligence.

## H. Multiscale architecture

`Scale` is a first-class value object in the spatial/representation layer, not an
Entity. It records spatial and temporal support/resolution, sampling or averaging
window, effective-property semantics, validity range, and provenance.

Pore-, grain-, core-, well-log-, seismic-, simulation-cell-, field-, and
basin-scale values may share a quantity definition while differing in support,
resolution, method, and averaging semantics.

Upscaling, downscaling, homogenization, restriction, and prolongation are
execution/domain operators. Their outputs record source/target Support and Scale,
method, assumptions, information loss, uncertainty, and lineage. Fractal,
multifractal, and other scaling laws remain optional domain PhysicsModels.

## I. Agent architecture

Agent, Goal, and optional Plan contracts belong above the physical and epistemic
layers. An Agent may be a human scientist, deterministic planner, optimizer, LLM,
reinforcement-learning policy, or hybrid. Its physical body may separately be an
Entity.

```text
Observation
    -> Interpretation / belief update
    -> BeliefState
    -> Agent(Goal, constraints)
    -> Plan logic
    -> proposed Action
    -> validation and applicability
    -> Process / PhysicsModel
    -> new WorldState
```

`Plan` is an optional first-class planning record when replay, approval,
comparison, or provenance is required; it is not part of the kernel. An Agent may
propose actions or experiments but cannot redefine physical state, relabel an
estimate as observation, or bypass constraints and validity checks.

## J. Geoscience-domain architecture

The geoscience domain is deep and modular; it extends contracts rather than
adding concepts to the kernel.

```text
world/
    core/          identity, relation, state, field, representation, evidence
    spatial/       frames, supports, transforms, scale
    epistemics/    interpretations, estimates, beliefs
    dynamics/      process, action, constraint contracts
    provenance/    derivation graph and artifact lineage

science/
    physics/       model, law, condition, coupling, validity contracts
    execution/     capabilities, plans, deterministic runtime adapters

domains/geoscience/
    common/        public-safe quantity/entity vocabulary and shared conventions
    geology/       formations, faults, stratigraphy, geometry, structural processes
    petrophysics/  rock/fluid measurements, saturation, porosity, log relations
    rock_physics/  elastic/material response and published substitutions
    reservoir/     regions, occupancy, flow state, wells/reservoir interaction
    geomechanics/  stress, strain, constitutive and failure models
    geochemistry/  composition, species, reactions, equilibrium/kinetics
    geophysics/    wave fields, acquisition, seismic/electromagnetic observations
    production/    controls, rates, facilities-facing state and observations
    wells/         trajectories, completions, MD/TVD frames, log observations
    monitoring/    vintages, sensors, change detection, experiment definitions
```

This is a responsibility map, not a mandated one-directory-per-concept tree.
Modules should split only when dependency direction and real implementations
justify it. `common` must remain small: it cannot become an ontology dumping
ground or encode workflow planning.

| Domain | Extends the kernel with | Must not redefine |
|---|---|---|
| Geology | Formation/Fault entities, geologic relations, structural processes and representations | Entity, Relation, Representation identity mechanics |
| Petrophysics | Quantity definitions, log observations, interpretation and constitutive operators | Field or Observation semantics |
| Reservoir | Reservoir roles/regions, FluidOccupancy, flow processes and operational actions | WorldState or occupancy as material identity |
| Production | Rate/control Fields, production observations, interventions, constraints | Action/Process distinction |
| Geomechanics | Tensor Fields, constitutive/failure laws, interface conditions | Physical tensor versus array distinction |
| Geochemistry | Material/species entities, composition Fields, reaction processes | Entity identity or BalanceLaw contract |
| Geophysics | Wave PhysicsModels, acquisition, seismic/EM observations and inversions | Observation versus state/estimate distinction |
| Wells | Well entities, trajectory representations, local frames, completions and log support | ReferenceFrame/Support mechanics |
| Monitoring | ObservationSpec, vintages, comparisons, uncertainty and experiments | Provenance or belief semantics |

Medicine or robotics could add sibling domain packages using the same contracts,
but they are architecture tests only and are not implementation goals.

## K. Cross-industry sanity test

| Category | Faulted reservoir | Beating heart | Robot manipulating an object |
|---|---|---|---|
| Entities | formation, fault, well, fluid material, reservoir region | patient, heart, chambers, tissue, device | robot, links, gripper, object, table |
| Relations | intersects, penetrates, part-of, occupies | part-of, connected-to, perfused-by | part-of, contacts, supports, grasps |
| Representations | horizons, fault surfaces, grids, well trajectories | anatomy meshes, segmentations, images | meshes, kinematic tree, point cloud |
| ReferenceFrames/Support | survey/depth/fault-local/well MD-TVD; cells/surfaces | patient/scanner/anatomical; tissue/mesh | world/base/joint/tool/camera; bodies/contact regions |
| Fields/WorldState | facies, pressure, saturation, stress, rates | pressure, flow, electrical potential, strain | pose, velocity, occupancy, contact force |
| Observations | seismic, logs, pressure, production | ECG, MRI, ultrasound, pressure | camera, encoder, tactile, force/torque |
| Processes | deformation, multiphase flow, reactions, waves | electrophysiology, contraction, blood flow | rigid-body dynamics and contact |
| Actions | drill, complete, inject, produce | pace, administer drug, perform procedure | move, apply torque, grasp, push |
| Agent/Goal | scientist/operator; characterize or monitor storage | clinician/controller; diagnose or stabilize | controller; manipulate safely |

The kernel is unchanged across all three. Only domain entity types, relations,
Fields, representations, PhysicsModels, constraints, observations, actions, and
validity knowledge differ. No domain-specific hack is required, so the
cross-industry acceptance test passes conceptually.

## L. Private world migration classification

The private `src/geoworld/world/**` package was inspected only at the
architecture/interface level. Its tracked files were not modified. This table is
a future private migration decision, not permission to copy code publicly.

| Existing private abstraction | Decision | Gate 1 disposition |
|---|---|---|
| Strict/extensible JSON-safe base models | KEEP | Strong serialization and namespaced-extension foundation |
| `QuantitySpec` | KEEP / EXTEND | Keep value, unit, and uncertainty; distinguish scalar value from FieldBinding |
| `VariableDefinition` | REFACTOR | Become quantity/Field semantics; aliases and full registries remain private |
| `CoordinateDefinition` | REFACTOR | Separate axis metadata from ReferenceFrame, Support, and transforms |
| `ScientificContext` | REPLACE as aggregate | Split assumptions, validity, quality, uncertainty, and provenance records |
| Provenance/quality/uncertainty records | KEEP / EXTEND | Attach through stable references to state, representation, observation, and estimates |
| `GeoEntity` | KEEP / EXTEND | Retain identity; move geometry to Representation references |
| `GeometryReference` | REPLACE | Use Representation + ReferenceFrame + Support + Provenance |
| `GeoRelationship` | KEEP / EXTEND | Add validity/state scope, direction, qualifiers, and uncertainty refs |
| `GeoModelGraph` | EXTEND / REPOSITION | Become persistent World identity/relationship registry, separate from state/data |
| `GeoStateMetadata` | KEEP / EXTEND | Preserve identity/time/lineage and add world plus binding references |
| `GeoState(dataset)` | REPOSITION | Numerical Field-bundle/StateRepresentation, not WorldState itself |
| Runtime xarray state validation | KEEP / REPOSITION | Numerical representation validator; geoscience bounds move to domain Constraints |
| `GeoObservation` and metadata | KEEP / REFACTOR | Separate acquisition spec, evidence identity, representation, support, quality, uncertainty |
| Noise/acquisition specifications | KEEP / EXTEND | Observation-layer contracts with domain modalities |
| `GeoBelief` weighted ensemble | REFACTOR | One BeliefState representation rather than the universal belief type |
| Hard-coded categorical-name detection | DEPRECATE | Use explicit Field value and semantic kinds |
| `ActionSpec` | KEEP / EXTEND | Generic intervention with targets/preconditions; domain meaning remains private |
| `WorldRunSpec` | REPLACE | Decompose into semantic specs and compiled ExecutionPlan |
| Requested process/output specs | REPOSITION | ExperimentSpec and ExecutionPlan |
| Uncertainty execution configuration | REFACTOR | Separate epistemic uncertainty representation from sampling/runtime settings |
| Capability metadata | KEEP / EXTEND | Add semantic IO, supports/scales, validity, methods, and provenance |
| Process/observation/inversion Protocols | KEEP / EXTEND | Align signatures with WorldState, Observation, and BeliefState |
| Run manifest and canonical hashes | KEEP / EXTEND | Preserve reproducibility; add world/field/representation/evidence lineage |
| Capability-use records | KEEP / EXTEND | Scientific method/capability lineage; keep operational telemetry separate |
| State and observation lineage | KEEP / EXTEND | Generalize into a derivation graph without losing compact records |
| Compatibility adapters | KEEP temporarily | Explicit migration boundary; deprecate after consumers migrate |

Explicit answers:

1. **Is `GeoState(dataset)` too numerically centered?** Yes, if treated as the
   semantic state. It remains valuable as an immutable numerical Field bundle.
2. **Where do entities and relations live?** In the persistent World registry and
   typed relation graph, with state-scoped validity where required.
3. **How does state reference Fields?** Through FieldBinding records that identify
   FieldDefinition, subject, Support, Representation version, Scale, time, and Provenance.
4. **How do representations relate to state?** A representation identity/version
   may be persistent or state-scoped; WorldState references the applicable version.
5. **What becomes persistent World?** Entity, relation, Field-definition, frame,
   and representation registries plus immutable state/derivation history.
6. **Where do observations and belief live?** Observation is kernel evidence;
   Interpretation, EstimatedState, and BeliefState live in the epistemic layer.
7. **What is already strong?** Strict schemas, quantity records, immutable xarray
   containers, capability protocols, acquisition/noise records, manifests,
   canonical hashing, and explicit state/observation/capability lineage.

## M. Preserved Phase 2 migration classification

Reviewed commit:
`10b43f00abd456ccbb85653898250bfdfd748fcb`. It remains unmodified and
unmerged on `feature/phase2-scientific-foundation`.

| Phase 2 component | Decision | Gate 1 placement |
|---|---|---|
| xarray conventions | KEEP / ADAPT | Numerical Field-bundle representation, not World |
| `GeoSpecV2` | REDESIGN / REPOSITION | Geoscience-facing umbrella/compiler; schema version is data metadata, not class identity |
| V1 compatibility/migration | KEEP temporarily | Explicit geoscience compatibility boundary |
| Variable/operator contracts | KEEP / ADAPT | Capability/execution contracts with subject/support/validity semantics |
| Dependency graph/DAG | KEEP / REPOSITION | Compiled ExecutionPlan beneath World/Physics semantics |
| Execution context | REFACTOR | Reference WorldState, representation registry, deterministic resources, and provenance |
| Namespace-derived RNG/SeedSequence | KEEP | Deterministic execution infrastructure with seed lineage and order independence |
| Structural geology kernels | KEEP / REPOSITION | Public geoscience domain implementations |
| Facies definitions/array | KEEP / ADAPT | Domain classification definitions plus categorical Field representation |
| Porosity | KEEP / ADAPT | FieldBinding with subject, Support, Scale, units, validity, and Provenance |
| Reservoir masks | REPLACE / REPOSITION | Explicit Region/Role or derived selection Field; reservoir meaning is contextual |
| Fault masks | KEEP / ADAPT | Derived Representation/Support of Fault, never Fault identity |
| Displacement fields | KEEP / ADAPT | State-scoped Field with frame, sign, support, scale, and method |
| Boundary clipping mask | KEEP | Diagnostic/quality Field with derivation lineage |
| Structural provenance | KEEP / EXTEND | Link entity, representation, state, method, capability, and artifact |
| Diagnostic visualization | KEEP / REPOSITION | Domain diagnostic view, not state semantics |
| Scientific tests | KEEP / EXTEND | Add identity/representation/state/frame semantic tests |
| Clean-room records | KEEP | Mandatory public provenance for independently implemented science |

Phase 2 is scientifically valuable but is not architecture-complete. Its RNG,
numerical conventions, kernels, tests, and clean-room evidence should survive.
Its GeoSpec, DAG, execution context, masks, and arrays require semantic placement
before integration. Gate 1 does not merge, rebase, cherry-pick, or amend it.

### GeoSpec decomposition decision

One GeoSpec must no longer mean world, state, experiment, and execution at once.

| Stable conceptual spec | Responsibility |
|---|---|
| `WorldSpec` | Persistent entities, relations, frames, and representation declarations |
| `StateSpec` | Initial/current values, FieldBinding records, occupancy, time, and constraints |
| `ObservationSpec` | Acquisition design, observed subjects/supports, noise, quality, and missingness |
| `ExperimentSpec` | Scientific question, compared states, interventions, observations, outputs, acceptance metrics |
| `ExecutionPlan` | Compiled capabilities, dependencies, deterministic resources, seeds, data movement, artifacts |

`GeoSpec` may remain a geoscience user-facing umbrella that compiles into these
contracts. Serialized documents carry an explicit `schema_version`; class names
should remain stable and must not encode `V2`, `V3`, or later version identities.

## N. Public/private boundary matrix

| Area | GeoWorld Open | Private GeoWorld intelligence |
|---|---|---|
| Kernel | Small interfaces, invariants, reference integrity, examples | Production persistence, lifecycle, migration, authorization integration |
| Ontology | Minimal Formation/Fault/Well/material examples and opaque type IDs | Full ontology, aliases, terminology resolution, validity/inference rules |
| Fields | Generic contracts and small published quantity examples | Complete property registry, conversions, derived-property intelligence |
| Relations | Generic mechanics and transparent examples | Scientific relation rules, causal graph, inference and resolution |
| Spatial | Frames, Support, transforms, simple grids/meshes | Survey integration, operational transforms, private spatial policies |
| State | Immutable public contracts | Persistence, concurrency, project/user lifecycle and recovery |
| Observations | Generic evidence/acquisition and synthetic examples | Private ingestion, conditioning, data governance, modality knowledge |
| Belief/inference | Explicit distinctions and transparent reference ensemble | Ranking, priors, interpretation policy, private inference and evaluation |
| Physics | Contracts plus independently implemented published methods | Calibrated models, private algorithms, applicability and coupling intelligence |
| Constraints/validity | Explicit rules for public methods | Full scientific rule base and automatic applicability reasoning |
| Scale | Generic metadata and transparent transforms | Calibrated up/downscaling policies and parameters |
| Execution | Small deterministic DAG/plan and reproducible provenance | Workflow planning, scheduling, resource policy, retries, security, operations |
| Agents | Mockable Agent/Goal/Action interfaces and validation boundary | Prompts, policies, routing, memory, RAG, model selection and evaluations |
| Data | Synthetic/licensed examples and reproducible artifacts | User/customer data, private fixtures, knowledge, benchmarks, telemetry |

The public ontology must expose types and contracts needed to understand and run
reference science, but must not encode private aliases, causal rules, operator
selection, calibrated defaults, coupling decisions, planning, prompts, or
evaluation cases. Public scientific implementations require published references,
clean-room records, and independently derived tests.

## O. Recommended implementation architecture

Implementation should be **contract-first, validated by a thin private
compatibility spike, and independently public for reference science**. Complete
private production migration is not a public-release prerequisite.

### Private production path

The private repository remains the production source of truth and provides real
requirements against which Gate 2 contracts can be tested. Gate 2 should use only
a narrow, disposable compatibility/prototype slice:

```text
private World/Entity/Relation registries
    -> immutable WorldState and FieldDefinition/FieldBinding records
    -> representation adapters for existing xarray GeoState
    -> observation and provenance adapters
    -> capability/execution adapters
    -> one representative existing product boundary
```

This exposes where abstract contracts fail against real geoscience workflows
without initiating broad private migration, changing production behavior, or
requiring a package-tree rewrite. Private migration may continue independently
after the first GeoWorld Open release.

### Public reference path

GeoWorld Open should implement only approved, public-safe contracts and
independently implemented published science:

```text
geoworld_open/world/       cohesive kernel, spatial, state, epistemic modules
geoworld_open/physics/     generic model/law/condition/validity contracts
geoworld_open/execution/   deterministic capabilities and ExecutionPlan
geoworld_open/domains/     bounded geoscience reference implementations
geoworld_open/specs/       stable specs plus schema-versioned serialization
```

Start with cohesive modules rather than one file per abstract concept. Split
only when concrete implementations create real dependency pressure. Do not add a
graph database, ontology framework, workflow engine, agent framework, or universal
equation language to satisfy architecture diagrams.

The repositories share reviewed concepts and serialized interoperability
contracts, not source dependencies or automatic synchronization. Any public
implementation must pass an explicit release-boundary and clean-room review.

## P. Release Gates 2-5 dependency plan

Gate 1 approval freezes conceptual meanings and dependency direction, not every
method signature. Gates 2 and 3 must iterate together because a kernel designed
without scientific use is speculative, while science integrated without semantic
contracts recreates the current array-centric architecture.

| Gate | Objective | Required outputs | Entry condition | Exit condition |
|---|---|---|---|---|
| **Gate 2: Minimal World-Kernel Contract Prototype** | Prove identity through evidence and lineage without deep domain physics | Public-safe kernel prototype; thin private compatibility spike; Entity/Relation/WorldState; FieldDefinition/FieldBinding; immutable Representation versions; Observation; Provenance; lightweight spatial concepts; xarray adapter; reservoir/heart/robot fixtures | Gate 1 approved/frozen | Reference integrity, immutability, epistemic role, versioning, cross-domain fixtures, and tests pass without geoscience dependencies in core |
| **Gate 3: Preserved Phase 2 Adaptation** | Prove real scientific output travels through the kernel | Separate integration path adapting xarray conventions, RNG, provenance, structural kernels, tests, clean-room records, and diagnostics; semantic adaptation of GeoSpec, execution context, DAG, facies, porosity, masks, and displacement | First Gate 2 slice works | Preserved science/tests pass; xarray, DAG, GeoSpec, and masks do not become World or semantic Entity identity |
| **Gate 4: One Vertical World Demonstration** | Build one coherent and impressive faulted-subsurface world | Formations, Fault, Well, Brine, ReservoirRegion; typed relations; grid/surface/trajectory representations; bounded Field set such as facies/porosity/pressure/temperature; one transparent Process from `t0` to `t1`; at least one appropriate Observation; full Provenance | Gates 2 and 3 jointly approved | One reproducible end-to-end world proves Entity, Relation, Representation, Field, WorldState, Process, Observation, and Provenance together |
| **Gate 5: Presentation and Release Audit** | Prepare GeoWorld Open for public visibility | Professional visualization and hero figure; architecture diagram; high-quality positively positioned README; Product/Blog links; scientific, provenance, reproducibility, IP-boundary, clean-room, secret/Gitleaks, license, CI, fresh-install, and content audits | Gate 4 accepted | All release audits pass and the public/private product distinction is accurate |

### Gate 2-Gate 3 iteration loop

1. Gate 2 implements one thin contract slice: persistent entities/relations,
   one WorldState, one FieldDefinition/FieldBinding, one immutable xarray-backed
   Representation version, one Observation, and Provenance.
2. Gate 3 maps one preserved Phase 2 structural output through that slice on a
   dedicated integration branch without modifying the preserved commit.
3. Failures are classified as contract defects, adapter defects, or domain
   semantics. Only genuine cross-domain contract defects revise Gate 2.
4. Repeat with Fault representation/displacement, facies classification, porosity,
   and diagnostics.
5. Freeze the contracts only after both semantic fixtures and Phase 2 scientific
   tests pass. Then finish the remaining Gate 3 migration.

This is iterative contract validation, not permission to merge Phase 2 during
Gate 1 or to let Phase 2 implementation details dictate the kernel.

### Gate 4 scope boundary

The recommended flagship is a faulted subsurface World containing two or more
Formations, one Fault, one Well, brine material, and one ReservoirRegion. It
demonstrates `INTERSECTS`, `PENETRATES`, `PART_OF`, and `OCCUPIES`; grid/volume,
structural, and trajectory representations; a bounded Field set; one transparent
state-changing Process; and one Observation pathway.

Gate 4 does **not** require broad reservoir simulation, geomechanics,
geochemistry, seismic/AVA, inversion, tensor completion, uncertainty framework,
multiscale framework, or agent planning before release.

### Gate 5 positioning and post-release growth

Gate 5 should lead with positive positioning such as:

> **A scientific world-model architecture for the subsurface.**

It distinguishes the private-powered GeoWorld Product from the public GeoWorld
Open reference implementation without leading with exclusions. After the first
public release, later versions may progressively add petrophysics, minerals and
fluids, rock physics, reservoir processes, production, geomechanics,
geochemistry, seismic/AVO, monitoring, uncertainty, multiscale, inversion,
learned world models, and agent planning. None is an initial-release prerequisite.

## Q. Architecture risks

| Risk | Failure mode | Mitigation/gate evidence |
|---|---|---|
| Over-abstraction | Dozens of empty types delay science | Eight-concept kernel; require two real consumers before promoting adjacent concepts |
| Ontology bloat | Universal package learns Formation, Tumor, Robot, or every relation | Opaque type IDs in core; domain packages own types/rules; public allowlist review |
| Duplicate semantic/numerical state | WorldState and xarray diverge or both claim authority | FieldDefinition/FieldBinding adapter, immutable lineage, canonical semantic/numerical consistency tests |
| Mutable representation lineage | A reused representation ID silently points to changed scientific inputs | Stable identity, immutable content-addressable versions, exact version references in WorldState and Provenance |
| Coordinate ambiguity | Arrays align by name while frames/datums/directions differ | Explicit ReferenceFrame, Support, transforms, axis semantics, validity, and provenance |
| Scale ambiguity | Core/log/seismic/grid values are compared as equivalent | Scale metadata and explicit transformation operators with loss/uncertainty lineage |
| Observation/truth confusion | Measurements, inversions, or synthetic outputs overwrite state | Separate Observation, Interpretation, EstimatedState, BeliefState, and asserted WorldState |
| Entity/material/occupancy confusion | CO2 identity acquires intrinsic coordinates or saturation | Domain occupancy relation/component links material, host, support, and Field binding |
| Physical tensor/array confusion | Any multidimensional array is labeled a tensor | Explicit physical rank, basis, symmetry, and transformation metadata separate from dimensions |
| Physics abstraction overreach | Universal equation system tries to model every theory | PhysicsModel contracts and references only; equations/solvers remain implementations |
| Constraint duplication | Schema, physics, planning, and UI enforce inconsistent rules | Typed Constraint results with subjects, severity, tolerance, residual, provenance |
| Private ontology leakage | Public aliases/rules reveal scientific planner and know-how | Public allowlist, clean-room records, deny-list scans, independent tests, boundary review |
| Public/private overcoupling | Repositories require synchronized source or expose private internals | No package dependency or auto-sync; reviewed concepts and serialized contracts only |
| Premature framework lock-in | Graph/workflow/agent framework dictates semantics | Framework-neutral records and Protocols; adapters remain replaceable |
| Phase 2 history damage | Rebase or rewrite destroys preserved scientific evidence | Dedicated integration branch later; preserved commit remains immutable |
| Agent bypasses science | LLM marks hypotheses as truth or runs invalid actions | Agent above belief; action validation, validity, deterministic capability, and provenance gates |
| Provenance becomes telemetry | Public scientific records reveal operational intelligence | Separate reproducibility lineage from private monitoring and policy data |

## Gate 1 acceptance decision

**Can the same small kernel represent a faulted reservoir, a beating heart, and
a robot manipulating an object without changing the universal kernel?** Yes.
The cross-industry table uses the same eight concepts and optional generic layers;
only domain types, rules, fields, models, and actions change.

**Can GeoWorld add deep geology, petrophysics, reservoir, geomechanics,
geochemistry, production, wells, monitoring, and geophysics without bloating the
kernel?** Yes. Each domain extends opaque types and generic contracts while the
kernel remains ignorant of scientific vocabulary and applicability rules.

**Can xarray, simulators, learned latent models, observations, and AI agents
coexist without becoming synonymous with the World?** Yes. xarray and latent
models are Representations, simulators implement Process/PhysicsModel
capabilities, observations are evidence, and agents operate above BeliefState.

### Gate decision

Gate 1 architecture is **APPROVED / FROZEN**.

The eight-concept kernel frozen for Gate 2 implementation is:

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

Adjacent spatial, epistemic, dynamics, physics, scale, and planning concepts
remain layered contracts. The freeze covers concept meanings, major semantic
boundaries, and dependency direction; it does not freeze method signatures or
serialization details. A minimal-kernel change requires an implementation-
discovered cross-domain contradiction.

This approval does not begin Gate 2 or authorize Phase 2 integration,
PhysicsModel implementation, rock physics, seismic/AVO, reservoir simulation,
AI planning, deployment changes, visibility changes, licensing changes, README
repositioning, or public/private package dependencies.
