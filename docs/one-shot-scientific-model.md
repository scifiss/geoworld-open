# One-shot synthetic model figure

[Download the 320 dpi publication PNG](assets/geoworld-three-layer-co2.png).

This composite was exported by a completed private GeoWorld numerical job for:

> build shale sand carbonate, co2 in sand carbonate very porous

The validated GeoSpec used a 300 × 160 cell 2D grid, 10 m horizontal and 5 m
vertical spacing, and seed 7. Its layers are shale (φ=0.08 default), sand
(φ=0.22 default), and carbonate (φ=0.28 high-porosity policy). The existing
localized CO₂ substitution was enabled in sand at saturation 0.65. No fault
was requested.

The numerical job produced 1,619 nonzero saturation cells, all in sand; the
realized maximum is 0.65. Facies codes 0, 1 and 2 correspond to shale, sand and
carbonate. Vp, Vs and density vary in the plume, and the computed reflectivity
and depth-domain synthetic seismic response are nonzero. The composite shows
these actual job arrays plus porosity and acoustic impedance. The plot uses
vertical display scaling for readability while axes retain physical metres.
This is a deterministic synthetic demonstration, not field seismic or inversion.

The production job's artifact inventory retains `summary.png`, nine individual
`scientific_*.png` panels, the original numerical CSV arrays, GeoSpec, scenario,
trace and manifest. Studio offers the composite through **Download publication
figure (PNG)** and the complete artifact inventory under **Complete details**.
Studio runs a validated typed build immediately when its 2D grid has at most
400 × 240 cells and 100,000 cells total, with at most six layers. Explicit
prepare-only, degraded interpretation, unresolved clarification and larger
models retain their review controls. Accepted requests use a session submission
key to prevent a Streamlit rerender from submitting the same job again.
The committed example image is 5165 × 3545 pixels at 320 dpi, SHA-256
`024a12c79b024307fa0570148745592a6f32e2a5787bbc1d3952bee4d2a5cde5`.

The semantic action for this example was validated locally without a cloud
model: no provider credentials were available in the workspace. Live provider
wording robustness remains unverified.
