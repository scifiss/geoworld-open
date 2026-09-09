# Studio layout and saving

These are public presentation/client features. They do not change scientific
calculations, source image artifacts, authentication, or backend configuration.

## Everyday layout

The normal Studio page is responsive; no screenshot mode is needed.

- **Page layout → Auto** (default): request/workflow on the left and results on
  the right when the main content area is wide enough. It stacks on smaller screens.
- **One column**: always puts results below the workflow.
- **Two columns**: prefers side-by-side results at somewhat narrower widths than
  Auto, but still stacks on small screens so inputs and figures remain usable.

These choices are in the sidebar and stay in the current session. Auto measures
the available main area, excluding the sidebar, rather than just the window.
Before a result is available, the workflow uses one column without an empty
results column. Layout changes do not submit a scientific job. Resizing in Auto
is CSS-only and does not rerun the application.

The page uses the available main width with small side margins, instead of a
fixed 1240/1600-pixel cap. Excess bottom padding is removed. If content is shorter
than the browser viewport, the remaining window background is normal; no web
layout can shrink the physical browser window to the content.

### Text, figures, and details

Keep browser zoom at **100%** (`Ctrl+0` in Chrome/Edge on Windows/Linux).
Under **Display settings**, text defaults to **18 px** and **Fit figures to
column** is on. Figures retain their aspect ratio and fill the available column.
Turn fitting off to choose a smaller **Figure width**. This affects display only;
original downloadable images remain unchanged.

For models, review **Prepared model / assumptions** between **Prepare model**
and **Run model**. In **Model & Figures**, expand **Tables & scientific details**
for the layer table and raw scientific summary. They are collapsed initially
to keep the primary workflow compact.

## Save the actual page as PDF

1. Select the results tab and expand the details you want to include.
2. In the sidebar open **Save & export → Save page as PDF**.
3. In the browser's print dialog choose **Save as PDF**. Landscape is suggested
   for scientific plots. Turn off **Headers and footers** to remove the
   browser-added date, URL, title, and page numbers.
4. Save, or cancel. The normal page and buttons remain available afterwards.

Printing excludes the sidebar and Streamlit toolbar. It uses the current
question box and selected results tab, including any unsent edits. Other tabs
remain hidden. Review visible material first: PDF is not a general-purpose
privacy/redaction filter. Expanded technical details may contain sensitive
project information.

The layout adapts to the printable paper width; **One column** remains a
single-column print choice. Long results paginate instead of being cropped to
force them onto one sheet. You can adjust paper size and scale in print preview.
Saving and cancelling do not rerun a scientific job, require screenshot mode,
or leave the interface hidden. The regular browser Print command works too.

## Save a portable HTML report

After a completed run, open **Save & export → Prepare HTML report**, then
**Download HTML report**. Open the downloaded file in a browser.

This is a **formatted offline report, not a clone of the live Studio interface**.
It contains the submitted question, answer, citations, figures, and assumptions.
Unlike PDF, it uses the saved submitted question, not unsent changes in the
editor. Older sessions without that question are labeled explicitly.

The HTML report embeds original raster figure bytes and has no external scripts,
fonts, screenshot service, or network requests. It excludes account details,
credentials, backend URLs, full metadata, and traces. All user-controlled text
is HTML-escaped. It still contains scientific results and questions, so review it
before sharing.

Its own **Page scale**, **Text size**, **Figure width**, and **Print / Save PDF**
controls remain available. Report controls are excluded from printing. This is
a presentation copy, not the authoritative artifact archive; **Artifacts** still
provides individual files and the complete run export.

## Screenshots and slide decks

There is no dedicated screenshot panel or capture mode in the live page now.
Use normal browser/OS screenshot tools if you want a PNG. For a slide, choose
two columns on a wide window, or use **Overview** for a shorter story and place
individual figures from **Artifacts** on separate slides. Do not shrink a long
page until its text becomes unreadable.

Raster plot-axis labels cannot be enlarged independently with Studio's text
slider. Use a wider results column or download the original figure to inspect
small labels.

## Developer verification

Unit tests cover display limits, layout choices, safe HTML escaping, citation
labels, original image bytes, and restricted offline scripting. Streamlit widget
tests check result preservation, submitted-question binding, session cleanup,
fallback confirmation, sidebar-only exports, and no submission on layout changes.

Opt-in Chromium tests run the real app with a fake HTTP client and public
reference figures. They cover Auto/manual layouts, available-width sizing,
narrow screens, native PDF without persistent capture state, hidden sidebar
and inactive tabs during print, multi-page result completeness, and unchanged
image aspect ratios. A PDF reader checks the final figure captions and summary,
and verifies that account details are absent. No live account or model is used.

Studio's demo extra requires Streamlit 1.63+ for trusted static JavaScript via
`st.html`. Only the packaged native-print action uses that opt-in: no prompt,
answer, credential, or result object is interpolated into executable HTML.

```bash
python -m pip install -e '.[demo,dev]' playwright pypdf
python -m playwright install chromium
python -m pytest -q
GEOWORLD_BROWSER_TESTS=1 python -m pytest -q -s tests/test_studio_presentation_browser.py
```

Chromium also needs the operating-system libraries listed by Playwright. Browser
tests are opt-in so SDK-only installations do not require a browser.
