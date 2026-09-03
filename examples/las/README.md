# LAS Quicklook samples

These synthetic CWLS LAS 2.0 files exercise GeoWorld Studio's measured-depth
quicklook workflow without containing field, customer, private, or licensed data.
They are illustrative reference data rather than calibrated field models.

- `gw_demo_01_layered.las` represents `GW-DEMO-01` from 1800–2300 m MD.
- `gw_demo_02_layered.las` represents `GW-DEMO-02` from 1810–2310 m MD.

Each contains 201 samples at 2.5 m spacing and 11 curves, including VP, VS,
RHOB, GR, deep resistivity, water saturation, effective porosity, NPHI, DT,
and DTS. Both wells cross the same five-part shale–sand–shale–sand–shale
stratigraphic order, but their formation thicknesses differ:

| Well | Upper shale | High-porosity sand | Middle shale | Cemented sand | Lower shale |
| --- | ---: | ---: | ---: | ---: | ---: |
| `GW-DEMO-01` | 75 m | 80 m | 80 m | 95 m | 170 m |
| `GW-DEMO-02` | 55 m | 105 m | 80 m | 65 m | 195 m |

In GeoWorld Studio, open **LAS Quicklook**, download both samples, upload them,
select `union`, display depth in `m`, and try curves such as
`GR, VP, VS, RHOB, RESD, SW, PHIE`. The protected backend remains authoritative
for parsing, unit handling, QC, and plots.

The present files are measured-depth examples. They do not yet encode distinct
wellhead elevations, deviation surveys, TVD/TVDSS conversion, or coordinates tied
to a shared 3D geological world.
