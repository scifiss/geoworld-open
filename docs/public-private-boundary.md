# GeoWorld public/private capability boundary

This file is the canonical placement policy for GeoWorld Open.

## Public repository purpose

`geoworld-open` is the executable public standard, SDK, benchmark, conformance, and reference layer for GeoWorld. It should be technically strong and citeable, but it must not expose differentiated production intelligence.

### Public categories

- **Standards/contracts**: World Kernel, GeoSpec, capability specifications, validity domains, units, transitions, render contracts, artifact/provenance contracts.
- **SDK/infrastructure**: clients, registries, serialization, hashing, loading, verification, manifest/provenance tools.
- **Benchmarks/evaluation**: versioned scenarios, expected/reference outputs where safe, reproducibility/tolerance checks, conformance tests.
- **Minimal reference science**: transparent textbook implementations necessary to make the standard executable. They must be uncalibrated, bounded, and explicitly labeled as reference implementations.
- **Public product surface**: frontend/client code may authenticate and submit jobs to the official private GeoWorld backend over HTTP. It must not import private source.

## Protected private categories

Keep implementation in private `geoworld` when it contains any of:

- production or optimized physics/numerics;
- formation/lithology-specific inference, pressure/temperature corrections, model blending, stabilization, calibration or tuned heuristics;
- advanced rock physics, seismic, Zoeppritz/vendor logic, inversion, UQ;
- fault-damage recipes, advanced deformation/geology, coupled workflows;
- heavy rendering implementation: production 2D composition, 3D volume rendering, 4D/time-lapse video, GPU/performance optimization;
- private agent reasoning/planning/routing, prompts, RAG, knowledge corpus, knowledge mining, private evaluation data;
- user/project intelligence, project knowledge buildup, commercial workflow logic;
- production auth internals, database/user data, secrets, deployment configuration and cost strategy.

Public contracts may describe the required inputs, outputs, units, assumptions, validity domains and render requests for protected capabilities without exposing how the capability is implemented.

## Connection rule

The intended architecture is capability-based:

```text
public GeoWorld UI / SDK
        |
        | HTTP
        v
private GeoWorld backend / protected capabilities
        |
        +--> private reasoning, knowledge, physics, renderer
        |
        +--> outputs conforming to public contracts
```

The reverse code dependency is allowed and preferred for standards:

```text
private geoworld
    -> imports/pins geoworld-open standards, SDK and contracts
```

Never create a Python import from `geoworld-open` into private `geoworld`. Public-to-private access must be through documented HTTP/service contracts so the public repository remains independently installable.

## Current boundary audit baseline

The August 2026 audit classified the existing public scientific code as bounded/reference science. Retain as public references unless materially extended:

- acoustic impedance `Z = Vp * density`;
- explicit layer/property lookup;
- explicit property perturbation;
- analytic folds/planar faults for benchmarks;
- normal reflectivity, Ricker convolution and linearized Aki-Richards reference AVO;
- hydrostatic/gradient fields, Gaussian state perturbation and deterministic observation noise;
- professional but bounded 2D benchmark plotting.

Do not extend those modules toward production-calibrated behavior without a new boundary review.

## New-feature decision test

Before coding, answer:

1. Is this defining **what a compatible GeoWorld capability must accept/return**? -> public.
2. Is this a **benchmark, verifier, SDK or minimal transparent reference**? -> public.
3. Does this encode **how GeoWorld gains performance, scientific specialization, calibration, reasoning quality, knowledge or commercial advantage**? -> private.
4. Does the feature require private source to run? -> redesign behind HTTP or keep it private.
5. Would publishing the implementation reduce commercial or unpublished research advantage? -> private.

When uncertain, default to protecting implementation and expose only the contract.