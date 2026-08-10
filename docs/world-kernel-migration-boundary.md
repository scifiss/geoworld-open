# Phase 1.5 Migration and Public/Private Boundary

## 1. Repository reconciliation

At creation of `design/world-kernel`:

```text
main = origin/main = 0b290516937c71a4a3e602a668660672c8e7469f
feature/phase2-scientific-foundation = 10b43f00abd456ccbb85653898250bfdfd748fcb
design/world-kernel starts from main at 0b290516
```

The Phase 2 commit remains unmodified on its separate branch. It was not merged,
rebased, amended, squashed, cherry-picked, or copied into this design branch.

The public working tree was clean before this documentation work. The private
repository contained pre-existing unrelated local changes, but tracked
`src/geoworld/world/**` files were unmodified and were inspected only at the
architectural/interface level.

## 2. Existing private world-model classification

This classification guides future private refactoring; it does not authorize
copying any implementation into GeoWorld Open.

| Existing private concept | Decision | Architectural direction |
|---|---|---|
| Strict/extensible JSON-safe models | KEEP | Retain strict serialization and namespaced extensions |
| `QuantitySpec` | KEEP WITH ADAPTATION | Keep value/unit/uncertainty; distinguish scalar values from Field bindings |
| `VariableDefinition` | REFACTOR | Become Field/quantity semantics; private aliases and registries stay private |
| `CoordinateDefinition` | REFACTOR | Split axis metadata from ReferenceFrame, Support, and transforms |
| `ScientificContext` | REPLACE AS AGGREGATE | Separate assumptions, validity, uncertainty, quality, and provenance records |
| Provenance/quality/uncertainty metadata | KEEP AND EXTEND | Attach to entities, states, representations, observations, and derivations |
| `GeoEntity` | KEEP WITH ADAPTATION | General Entity identity; remove direct geometry ownership in favor of Representation refs |
| `GeometryReference` | REPLACE | Use Representation + ReferenceFrame + Support + provenance |
| `GeoRelationship` | KEEP WITH ADAPTATION | Add optional validity/state scope; domain relation rules stay outside kernel |
| `GeoModelGraph` | EXTEND | Become World semantic registry/graph, separate from state and data |
| `GeoStateMetadata` | KEEP WITH ADAPTATION | Preserve identity/time/lineage; add world and field/representation bindings |
| `GeoState(dataset)` | REPOSITION | Good numerical snapshot container, too numerically centered to equal WorldState |
| Runtime xarray validation | KEEP/REPOSITION | Validate numerical Field representations; move hard-coded geoscience bounds to domain constraints |
| `GeoObservation` and metadata | KEEP WITH ADAPTATION | Separate acquisition specification, evidence record, representation, support, and uncertainty |
| Noise/acquisition specs | KEEP/EXTEND | Observation-layer contracts; domain modalities and models remain extensions |
| `GeoBelief` weighted ensemble | REFACTOR | One BeliefState representation, not the universal definition of belief |
| Hard-coded categorical-name detection | DEPRECATE | Replace with explicit Field value/semantic kinds |
| `ActionSpec` | KEEP WITH ADAPTATION | Generic intervention contract plus preconditions/targets; domain action meaning stays private |
| `WorldRunSpec` | REPLACE | Decompose into WorldSpec, StateSpec, ObservationSpec, ExperimentSpec, ExecutionPlan |
| Requested process/output specs | REPOSITION | Belong to ExperimentSpec and compiled ExecutionPlan |
| Uncertainty configuration | REFACTOR | Separate epistemic representation from sampling/execution configuration |
| Capability metadata | KEEP/EXTEND | Add typed semantic IO, validity, support/scale, method, and provenance contracts |
| Process/observation/inversion protocols | KEEP/EXTEND | Align with WorldState, Observation, and BeliefState boundaries |
| Run manifest and canonical hashing | KEEP/EXTEND | Add world/entity/representation/observation lineage while preserving canonical hashes |
| Capability/state/observation lineage | KEEP/EXTEND | Generalize to provenance graph without production telemetry leakage |
| Compatibility adapters | KEEP TEMPORARILY | Narrow migration boundary; deprecate after consumers move |

### Answers to the key private-design questions

`GeoState(dataset)` is not wrong; it is too narrow to be the world. It should
become a numerical Field-bundle or StateRepresentation associated with a richer
WorldState.

`World` should contain entity and relation identity independently from xarray.
WorldState should bind scalar/Field values and representations to those entities,
not equal one Dataset.

Persistent identity belongs to entities, relation records, field definitions,
reference frames, and representation records. Values, occupancy, active topology,
and dynamic relations belong to time-scoped state.

Representations live in a registry referenced by entities, fields, states, and
observations. Observations live in the epistemic/evidence layer. BeliefState lives
in the epistemic layer above observations and does not mutate asserted state.

Current provenance should evolve from run-centric records into a composable
derivation graph while retaining compact manifests and canonical hashes.

## 3. Unmerged Phase 2 classification

Commit reviewed: `10b43f0 Build Phase 2 scientific data and structural foundation`.

| Phase 2 component | Decision | World-kernel placement |
|---|---|---|
| xarray conventions | KEEP WITH ADAPTATION | Numerical representation for Field bundles, not World itself |
| GeoSpec V2 | REDESIGN/REPOSITION | Geoscience convenience compiler into WorldSpec + StateSpec + ExperimentSpec |
| V1 migration | KEEP TEMPORARILY | Geoscience compatibility layer with explicit legacy status |
| Variable/operator contracts | KEEP WITH ADAPTATION | Execution/capability layer with semantic subject/support and validity |
| Lightweight DAG compiler | KEEP/REPOSITION | Compiled ExecutionPlan, never semantic world identity |
| Execution context | REFACTOR | Reference WorldState, representation registry, provenance, and deterministic resources |
| Namespace-derived RNG | KEEP | Execution infrastructure; preserve seed lineage and order independence |
| Structural geometry kernels | KEEP/REPOSITION | Public geoscience geology-domain implementations |
| Facies definitions/array | KEEP WITH ADAPTATION | Facies classes in geoscience; categorical Field representation in state |
| Porosity array | KEEP WITH ADAPTATION | Porosity Field binding with subject, support, scale, units, and provenance |
| Reservoir mask | REPLACE/REPOSITION | Explicit Region/Role or derived selection Field; reservoir status is not inherent in facies |
| Fault masks | KEEP WITH ADAPTATION | Derived representation/support of a Fault entity, not the Fault identity |
| Fault displacement fields | KEEP WITH ADAPTATION | State-scoped Field with frame/sign/support semantics |
| Boundary clipping mask | KEEP | Diagnostic/quality Field with explicit derivation |
| Structural provenance | KEEP/EXTEND | Link entity, representation, state, method, and artifact lineage |
| Structural diagnostic | KEEP/REPOSITION | Geoscience diagnostic visualization |
| V2 CLI dispatch | REFACTOR LATER | Select/compile specs into execution plans; preserve explicit V1 path |
| Scientific tests | KEEP/EXTEND | Add identity/representation/state and cross-frame semantic tests |
| Clean-room records | KEEP | Required for every public domain implementation |
| Documentation | KEEP/RECONCILE | Retain scientific details; update placement after architecture integration |

Phase 2 should eventually be integrated through a dedicated integration branch
after the kernel contracts are accepted. Preserve its commit identity; do not
rebase or amend it merely to make the history linear.

## 4. Public/private boundary matrix

| Area | GeoWorld Open | Private GeoWorld |
|---|---|---|
| Kernel concepts | Minimal interfaces and semantics | Production implementation and migration policy |
| Entity types | Formation, Fault, Well, FluidMaterial reference subset | Complete ontology, aliases, lifecycle, resolution |
| Relations | Generic relation contract and small explicit examples | Relation registry, validity rules, inference, causal knowledge |
| Fields | Generic Field/representation contracts and explicit examples | Full property registry, aliases, conversions, derived-property intelligence |
| Spatial | ReferenceFrame, Support, transforms, simple public examples | Survey/grid integration, private transforms, operational mappings |
| State | Immutable public WorldState contract | Persistence, lifecycle, concurrency, user/project integration |
| Observation | Generic evidence/acquisition contracts and synthetic examples | Private ingestion, modalities, conditioning, data governance |
| Belief/interpretation | Generic distinctions and transparent ensemble example | Inference policies, ranking, interpretation knowledge, private evaluation |
| Physics | Contracts plus independently implemented published methods | Calibrated models, proprietary methods, applicability and coupling intelligence |
| Constraints/validity | Explicit public rules for public methods | Full scientific rule base and automatic applicability selection |
| Scale | Generic metadata and transparent transforms | Field-derived upscaling/downscaling policies and calibrated parameters |
| Execution | Lightweight deterministic plan/DAG and provenance | Production scheduling, resource policy, retries, security, operations |
| Agents/planning | Generic mockable contracts and validation boundary | Prompts, planning policy, routing, memory, RAG, model selection, evaluations |
| Provenance | Reproducibility lineage and sanitized artifacts | Operational telemetry, audit policy, internal capability intelligence |
| Data/examples | Synthetic, licensed, explicit public cases | User/customer data, internal research, private fixtures and benchmarks |

Public code must never contain private aliases, defaults, ontology-resolution
tables, applicability heuristics, coupling selection, benchmark cases, prompts,
or production traces. Equivalent public scientific methods require independent
references, clean-room records, and independently derived tests.

## 5. Proposed future private architecture

Design only:

```text
src/geoworld/
├── world/
│   ├── core/             # identity, world graph, state, fields, representations
│   ├── spatial/          # frames, support, transforms, topology, scale
│   ├── epistemics/       # observations, interpretations, estimates, beliefs
│   ├── dynamics/         # process/action/constraint contracts
│   └── provenance/       # derivation graph, artifacts, manifests
├── science/
│   ├── physics/          # generic model/law/condition/coupling contracts
│   └── execution/        # capabilities, plans, runtime adapters
├── domains/
│   └── geoscience/
│       ├── ontology/     # private registries/rules
│       ├── geology/
│       ├── petrophysics/
│       ├── rock_physics/
│       ├── reservoir/
│       ├── geomechanics/
│       ├── geochemistry/
│       ├── geophysics/
│       ├── production/
│       └── wells/
├── planning/             # agents, goals, plans, policies
└── platform/             # persistence, API, auth, jobs, deployment
```

The private ontology and planning layers are not candidates for public mirroring.

## 6. Proposed future public reference architecture

Design only:

```text
src/geoworld_open/
├── world/
│   ├── core.py           # minimal identity/evidence contracts
│   ├── spatial.py        # frames, support, representation descriptors
│   ├── state.py          # immutable state and Field bindings
│   ├── epistemics.py     # observation/estimate/belief distinctions
│   └── provenance.py
├── physics/
│   └── contracts.py      # model/law/condition/validity interfaces only
├── execution/
│   ├── capabilities.py
│   ├── plan.py
│   └── random.py
├── domains/
│   └── geoscience/
│       ├── entities.py   # minimal Formation/Fault/Well/FluidMaterial set
│       ├── geology/
│       ├── petrophysics/
│       ├── rock_physics/
│       └── geophysics/
├── specs/                # World/State/Observation/Experiment and GeoSpec facade
├── artifacts/
└── visualization/
```

Avoid one file per abstract concept. Begin with cohesive modules and split only
when real implementations create pressure. No external graph, ontology, workflow,
agent, or physics framework is required initially.

## 7. Recommended migration sequence

No step begins until this design is approved.

1. **Architecture decisions and semantic tests.** Record ADRs for identity,
   representation, state, observations, specs, and public/private boundaries.
   Gate: three cross-industry metadata-only cases use the same contracts.
2. **Minimal public kernel prototype.** Implement only core identity/evidence
   schemas and reference integrity. Gate: no xarray or geoscience dependency in core.
3. **Spatial and Field representation adapter.** Add frames, supports, transforms,
   Scale, and an xarray-backed public representation. Gate: entity identity survives
   two representations/frames and state changes.
4. **Epistemic separation.** Implement Observation, Interpretation reference,
   EstimatedState, and an ensemble Belief representation. Gate: observed and
   estimated samples cannot be confused or overwritten.
5. **Phase 2 integration branch.** Combine the preserved Phase 2 history with the
   approved kernel without rebasing it; adapt structural outputs into geoscience
   entities, Field bindings, and representations. Gate: all Phase 2 scientific tests
   plus new semantic tests pass.
6. **Physics and validity contracts.** Add model/law/condition/coupling interfaces,
   not formulas. Gate: simple analytical and external-solver adapters share contracts.
7. **Published rock physics and fluid science.** Resume the former Phase 3 only
   after explicit Field/support/validity semantics exist.
8. **Seismic/AVA and observation models.** Treat synthetic seismic as an Observation
   generated from state, not a state property.
9. **Experiments, multiscale, and uncertainty.** Compile ExperimentSpec into a
   deterministic ExecutionPlan with explicit sensitivity metrics.
10. **Public-safe planning adapter.** Add generic mockable Agent/Goal/Action contracts
    only after deterministic science and epistemic boundaries are stable.
11. **Private compatibility review.** Add private adapters deliberately; do not create
    automatic repository synchronization.
12. **Visualization, positioning, and release audit.** Complete scientific storytelling,
    documentation, license/security, and clean-room review.

## 8. Top architectural risks and mitigations

| Risk | Mitigation |
|---|---|
| Over-abstraction | Require two current use cases before adding a kernel concept; keep cohesive modules |
| Ontology bloat | Put domain classes and rules in domain packages; kernel uses opaque type IDs |
| Semantic/numerical coupling | Entity/Field/Representation/WorldState are distinct contracts |
| Coordinate ambiguity | Require frames, axis semantics, support, transforms, and provenance |
| Observation treated as truth | Separate evidence, interpretation, estimate, belief, and asserted state |
| Physical tensor confused with array | Record physical rank/basis separately from storage dimensions |
| Cross-scale inconsistency | Require Scale and explicit transformation lineage |
| Private ontology leakage | Public allowlist, clean-room records, independent tests, deny-list scans |
| Duplicate public/private runtimes | Share conceptual contracts only for now; use reviewed adapters, no auto-sync |
| Premature dependency coupling | No graph/ontology/agent framework; xarray remains a representation dependency |
| Giant GeoSpec returns | Separate semantic specs from compiled ExecutionPlan; retain facade only for UX |
| Agent bypasses science | Validate actions/plans against schemas, constraints, validity, and provenance |
| Provenance becomes telemetry | Keep scientific derivation separate from private operational monitoring |

## 9. Decision summary

The high-level foundation document is directionally correct, but not every named
concept belongs in one universal kernel. The final design uses a small
identity/evidence kernel, adjacent generic layers, and deep domain packages.

The preserved Phase 2 work remains scientifically useful. Its numerical model,
RNG, geology kernels, tests, and provenance survive; their semantic placement
changes. The DAG becomes execution infrastructure, xarray becomes a Field
representation, and GeoSpec becomes a geoscience facade rather than the world.
