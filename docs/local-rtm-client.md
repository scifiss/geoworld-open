# Experimental Model + RTM client

This is a portable HTTP/UI contract, not a public numerical implementation.
It requires an explicitly enabled local private GeoWorld backend. Do not enable
the heavy numerical workflow on the production Render services.

The Studio selector is visible only with `GEOWORLD_STUDIO_LOCAL_RTM=1` and a
loopback `GEOWORLD_BACKEND_URL`. Existing Ask/Build and LAS behavior is unchanged.

Authenticated `POST /rtm/preview` accepts exactly one of `prompt` or `experiment`.
The canonical public types live in `geoworld_open.client.rtm`. The experiment
wraps an existing GeoSpec payload, SI acoustic acquisition and bounded imaging
settings. It does not add a concept to the frozen World Kernel.

`POST /jobs` accepts `mode_hint="model_rtm"`, `rtm_experiment`, and an optional
server-issued `rtm_preparation_id`. Prepared LLM attribution is bound server-side
to the user, prompt and exact experiment. Structured-input runs are distinctly
labeled and must not be advertised as successful LLM interpretation.

Job progress is actual worker stage text. Existing owned job/artifact endpoints
return the result, raw arrays, input experiment, trace, manifest and diagnostics.
Model + RTM shows true/migration velocities, a genuine time-domain shot and one
Born-adjoint image. No optimized velocity, elastic AVO or converged LSRTM claim
is made. A prior result loaded manually says **Replay of recorded run**.

No torch/deepwave dependency, private prompts, provider credentials or private
package imports are introduced into this public client.
