# GeoWorld Open agent rules

Read `docs/public-private-boundary.md` before adding or moving any capability.

## Placement rule

Put code in **geoworld-open** only when it is one of:
- public standard, schema, contract, SDK, client, benchmark, conformance, evaluation, serialization, manifest/provenance verification;
- minimal transparent reference implementation needed to prove the public contract;
- public frontend/client code that calls GeoWorld services over HTTP without importing private source.

Do **not** place differentiated implementation here. Keep private:
- production physics/numerics, calibration, formation- or pressure/temperature-specific logic;
- advanced seismic/rock physics, inversion/UQ;
- heavy 2D/3D/4D rendering, animation/video, GPU/performance implementation;
- private agents, routing/planning policy, prompts, RAG, knowledge mining, accumulated domain knowledge;
- user/project intelligence, production auth/database data, commercial workflows, production configuration/secrets.

## Dependency rule

- Public code must never import the private `geoworld` package.
- Public code may call an official protected GeoWorld capability through a documented HTTP interface.
- Public capabilities must remain independently runnable when the protected service is unavailable.
- The private product may depend on public standards/SDK/contracts.

## Before implementing a new feature

Classify it as one of:
1. PUBLIC_STANDARD
2. PUBLIC_SDK_INFRA
3. PUBLIC_BENCHMARK
4. PUBLIC_REFERENCE
5. PRIVATE_IMPLEMENTATION
6. PRIVATE_INTELLIGENCE
7. DUPLICATED_LEGACY

If classification is 5 or 6, do not implement it here. If uncertain, stop and report the boundary question instead of exposing implementation.

## Scientific authority

`World`, `Entity`, `Relation`, `Representation`, `Field`, `WorldState`, `Observation`, and `Provenance` remain the eight-concept public World Kernel. Do not add a ninth kernel concept without explicit approval.

Public reference science must be textbook/transparent, explicitly bounded, uncalibrated, and clearly labeled as reference behavior rather than production GeoWorld science.

## Rendering

Public may define `RenderSpec`, scene/view/camera/layer/time-sequence contracts, color semantics, benchmark requests, and minimal reference plotting. Production renderer implementation, advanced composition, 3D/4D/video, GPU and optimization remain private.

## Changes

Keep public/private boundaries explicit in code and tests. Do not weaken secret scans, provenance, determinism, or conformance checks. Do not change repository visibility, deployment, licensing, or protected-service behavior unless explicitly requested.