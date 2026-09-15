# Local execution contracts and FWI reproduction selections

These contracts are SDK/service evidence, **not World Kernel concepts**. The
eight-concept kernel is unchanged. Resource detection, reserves, planning and
scientific implementation stay in the protected backend.

`geoworld_open.client.execution` defines:

| Contract | Purpose |
| --- | --- |
| ResourceSnapshot | Sanitized backend CPU/RAM/GPU/VRAM/disk availability and timestamp |
| ExecutionPreference | Defaults: auto device, balanced priority, prefer local; optional upper budgets |
| CapabilityResourceProfile | Workload identity and resource/timing evidence supplied by an implementation |
| ExecutionPlan | Resolved device/threads, estimates, reserves, feasibility, scientific mode and reasons |
| ExecutionEstimate | Runtime range, confidence, evidence sources and assumptions |
| ExecutionTelemetry | Actual runtime, memory, versions, work units and result hashes |

Budgets are not guaranteed OS allocations. Snapshots do not contain hostnames,
usernames, paths, IP addresses, environment variables or credentials. Plans must
be rechecked before launching. A preflight is not a numerical result.

Existing `/rtm/preview` and `/references/preview` responses carry optional
`execution_plan` fields for compatibility with saved older results. New Studio
Run controls require a feasible plan. Execution preferences are advanced controls;
normal users receive an automatic recommendation.

The shared acoustic `/rtm/preview` contract accepts `operation="forward"` for
generated-model forward-only preparation. An approved job uses `model_forward`;
the existing acoustic result envelope has `method="acoustic_forward"`. It contains
shot records, not a Born-adjoint image, and the worker does not invoke RTM.
The default operation remains RTM for existing clients and recorded experiments.

Authenticated, local-only `/fwi/preview` accepts `FWIPreviewRequest` from
`geoworld_open.client.fwi`. Natural language and structured debugging selections
are mutually exclusive. The contract distinguishes three identities:

| Identity | Scientific work | Default display snapshots |
| --- | --- | --- |
| `deepwave-marmousi1-simple-fwi-bounded-10-v0.0.26-r1` | Preserved Phase1A, ten simple SGD updates | Final only |
| `deepwave-marmousi1-simple-fwi-250-memory-adapted-v0.0.26-r1` | 250 simple SGD updates | Updates 50/100/150/200/250 |
| `deepwave-marmousi1-progressive-fwi-memory-adapted-v0.0.26-r1` | Five frequency stages, two outer LBFGS steps each | Steps 2/4/6/8/10: after 10/15/20/25/30 Hz |

These are explicitly labeled upstream-derived/memory-adapted acoustic Vp
experiments, not bytewise unchanged scripts, RTM or elastic/AVO inversion.
Contract support alone is not scientific acceptance or a guarantee that a
particular backend admits execution; its validation and resource gates apply.
The response contains a model-only preview, inherited settings, actual LLM
attribution when used, conflicts and an execution plan. Preview never launches
inversion. An explicit `/jobs` request uses `mode_hint="bounded_fwi"` and its
owner-bound `fwi_preparation_id`; it accepts no arbitrary paths or solver code.
The legacy transport mode name is retained for compatibility; the result's
`reference_id` and trace capability distinguish the actual experiment. Selecting
`action="run"` records user intent, not execution by the preview endpoint.

`IntermediateResultPolicy` in `client.intermediate_results` is a portable display
policy, not a numerical or hardware policy. It defaults to `auto`, uses scientific
stage boundaries when supplied, and otherwise gives final-only output for short
runs or about five states for long runs. `final`, `interval`, and explicit
`schedule` overrides are bounded to at most ten states, always including final.
Backends may reject policies unsupported by a preserved reference; they must not
promise snapshots they do not produce. Display snapshots are separate from
restart checkpoints. `FWIPreview.snapshot_schedule` records the resolved counts.

`JobProgress` retains its existing RTM behavior and can also report completed
shots, SGD updates, or `LBFGS outer step` counts. The simple250 denominator is
250; the progressive denominator is ten. Inner shots, line-search closure
reevaluations, snapshots and checkpoint writes never increment these counts.
Optional `stage_label` and `eta_confidence` describe the frequency/closure and
estimate uncertainty without inventing a fixed closure count.
Live ETA is based on measured work and is distinct from
the pre-run runtime range. Artifacts, traces and manifests use the existing job
system. Checkpoint continuation is a local scientific proof, not a general
durable job, remote scheduler or migration service.

The vendored `reference/deepwave_marmousi/example_fwi.py` is the unmodified MIT
upstream source at commit `7dbaeda5fdfbff2a6d579dcc9f7f18488c5e6084`, SHA-256
`fd5f708df9b79d16a7e3be9e19861a602e5de9909fd1df9d6d4bf30f451a47ee`.
It is provenance material, not a public optimized inversion implementation.
The bounded and simple250 identities refer to the first inversion section;
the progressive identity refers to its constrained, frequency-filtered section.
The published script itself remains untouched. See the adjacent existing LICENSE.

Studio shows the actual interpretation provider/model separately from numerical
execution. Figures label inputs, current/recovered velocity, velocity changes and
synthetic truth. Truth is used for the upstream-style initial model and evaluation,
not as a term in the data objective. Lower data loss alone is not proof of model
recovery; losses from different frequency stages are not directly comparable.
