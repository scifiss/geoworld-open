# Browser acceptance correction

The failed run used Streamlit 1.65.0 and Playwright 1.62.0. It timed out before the first screenshot, so no artifact establishes the exact transient focus in that CI run. Its logs identify the missing numeric input, not an exception in the application.

Matched-version offline captures show that the replacement layer editor is accessible, carbonate displays 25%, and `input.gdg-input` remains the valid numeric-input selector. The original journey allowed interaction with an old preview: composer clearing and the presence of a plot do not establish completion of the follow-up preparation. The keyboard helper also sent navigation without checking grid focus or the selected cell.

The correction waits for the actual replacement carbonate value, scopes the editor to its Apply form, verifies canvas focus, checks every keyboard-selected cell and its editability, and verifies the entered percentage before Apply. Fixed sleeps were removed. Execution asserts both carbonate 0.25 and sand 0.22, one submission, and byte-identical CSV/ZIP downloads. Failures now retain screenshot, DOM and focus/selection diagnostics.

The complete offline journey runs at normal and 4× throttled browser CPU speeds in CI. Focused local validation with CI dependencies: **36 passed**, including both browser journeys. No provider or scientific experiment was called; no production UI or numerical algorithm was changed.

Full-page captures cover the original preview, carbonate follow-up, sand edit, narrow layout, completed results, selected fields and downloads. Review found that the fixture had reused an unrelated dashboard image for every field; it now renders clearly labeled eight-cell fixture fields, aligned physical coordinates and truthful shared velocity limits. Wide plots/units and single execution controls are readable. Narrow input tables retain their existing horizontal scrolling; chat remains below the workspace. Conversation history remains a deliberately scrolling panel.

Run the same checks:

```sh
GEOWORLD_BROWSER_TESTS=1 GEOWORLD_BROWSER_ARTIFACTS_DIR=/tmp/workspace-browser python -m pytest -q tests/test_semantic_model_browser.py tests/test_studio_scientific_workspace.py tests/test_studio_assistant.py tests/test_studio_legacy_model.py
```

CI retains `scientific-workspace-browser` artifacts with separate `cpu-1` and `cpu-4` captures. These are offline UI evidence, not an authenticated scientific execution or publication evidence. The original intermittent input timeout was not reproduced in the initial matched-version local runs; the correction closes the observed readiness/focus gaps without changing the selector or hiding failures with delays.
