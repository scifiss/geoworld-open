# Limitations

- Models are 2D synthetic sections with regular Cartesian sampling.
- Layer properties are constant except for an optional explicit elliptical perturbation.
- Fault geometry is planar and fold geometry is sinusoidal.
- The vertical axis is depth but is used as the convolution sample axis; this is not a physical depth-to-time workflow.
- The Aki-Richards calculation is linearized and intended for qualitative demonstrations.
- No field data are loaded, interpreted, calibrated, or inverted.
- No uncertainty, sensitivity, optimization, or ensemble workflow is included.
- Numerical outputs must not be used for drilling, storage assurance, reserves, safety, or other operational decisions.
- The local demo has no authentication or multi-user isolation and should not be exposed as a public service without a separate security design.

The bounded scope is intentional. It keeps the equations, assumptions, and provenance easy to inspect while protecting production-only capabilities.

