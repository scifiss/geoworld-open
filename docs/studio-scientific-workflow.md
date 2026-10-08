# Protected scientific results in the single Assistant

The public client adds bounded `ScientificGoalAction`, scientific experiment context, preview/result receipts, and presentation of protected scientific jobs. These objects describe requests and results and grant no execution permission. Private GeoWorld selects operators, calibrations, applicability and resource policy.

`POST /intent/interpret` accepts the existing `StudioRequest` and may return route `scientific_workflow` with a `ScientificWorkflowPreview`. A ready preview binds a protected preparation ID, selected capability names, plan/input hashes, assumptions, limits and a resource estimate. A public client does not supply server paths or calibration objects.

Submit through the existing `POST /jobs` with `mode_hint="scientific_workflow"`, the preview's exact recorded request and `scientific_preparation_id`. The backend validates ownership and prepared inputs and makes duplicate submissions for the preparation idempotent. Existing job status and protected artifact routes return `ScientificWorkflowResult` and downloadable evidence. The normal single composer invokes this path; no Advanced control is required.

Studio presents an interactive section, selected scientific fields, display scaling, result metrics and Overview / Models & Figures / Scientific Evidence / Provenance / Complete Details. The Assistant is on the left for scientific experiments; narrow layouts place it below results. Plotly selections/zoom use a stable per-job revision. Saved scientific jobs restore their bounded task referent using their actual recorded action, so follow-ups can reuse the existing model. An unrelated Q&A turn retains the scientific workspace.

Scientific selection, composition, resource access, algorithms and calibration remain private. Public code calls only authenticated HTTP interfaces and renders returned arrays/artifacts. It contains no SAGE-AVO dependency, research fixture, applicability rules or scientific orchestration.
