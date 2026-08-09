# Scientific Scope

GeoWorld Open demonstrates how typed inputs, deterministic operators, and provenance can make a synthetic geoscience workflow inspectable.

## Included approximations

1. Layers are piecewise constant and are displaced by optional analytic fold and fault surfaces.
2. Porosity, saturation, Vp, Vs, and density are explicit scenario values; no hidden lithology recipe is used.
3. The optional CO2 example is an ellipse clipped to a named layer. Its elastic multipliers are explicit inputs.
4. Acoustic impedance is `Vp * density`.
5. Normal reflectivity uses the adjacent-sample impedance contrast.
6. Synthetic response is vertical convolution with a normalized Ricker wavelet.
7. Angle reflectivity uses a three-term linearized Aki-Richards approximation, followed by the same wavelet convolution and arithmetic angle-band averaging.

These are educational forward-modeling approximations. Every example states its assumptions in YAML and repeats them in the generated report.

## Excluded science

The repository does not perform rock-physics calibration, Gassmann fluid substitution, anisotropy, attenuation, multiples, wave-equation modeling, depth-to-time conversion, inversion, uncertainty analysis, flow simulation, geomechanics, history matching, or field-data conditioning.

Production algorithms, calibrated recipes, accumulated geoscience knowledge, and evaluation methods are outside the open-core boundary.

