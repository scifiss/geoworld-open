# Equation Derivations and Provenance

The source in this repository was authored independently for GeoWorld Open. It is not copied from the proprietary GeoWorld implementation. The equations below are standard published approximations and are written in direct NumPy form so their assumptions can be reviewed.

## Ricker wavelet

For peak frequency `f` and centered sample time `t`:

```text
a = (pi f t)^2
w(t) = (1 - 2a) exp(-a)
```

The implementation constructs an odd-length symmetric sample sequence and normalizes peak absolute amplitude to one.

## Normal-incidence reflectivity

With acoustic impedance `Z = rho Vp`, the interface coefficient is:

```text
R = (Z2 - Z1) / (Z2 + Z1)
```

Zero-denominator guards and finite-value conversion are explicit in the operator.

## Linearized Aki-Richards approximation

The public operator uses averages and normalized contrasts across adjacent vertical samples:

```text
intercept = 0.5 (dVp/Vp + dRho/Rho)
gradient  = 0.5 dVp/Vp - 2 (Vs/Vp)^2 (dRho/Rho + 2 dVs/Vs)
curvature = 0.5 dVp/Vp (tan(theta)^2 - sin(theta)^2)
R(theta)  = intercept + gradient sin(theta)^2 + curvature
```

This linearized form is useful for a bounded qualitative example. It is not an exact Zoeppritz solution and is not valid for every contrast or incidence angle.

## References

- Aki, K., and Richards, P. G. (1980). *Quantitative Seismology: Theory and Methods*. W. H. Freeman.
- Ricker, N. (1953). Wavelet contraction, wavelet expansion, and the control of seismic resolution. *Geophysics*, 18(4), 769-792.

The references identify the standard scientific basis; no reference text or software source is reproduced here.

