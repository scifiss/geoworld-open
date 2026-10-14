# Reusable capability development: bounded first gate

This is an offline foundation, not autonomous software generation or a new
Studio route. No endpoint, package installer, live source editing, deployment
or generated-code execution is introduced.

## Architecture audit and selected authorities

| Existing implementation | Reused authority |
|---|---|
| `standard/capabilities.py` | Frozen `CapabilitySpec`, unit/dimension/dtype declarations, validity domain, xarray plugin protocol |
| `sdk/registry.py` | Versioned installed-plugin registration and discovery |
| `engine/contracts.py` | Existing execution metadata, context and result contracts |
| `engine/plan.py` | Existing dependency ordering and exact interface compatibility checks |
| `conformance/suite.py` | Existing output, reproducibility, input nonmutation, World and artifact checks |
| `world/models.py`, structural transitions | Eight kernel concepts, immutable records and state-bound input/content verification |
| Gate 3 structural / Gate 4 flagship integration | Real representation-backed geometry, state lineage and existing numerical fixtures |

There is no additional registry or compiler. `sdk/development.py` bridges the
public plugin declarations to the existing execution metadata and compiler.
Its assessment is exact typed interface discovery, not semantic intent routing
or scientific applicability admission. Production decisions remain private.

| Outcome | Required evidence | Next step |
|---|---|---|
| `execute_existing` | Exact registered operation/version, compatible supplied interfaces | Existing applicability, ownership, provenance and resource gates |
| `compose_existing` | Unique compatible producers explicitly permitted by the request; acyclic plan | Existing compiler and admission gates |
| `development_required` | Identified absent operation, no unresolved questions or unreviewed scientific constraints | Reviewed development plan; explicitly invoked generator proposal |
| `clarification_required` | Missing data, ambiguity, unknown units/dimensions, unavailable version, unsupported constraints or cycle | Resolve context; do not generate a substitute scenario |

Inputs are declared interfaces, not proof that real data exist or are eligible.
Missing data cannot trigger an unrequested synthetic/source generator. Dependency
authorization is explicit in `permitted_dependencies`. A discovery receipt never
authorizes execution. Existing private admission gates remain necessary.

## Changed-module responsibilities

* `standard/development.py`: request, assessment, plan, candidate manifest,
  verification report and provider-neutral generator protocol.
* `sdk/development.py`: read-only exact interface discovery and plugin/execution
  adapter. Trusted installed plugins only; this is not a sandbox.
* `sdk/verification.py`: bind receipts to exact request, source manifest and
  acceptance criteria. Evidence authenticity still requires a reviewed verifier.
* `reference/spatial.py`: transparent geometric predicates, without geology roles.
* `domains/geoscience/relationships.py`: role validation, supported semantic
  assignment and content-bound World evidence. Unsealed caller geometry is rejected;
  an evidence reference or caller-generated geometry hash cannot establish shape.
* Structural and flagship `relationships.py`: verify immutable bundles and
  compiled inputs, extract supported geometries, bind them to exact entities and
  WorldState lineage, and preserve compatible relation IDs.
* Flagship integration/artifacts: replace unconditional relation insertion and
  persist the additional evidence without changing numerical operators.

These are public standards/SDK and minimal reference science. Production
intelligence, code-generation policy and differentiated scientific operators
remain private. Public code imports no private implementation.

## Geometric and scientific support

Regions are unions of closed, occupied cells on bounded regular depth/x grids.
Membership denotes entire cells, not inferred subcell geological boundaries.
Curves are explicit piecewise-linear paths in a named local x/depth-down frame.
Only metres/kilometres are converted; incompatible frames abstain. No implicit
map projection, coordinate transform or 3D topology is supplied.

Slab clipping gives curve/cell intervals. Interior tests use the complete cell
union, so artificial internal grid seams do not break a well trajectory.
Boundary contact supports INTERSECTS with zero uncertainty, but not PENETRATES.
Interior length is nominal path length on the declared support. A robust interior
sample outside the tolerance/approximation band establishes penetration;
uncertain boundary-only contact is indeterminate. Disjoint paths are absent.

Containment requires nonempty child support and full occupied-cell area coverage.
Cross-resolution coverage uses relative rounding tolerance `1e-12`, zero absolute
area tolerance. A nonzero geometric tolerance cannot manufacture missing PART_OF
membership. PART_OF additionally requires the explicitly authored parent role;
geometry alone is insufficient. Wells and faults also require registered typed
Entities; arbitrary shape overlap does not invent geological roles.

The structural adapter requires the bundle's exact versioned Representation to
match the immutable World record, rechecks its content hash, state FieldBindings,
regular-grid Support, ReferenceFrame, provenance method, and the exact compiled
input hash. Formation geometry is reconstructed from `layer_index` and its
explicit `formation:<id>` mapping. `reservoir_selection` is checked against the
compiled reservoir-role lookup; the flagship adapter accepts it as the named
ReservoirRegion geometry only when it isolates the ReservoirRegion's explicitly
authored Formation. Otherwise that geometry is `unknown` and its relationship is
indeterminate. The flagship well curve is checked against the exact CSV bytes,
version, well Entity, CURVE Support, frame, compiled input, and derivation record.

Only these source adapters attach nonserialized verification context. That
context is not itself authority: before evaluating predicates,
`derive_relationships()` reruns the source adapter's extraction and compares the
resulting geometry, exact Representation records, entity, state, and authored
PART_OF target. Calling the internal context-attachment helper with arbitrary
geometry does not pass this re-derivation check. Changing geometry, evidence,
entity, relation state, or Representation identity invalidates verification.
State compatibility follows parent-state and provenance lineage; it does not
require every legitimate derived Representation to be a direct member of the
current state. A digest of arbitrary caller geometry is never accepted as
source evidence.

For a single final fault after folds, the defining trace is

```text
z(x) = reference_depth + (x - fault_x) * tan(dip) / dip_direction
       + sum(fold_amplitude * sin(fold_phase(x)))
```

The linear interpolation error bound is
`sum(abs(amplitude) * (2*pi/wavelength)^2) * dx^2 / 8`.
The existing structural input permits dip below 89 degrees, not vertical faults.
Generic explicit vertical polylines are supported. Earlier faults or subsequent
deformations need a surface-advection operator not currently represented and
are indeterminate. Displaced-side `fault_selection` masks are never substituted
for surfaces.

Reference limits: 131,072 cells per region, 4,097 curve vertices and 2,000,000
cell visits per query. Nonfinite/overflowing coordinates, areas, lengths and
combined uncertainty are rejected. These are bounded reference operations,
not optimized production computational geometry.

## Identity, evidence and compatibility

Relations are issued only for positive assessments. Absent and indeterminate
assessments remain in canonical, content-hashed TABLE evidence. It records exact
source geometries, frame/unit/tolerance/grid information and Representation
versions. Provenance connects the state, Entities and source Representations to
the evidence and supported Relations. A source reference alone is insufficient:
geometry must have been extracted from or independently derived from the
content-verified source through the trusted adapter. No new WorldState or kernel
concept is introduced by semantic enrichment.

Input Worlds/bundles are unchanged; reapplying the same derivation returns the
same immutable records with no duplicates. Conflicting existing IDs fail closed.
The flagship's five historical relation IDs remain unchanged for the supported
example. Its one additional TABLE Representation and JSON artifact are deliberate
additive changes. Pressure, temperature, structural arrays, synthetic observation,
state lineage and existing artifact names remain compatible. The manifest and
World hashes change because actual relationship evidence is now included.

## Verification and future generation boundary

Development plans preserve original acceptance criteria and require unit,
integration, regression, negative, scientific and conformance checks. Scientific
verification must include an independently justified analytical, metamorphic or
reviewed-reference expectation; import success and authored assertions alone
cannot produce a verified report. Hash-bound receipts do not authenticate their
own author or execute their evidence. A `verified` receipt remains ineligible
for execution/registration pending trusted review.

Candidate manifests require relative source paths, file hashes, interfaces,
version, license and generator attribution. License text is recorded, not proof
of commercial eligibility. Execution eligibility and authorization are literal
false; the private execution entry point denies before import. This gate has no
isolated process/filesystem/network runner. The next bounded gate is a reviewed
offline isolation/verifier implementation with external reference expectations,
source/license admission and human-controlled versioned registration.

## Offline verification

See `capability-foundation-verification.md` for exact commands/results. New tests
use independent rectangles/lines, analytical lengths, grid refinement,
translation and unit conversion; varied valid fault dips/directions, shallow
wells, expanded reservoir support, uncertainty and unsupported surface history.
They cover exact discovery, permitted composition through the existing compiler,
ambiguity/cycles, source receipts, candidate denial, conformance, immutability,
stable identities, semantic artifact integrity and private-import boundaries.
