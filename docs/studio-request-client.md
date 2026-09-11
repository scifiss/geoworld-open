# One-request Studio interface

The default Studio page has one natural-language entry. `interpret_studio(prompt)`
calls authenticated `POST /intent/interpret` and returns a typed `StudioDecision`.
Public code renders the decision; private service intelligence selects the route.
Project-scoped callers may pass `project_id`; authorization precedes inference.

This endpoint does not execute scientific work. Existing preview/validation and
job endpoints remain authoritative. Requests needing unavailable capabilities return
`route="blocked"` with a human-readable explanation. No generic Python/tool execution
or user-supplied filesystem path is part of this contract.

Model/reference workflows pass the original prompt to the existing domain preparer.
The UI displays actual per-call LLM attribution separately from deterministic data
loading/numerical computation. Only an explicit numerical Run button submits a
simulation. Typing, layout changes and export do not resubmit interpretation or jobs.

Marmousi previews show the interpreted dataset, then allow crop/property review.
Manual dataset loading/debugging remains under the optional Advanced tools, not the
primary request flow. Full-waveform inversion and forward-only Studio execution are
not implied by the presence of model previews or an RTM reference.

The bounded generated-model RTM route displays typed Vp, Vs and density grids
before execution. The user must review the plots and check approval before the
Run button is enabled. The constant-density acoustic Deepwave solver uses Vp
only; Vs and density are labeled as context. The client sends the preparation ID,
and the protected service verifies that the executed Vp hash equals the prepared
Vp hash. Editing or re-preparing resets approval. Marmousi crop-to-RTM is not part
of this bounded path yet.

Completed results stay visible across workspace/form edits and are labeled with the
submitted request. **Open saved run** restores an owned completed job using the
existing job and artifact APIs, without running a solver or calling an LLM. HTML
downloads do not trigger a Streamlit rerun; a browser/session restart still requires
sign-in and reopening the backend job. Report contents use the accepted job's request,
not unsent text currently in the editor.
