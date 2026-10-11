# Shared scientific workspace

Ordinary GeoSpec models and protected scientific experiments use **Model & Inputs**, **Scientific Results**, **Evidence & Data**, and **Advanced**. The single Assistant stays on the right on desktop and below the workspace on narrow screens.

Accepted ordinary requests prepare once. Bounded automatic execution opens completed results; otherwise **Run simulation** submits the reviewed inputs. Lithology, thickness (m), and porosity (%) are committed atomically with **Apply layer edits** and validated by the protected preview API. Baseline Vp, Vs and density remain read-only. Applying changed inputs prepares a new experiment without submitting it; the previous result remains identified and available until the new job completes.

Porosity percentages are display conversions; stored fractions and downloaded bytes are unchanged. Vp/Vs scale comparison appears only when both fields are selected. Selection order controls ordinary panels; the scientific workspace retains its existing explicit reorder controls. Raw specifications are under Advanced.

CSV/NPZ downloads fetch only the selected file. The numerical ZIP includes original CSV/NPZ/JSON/YAML files and a download-byte hash inventory when recorded sizes total at most 32 MiB. Unknown/larger inventories use individual downloads. Preparing downloads or exports does not submit scientific jobs. All retrieval uses existing owner-scoped APIs.

The independent heterogeneous benchmark retains its existing fixed scientific input contract and supported Assistant follow-ups. The ordinary layer editor does not pretend to edit that different numerical operator.

Run deterministic state-transition checks:

```sh
python -m pytest -q tests/test_studio_scientific_workspace.py tests/test_studio_assistant.py tests/test_studio_legacy_model.py tests/test_studio_scientific.py
GEOWORLD_BROWSER_TESTS=1 python -m pytest -q tests/test_semantic_model_browser.py
```

`geoworld_open.workspace_browser` supplies reusable DOM helpers for atomic edits, navigation, selection and settled rerenders. The authenticated private acceptance runner exercises these controls against the normal protected APIs and records full-page screenshots, numerical hashes and cgroup memory. Browser fixtures are separate from real-provider acceptance.

The existing browser CI job runs the deterministic prepared-model journey on every push/PR and retains its screenshots as an artifact; ordinary CI does not call an external provider.

Large tables require horizontal scrolling on narrow screens; the four navigation tabs wrap. ZIP packages deliberately exclude figure files; saved figure/export downloads remain available through their existing result/Advanced controls.
