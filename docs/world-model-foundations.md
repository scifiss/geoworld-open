# World-Model Foundations

> **Current status:** This document records the cross-domain reasoning that led
> to the World Kernel. Some sections preserve early candidate architectures for
> design history. The implemented minimal kernel is the frozen eight-concept
> model: **World, Entity, Relation, Representation, Field, WorldState,
> Observation, and Provenance**. Concepts such as Component, Process, Action,
> Agent, Goal, Constraint, Uncertainty, ReferenceFrame, and Scale are layered or
> adjacent concepts, not members of the minimal kernel. See the authoritative
> [World Kernel architecture](world-kernel-architecture.md),
> [implemented contracts](world-kernel-contracts.md), and
> [Gate-1 decision record](world-kernel-gate-1.md).

## Why this document exists

GeoWorld should not be defined by one workflow such as AVO, CO2 monitoring, seismic modeling, petrophysics, reservoir simulation, geomechanics, or geochemistry. Those are domain capabilities that operate on a deeper representation of a physical world.

The goal of this document is to capture the small set of architectural ideas that recur across subsurface modeling, embodied AI, autonomous driving, robotics, medicine, and simulation. The design principle is simple:

> **Make the kernel general; make the domain deep.**

GeoWorld is the first and deepest domain implementation. The public architecture may expose the general concepts, while detailed geoscience ontologies, applicability rules, calibrated relationships, inference policies, and product intelligence remain private.

---

## Lessons from neighboring world-model traditions

### Subsurface modeling: identity is not representation

Industry subsurface standards such as RESQML distinguish the physical or conceptual **feature** from a human **interpretation**, a computational/geometric **representation**, and properties attached to that representation.

This distinction is fundamental. A fault is not its triangulated surface. A formation is not its grid. A reservoir is not its porosity array. One physical or conceptual entity may have several interpretations and several numerical representations.

This motivates persistent semantic identity independent of meshes, grids, arrays, and observations.

### Medical information systems: observation is not the subject

Healthcare standards such as FHIR explicitly distinguish a patient, condition, procedure, device, or body structure from an **Observation** made about that subject.

The same principle is essential for GeoWorld:

- a formation property is not the same thing as a well-log measurement;
- an observation is not automatically ground truth;
- an inverted property is an estimate or interpretation, not the physical entity itself.

### Robotics and autonomous driving: worlds support interaction

Robotics and autonomous-driving simulators reconstruct or represent geometry, materials, actors, dynamics, and sensors so an agent can act in the world and observe the consequences.

A useful world model therefore needs more than static geometry. It needs:

- state,
- observations,
- processes/dynamics,
- actions,
- representations,
- and a perception-action loop.

### Learned world models: predict consequences, not just pixels

Modern AI world-model research increasingly emphasizes prediction of future state or future observations conditioned on actions. Some systems use explicit geometry and physics; others use learned latent states; many combine explicit simulation with learned models.

GeoWorld should be compatible with both:

1. **explicit scientific state** for interpretability, provenance, and physical reasoning;
2. **learned latent state** for data-driven prediction, approximation, and planning.

The architecture should not force a choice between them.

---

## Historical candidate kernel explored before Gate 1

The world itself should be conceptually smaller than any domain built on top of it.

Before Gate 1, the design exploration considered this broader candidate:

```text
World
├── Entity
├── Component
├── Relation
├── State
├── Field
├── Observation
├── Representation
├── Process
├── Action
├── Agent
└── Goal
```

Cross-cutting concepts include:

```text
Time
Uncertainty
Provenance
Interpretation
Constraint
ReferenceFrame
Scale
```

This was a **conceptual classification tree**, not the implemented kernel. Its
cross-domain reasoning is retained below as design history. Gate 1 subsequently
froze the smaller implemented kernel:

```text
World
├── Entity
├── Relation
├── Representation
├── Field
├── WorldState
├── Observation
└── Provenance
```

The instantiated World remains a graph because real entities have many-to-many
relationships. The other explored concepts below belong in supporting contracts,
domain layers, execution systems, or future applications when justified.

---

## Entity

An **Entity** has persistent semantic identity.

Examples:

| Domain | Entities |
|---|---|
| Geoscience | Formation, Fault, Horizon, Well, ReservoirRegion |
| Medicine | Patient, Organ, Tumor, Device |
| Autonomous driving | Vehicle, Pedestrian, RoadSegment |
| Robotics | Robot, Tool, Container, WorkspaceObject |

Identity persists even when geometry, state, observations, or representations change.

---

## Component (historical layered concept)

Use composition rather than a deep inheritance tree.

An entity can carry zero or more components such as:

```text
Geometry
Material
Thermodynamics
Kinematics
Mechanics
Composition
Transport
```

A geoscience domain can add:

```text
Petrophysics
Reservoir
Geomechanics
Geochemistry
Production
```

Not every entity has every component. A fault and a fluid share identity semantics but should not be forced into the same physical-property schema.

---

## Relation

The instantiated world is a typed graph.

Generic relations may include:

```text
part_of
contains
occupies
contacts
intersects
connected_to
bounded_by
derived_from
observes
acts_on
```

Examples:

```text
Fault F1 INTERSECTS Formation A
CO2 OCCUPIES Reservoir A
Well W1 PENETRATES Formation A
Tumor T PART_OF Liver
RobotHand CONTACTS Cup
Vehicle A FOLLOWS Vehicle B
```

Domain-specific relation types and validity rules belong to domain packages, not the universal kernel.

---

## WorldState

A **WorldState** describes the condition of the world at a particular time or valid interval.

```text
WorldState(t)
    ↓
Process / Action
    ↓
WorldState(t + Δt)
```

Examples of state variables include reservoir pressure, fluid saturation, fault stress, patient blood pressure, tumor size, vehicle velocity, or robot joint configuration.

Persistent entity identity is separate from state. The same formation or vehicle exists across many states.

---

## Field

A **Field** is a numerical quantity defined over a spatial, temporal, categorical, ensemble, or other coordinate domain.

A Field is not an Entity.

```text
Formation_A
├── porosity(z, x)
├── permeability(z, x)
├── pressure(t, z, x)
└── stress(t, z, x, i, j)
```

This distinction allows semantic objects to reference numerical representations such as xarray datasets, meshes, grids, graphs, point sets, and tensors without becoming those representations.

---

## Observation

An **Observation** is partial evidence about a world state.

```text
Observation
├── subject
├── modality / sensor
├── time
├── coordinates / support
├── uncertainty
└── data / representation
```

GeoWorld examples include seismic, well logs, DAS, core measurements, pressure gauges, production measurements, and remote sensing.

A crucial distinction is:

```text
physical state ≠ observation ≠ inferred state
```

This enables forward modeling, inversion, data assimilation, uncertainty, and alternative interpretations without confusing measurements with reality.

---

## Representation

One entity or state may have many computational representations.

```text
Fault F1
├── semantic identity
├── polyline representation
├── triangulated-surface representation
├── voxel representation
└── simulator-grid representation
```

Likewise, a physical object in medicine or robotics may be represented by an image, segmentation, mesh, point cloud, grid, learned embedding, or finite-element model.

Representation should therefore be explicit and replaceable.

---

## Process (historical layered concept)

A **Process** describes dynamics or physics that evolve state.

Examples:

| Domain | Processes |
|---|---|
| Geoscience | Fluid flow, wave propagation, elastic deformation, chemical reaction |
| Medicine | Blood flow, electrical conduction, growth |
| Autonomous driving | Vehicle and pedestrian dynamics |
| Robotics | Rigid-body dynamics, contact, grasp dynamics |

A process may be implemented by an analytical equation, PDE solver, numerical simulator, surrogate model, learned world model, or external service.

An execution or domain layer should care about the contract and semantics, not
the implementation technique. `Process` is not one of the frozen kernel concepts.

---

## Action (historical layered concept)

An **Action** is an intervention that may alter world state.

Examples:

```text
Geoscience: inject, produce, drill, stimulate
Medicine: administer_drug, perform_procedure
Vehicle: accelerate, brake, steer
Robot: grasp, push, move
```

This changes the question from only:

> What exists?

into:

> What will happen if I do X?

---

## Agent and Goal (historical adjacent concepts)

An agent should sit on top of the world, not define the world.

The core loop is:

```text
Agent
    perceives
Observation

Agent
    maintains
Belief / EstimatedState

Agent
    has
Goal

Agent
    chooses
Action

Action
    affects
WorldState
```

Or as a closed loop:

```text
                ┌──────────── WORLD ────────────┐
                │                               │
        WorldState ── Process/Action ──> New WorldState
                │                               │
                └──────── Observation ──────────┘
                              │
                              v
                            Agent
                       /       |       \
                 Belief      Goal     Policy
                              |
                            Action
                              |
                              └───────────────> WORLD
```

This structure is intentionally independent of whether the agent is an LLM, planner, robot controller, human scientist, reinforcement-learning policy, optimizer, or hybrid system.

---

## Explicit, inferred, and learned state

A scientific world system should support several epistemic layers rather than pretending all state is known exactly.

```text
Physical / hypothetical WorldState
        │
        ↓ observation model
Observation
        │
        ↓ inference / interpretation
BeliefState / EstimatedState
```

A learned latent world model may coexist with the explicit state:

```text
ExplicitState ───────┐
                    ├──> learned representation z_t
Observations ───────┘
                             + Action
                                ↓
                         predicted z_(t+1)
```

Explicit state provides scientific semantics and provenance. Learned state can provide approximation, prediction, data fusion, and planning.

---

## Geoscience as the first deep domain

The universal kernel should not know the detailed meaning of a fault, reservoir, completion, mineral reaction, or AVO attribute.

Those belong in domain modules:

```text
domains/
└── geoscience/
    ├── geology/
    ├── petrophysics/
    ├── rock_physics/
    ├── reservoir/
    ├── geomechanics/
    ├── geochemistry/
    ├── geophysics/
    ├── production/
    └── wells/
```

A later extraction into a broader cross-industry package is possible only if real applications demonstrate that the kernel abstractions remain useful outside geoscience.

Design general; implement geoscience first.

---

## Public / private boundary

The architecture itself is valuable evidence of system-design skill and may be public.

### Appropriate for GeoWorld Open

- Entity identity concept
- WorldState concept
- Field concept
- Relation concept
- Observation concept
- Representation concept
- optional Process and Action interfaces outside the minimal kernel
- optional Agent/Goal interfaces outside the minimal kernel
- a small reference set of geoscience entities such as Formation, Fault, FluidMaterial, and Well
- standard published physics operators
- transparent examples and reproducibility

### Keep in private GeoWorld

- full geoscience ontology and property registry
- domain-specific relationship rules
- ontology resolution and aliases
- automatic property inference
- applicability rules
- automatic workflow planning
- accumulated geoscience knowledge
- calibrated defaults and priors
- proprietary scientific operators
- cross-domain coupling intelligence
- production prompts, RAG, memory, evaluations, routing, and operational infrastructure

The design rule is:

> **Expose the architecture. Protect the intelligence.**

---

## Design principles

1. **Identity is not representation.**
2. **Observation is not reality.**
3. **A field is not an entity.**
4. **Use composition over deep inheritance.**
5. **Use a graph for instantiated relationships, not a universal object tree.**
6. **World state is separate from the agent.**
7. **Processes describe evolution; actions describe intervention.**
8. **Explicit and learned world models should be able to coexist.**
9. **Uncertainty and provenance are first-class.**
10. **Keep the kernel small and move scientific meaning into domains.**
11. **Design general; implement geoscience first.**
12. **Expose concepts publicly; keep accumulated scientific intelligence private.**

---

## References and conceptual precedents

- Energistics RESQML — feature / interpretation / representation / property knowledge hierarchy.
- World Labs — functional taxonomy of world models, including state, observation, action, simulation, rendering, and planning.
- HL7 FHIR — typed resources and explicit separation of observations from subjects and clinical entities.
- Waabi World — digital-twin reconstruction, sensor simulation, scenario generation, and closed-loop autonomous-driving evaluation.
- Google DeepMind Genie — learned interactive world simulation conditioned by actions.
- NVIDIA Cosmos — world foundation models for physical reasoning, simulation, and action.

These systems are not identical and should not be imitated mechanically. Their shared patterns motivate the small kernel above.
