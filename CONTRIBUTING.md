# Contributing

Contributions should preserve the bounded, transparent nature of GeoWorld Open.

1. Create an issue that states the scientific purpose and assumptions.
2. Keep scenario parameters explicit and avoid opaque lithology defaults or hidden calibration.
3. Add focused tests for equations, shapes, finite values, determinism, and invalid input.
4. Do not contribute private datasets, production GeoWorld code, proprietary algorithms, credentials, generated run directories, or unreviewed binary artifacts.
5. Run:

   ```bash
   python -m pytest -q
   python scripts/scan_secrets.py
   python -m compileall -q src apps scripts tests
   ```

6. Document scientific limitations and the derivation of any equation or example.

By submitting a contribution, you agree that it is licensed under Apache-2.0 and that you have the right to provide it.

