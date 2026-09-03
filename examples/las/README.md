# LAS Quicklook samples

These small synthetic CWLS LAS 2.0 files exercise GeoWorld Studio's measured-depth
quicklook workflow without containing field or customer data.

- `well_alpha_m.las` uses metres, increasing measured depth, and standard curve mnemonics.
- `well_beta_ft_decreasing.las` uses feet, decreasing measured depth, and alternate mnemonics.

In GeoWorld Studio, open **LAS Quicklook**, download both samples, upload them,
select `union` and target unit `m`, and optionally enable deterministic resampling.
The protected backend remains authoritative for parsing, unit handling, QC, and plots.
