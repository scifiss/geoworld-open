# Gate 4: Flagship World Demonstration

## Purpose and scope

This bounded demonstration shows one real vertical path through the approved
World Kernel. It combines persistent geological identity, numerical Fields,
immutable state lineage, one transparent analytic state change, synthetic
evidence, typed Provenance, and checksummed artifacts.

It is not reservoir simulation, pressure diffusion, field interpretation,
history matching, production forecasting, or calibrated subsurface physics.

## Authority flow

```text
FlagshipSpec YAML
  -> immutable CompiledFlagshipInput
       -> embedded immutable CompiledStructuralInput
       -> canonical JSON + exact content hash
  -> Gate 3 structural World and structural state
  -> explicit flagship semantic bootstrap
  -> baseline pressure/temperature transition
  -> analytic pressure-perturbation transition
  -> synthetic well-pressure Observation
  -> Representation-backed artifacts and checksums
```

The exact flagship input includes every structural, ReservoirRegion, Well,
baseline, perturbation, observation, noise, and output value. Before either
state transition computes numerical values, its canonical hash must match
`representation:flagship-input@v1` registered in the World. A separately
modified post-bootstrap input is rejected.

## Persistent semantic objects

The example creates three Formation Entities, one Fault, one Fold,
`reservoir-region:r1`, and `well:w1`. The ReservoirRegion is not
`reservoir_selection`: the former is a persistent Entity; the latter is a
Boolean Field. Likewise, the Well is not its trajectory Representation, and
the Fault is not `fault_selection`.

The explicitly authored relations are:

```text
reservoir-region:r1 PART_OF formation:reservoir_sand
well:w1 PENETRATES reservoir-region:r1
well:w1 PENETRATES formation:reservoir_sand
fault:fault_f1 INTERSECTS reservoir-region:r1
fault:fault_f1 INTERSECTS formation:reservoir_sand
```

These are scenario statements. Gate 4 does not implement a general topology
engine.

## State lineage

```text
state:structural-final
  -> state:flagship-baseline       t = 0 days
  -> state:flagship-perturbed      t = 30 days
```

Relative model time indexes synthetic benchmark states. The 30-day label does
not mean a flow equation was integrated for 30 days. Each transition appends a
new state and records; earlier states and Entity IDs remain unchanged.

## Baseline benchmarks

Pressure is finite only where `reservoir_selection` is true:

```text
p0(z) = p_ref + rho_ref * g * (z - z_ref)
```

All parameters are explicit SI inputs. This is illustrative hydrostatic
pressure, not calibrated formation pressure.

Temperature is:

```text
T0(z) = T_ref + G * (z - z_ref)
```

This is an illustrative linear geothermal-gradient Field. No heat transport is
modeled.

## Analytic pressure change

```text
delta_p(x,z) = delta_p_max * exp(
    -0.5 * (((x-xc)/sigma_x)^2 + ((z-zc)/sigma_z)^2)
) * reservoir_selection(x,z)

p1(x,z) = p0(x,z) + delta_p(x,z)
```

Every parameter is authored. The change is zero outside the ReservoirRegion.
This benchmark has no permeability, flow equation, diffusion, mass
conservation, relative permeability, or fluid transport.

## Synthetic pressure evidence

The Observation samples `p1` at authored Well depths using nearest-cell
sampling. Explicit Gaussian noise uses the namespace-derived `SeedManager`, an
authored sigma, and an authored seed. Observation remains evidence, not a
WorldState and not ground truth.

```text
Observation
  -> evidence TABLE Representation
  -> observation Provenance
  -> perturbed pressure Representation + Well trajectory
  -> perturbed WorldState
  -> perturbation Provenance
  -> baseline Representation
  -> exact flagship-input Representation
```

## Reproducible artifacts

The run includes exact input JSON, final World and Provenance, compact graph and
state-lineage files, immutable numerical packages, trajectory and Observation
CSV files, assumptions, a correctness diagnostic, and one manifest. Semantic
Representation hashes and ordinary file SHA-256 checksums are independently
verified.

## Run

```bash
geoworld-open flagship-run \
  examples/scenarios/flagship_faulted_reservoir.yaml \
  --output runs/flagship-world
```

The existing `run` and `world-run` commands remain separate and unchanged.
