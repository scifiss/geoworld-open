# Contributing

Contributions should preserve GeoWorld Open's deterministic scientific authority
and explicit semantic contracts.

1. Create an issue that states the scientific purpose and assumptions.
2. Keep scenario parameters explicit; avoid hidden calibration, network calls, or
   required LLM behavior in scientific computation.
3. Preserve typed contracts and the distinctions `Entity != Field`,
   `Entity != Representation`, and `Observation != WorldState` where relevant.
4. Record assumptions, immutable state/Representation lineage, and Provenance for
   new World-centered scientific outputs.
5. Add focused tests for equations, shapes, finite values, determinism, invalid
   input, and reproducible artifacts.
6. Do not contribute private datasets, production GeoWorld code, non-public
   algorithms, credentials, generated runs, or unreviewed binary artifacts.
7. Run:

   ```bash
   python -m pytest -q
   python scripts/scan_secrets.py
   python -m compileall -q src apps scripts tests
   ```

8. Document scientific limitations and the derivation of any equation or example.

By submitting a contribution, you agree that it is licensed under Apache-2.0 and that you have the right to provide it.
