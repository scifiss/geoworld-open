# Capability foundation: local review evidence

Tested on 2026-10-13 with Python 3.11.16 / NumPy 1.26.4 in existing local
environments. No downloads, provider calls, GPU jobs or browser recording were
performed. Streamlit, API routing and numerical operators were not modified.

Both isolated worktrees use branch `feat/capability-development-foundation`.
There are **no new commits** and no push/merge/deployment:

| Worktree | Starting main commit |
|---|---|
| `geoworld-open-capability-foundation` | `40243d2acb2af0a7cbdabbeeb303c31bd2b66a5f` |
| `geoworld-capability-foundation` | `032aec8e79b4042ceef8f48b05bb10ec6e16d9b5` |

Original worktrees and unrelated publication changes are untouched.

## Commands and results

Commands below run from the public worktree; the Python executable belongs to
the existing private environment, while `PYTHONPATH=src` selects only this public
implementation. Standard-library/unit/reference tests do not require the private
product or optional scientific kernels.

```bash
PYTHONPATH=src MPLCONFIGDIR=/tmp/geoworld-mpl \
  ../geoworld/.venv/bin/python -m pytest -q \
  tests/test_spatial_relationships.py tests/test_capability_development.py \
  tests/test_flagship_world.py tests/test_flagship_artifacts.py \
  tests/test_conformance_sdk.py tests/test_open_core_boundary.py --tb=short
```

Final focused result: **64 passed in 19.68 s**. This includes plugin conformance,
World conformance, unchanged flagship behavior, negative geometry, exact source
receipts, semantic artifact tampering and public/private import boundaries.

```bash
PYTHONPATH=src MPLCONFIGDIR=/tmp/geoworld-mpl CUDA_VISIBLE_DEVICES='' \
  ../geoworld/.venv/bin/python -m pytest -q \
  -o faulthandler_timeout=60 --tb=short
```

Broader result: **515 passed, 8 skipped in 134.17 s**. Browser acceptance remains
opt-in and was not enabled for this offline/non-UI gate. The final adapter review
added one optional-input/runtime-unit regression after this full run collected
tests. That change was verified by the final 64-test focused suite, rather than
repeating the broad suite. Final development-plan guards also reject unresolved
questions and assessments for an unrelated missing operation. The earlier post-review contract/geometry subset also
passed **34 tests in 2.05 s**. No scientific/execution assertion was removed.

Private exact commands/results are in the matching private review record. Local
API tests need loopback socket permission; a sandbox-restricted focused attempt
was interrupted when it stalled. The rerun with local socket access completed.
There were no external/cloud calls.

Static checks: `python -m compileall -q src apps scripts tests`, `git diff --check`,
and AST parsing of every changed Python file with `feature_version=(3, 10)` pass.
Python 3.10/3.12 CI runtime execution was not performed or claimed.

Secret scan: `../geoworld/.venv/bin/python scripts/scan_secrets.py --all-files`
passes. Both existing source histories pass the current private commercial-source
checker with zero restricted blob/path matches. Public HEAD has 101 reachable
commits / 632 checked blobs; private HEAD has 154 / 1091. These ancestry receipts
cover the starting commits, **not an unpublished future commit**. Changed-file
SHA-256 checks against the existing restricted fingerprint policy also find zero
matches. No data/calibration/model artifacts are added by this change.

## Numerical preservation

`capability-foundation-numerical-check.json` records all 16 hashes. The unmodified
Gate 4 main implementation was run before editing; the new implementation was
run with the identical authored fixture and local environment. For each variable
in `structural_dataset`, `baseline_dataset` and `perturbed_dataset`, the comparison
uses `sha256(np.ascontiguousarray(array.values).tobytes())`. All 16 hashes match
exactly. This is same-environment bitwise evidence, not a portable floating-point
golden across different library/platform versions.

Reproduce the new-side comparison from the public worktree:

```python
from hashlib import sha256
from pathlib import Path
import json
import numpy as np
from geoworld_open.domains.geoscience.flagship import load_flagship_spec, run_flagship_world

r = run_flagship_world(load_flagship_spec('examples/scenarios/flagship_faulted_reservoir.yaml'))
actual = {}
for group in ('structural_dataset', 'baseline_dataset', 'perturbed_dataset'):
    for name, array in getattr(r, group).data_vars.items():
        actual[group + '/' + name] = sha256(np.ascontiguousarray(array.values).tobytes()).hexdigest()
expected = json.loads(Path('docs/capability-foundation-numerical-check.json').read_text())
assert actual == expected['numerical_hashes']
```

World/manifest hashes intentionally change to include geometry assessments and
their provenance. Existing well-observation and pressure/temperature assertions
continue to pass. The prior representation-count assertion now explicitly checks
the original five representations plus exactly one geometry evidence record.

## Changed files

Public contracts/SDK: `standard/development.py`, `sdk/development.py`,
`sdk/verification.py`. Public reference geometry: `reference/spatial.py`.
Domain semantics/adapters: geoscience `relationships.py`, structural
`relationships.py`, flagship `relationships.py`. Integration: flagship
`integration.py`, `artifacts.py`. Tests: `test_spatial_relationships.py`,
`test_capability_development.py`, `test_flagship_world.py`,
`test_flagship_artifacts.py`. Documentation: architecture/review records,
numerical hash receipt and `gate4-flagship-world.md`.

Private changes are limited to `agents/capability_development.py`, its tests and
architecture/review documentation. No scientific production implementation moved
into the public repository.

## Remaining gate

Supported spatial reference is 2D cell unions and explicit polylines. Multiple
fault/later-deformation surfaces abstain; there is no surface advection, 3D
topology or implicit frame transformation. The execution bridge uses canonical
declared NumPy kinds and dictionary context parameters; richer resource/context
bindings need a reviewed adapter.

No trusted candidate sandbox/verifier exists, so execution remains disabled.
No live autonomous development routing is enabled. A reviewed public commit and
compatible private dependency-pin update are required before independent CI
publication; both current production pins are unchanged. The next bounded gate
is isolated offline verification and controlled admission, not deployment.
