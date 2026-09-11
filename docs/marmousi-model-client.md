# Marmousi model exploration client

The local Studio **Marmousi models** workspace talks to an authenticated backend;
it does not import private GeoWorld or ship benchmark binaries. Install the
`demo` extra for Streamlit/Plotly. The backend administrator configures datasets.

Service contracts:

- `GET /references/compute`: backend CUDA availability, full-reference admission
  estimate and explanation. This probes the backend, not the browser's GPU.
- `POST /references/preview`: optional `device: cpu|cuda` (default CPU), bound
  to preparation. Changing device requires re-preparation. Device is reported
  separately from the unchanged numerical reference definition.
- `POST /models/marmousi/interpret`: `{prompt, project_id?}` → typed selection,
  unresolved questions and actual LLM attribution; never solver execution.
- `POST /models/marmousi/preview`: `{selection, project_id?}` → bounded preview,
  native crop coordinates, property units, assumptions and source provenance.
- `POST /jobs`, `mode_hint=marmousi_model`, `marmousi_model={selection, project_id?}`:
  save the reviewed model preview through the existing job/artifact/trace system.

Example selection:

```json
{
  "dataset": "marmousi2",
  "crop": {"x_start_m": 4000, "x_stop_m": 10000, "z_start_m": 500, "z_stop_m": 3000},
  "overrides": {"porosity_fraction": 0.2},
  "display_property": "density"
}
```

Marmousi models are loaded, not invented. A crop preserves physical coordinates
and native spacing; preview display sampling is not solver resampling. Uniform
overrides are hypothetical assumptions over the crop. Neither benchmark supplies
porosity. Editing/cropping is not unchanged-reference reproduction and this
workspace does not run RTM, elastic modeling, FWI or fluid substitution.

Authentication and project access are enforced by the backend. Only installed,
named datasets are selectable; no arbitrary filesystem paths are accepted.
The local-only capability remains unavailable on the hosted Render backend.

## RTM job progress

`GET /jobs/{job_id}` may include typed `progress_detail`: completed/total RTM
batches, execution phase, elapsed seconds, timestamp and optional ETA for
remaining batches. Old servers/jobs remain compatible when this field is absent.
Studio never derives a work percentage from polling time. Batch completion is
not job completion: final update, artifacts and validation may still be running.
The API's terminal `succeeded`/`failed` status remains authoritative.
