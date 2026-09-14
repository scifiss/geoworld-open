# Local execution contracts (Phase 1A)

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
are mutually exclusive. The only admitted version is
`deepwave-marmousi1-simple-fwi-bounded-10-v0.0.26-r1`: a **modified**, bounded
upstream-derived acoustic velocity inversion, not unchanged full FWI, RTM or AVO.
The response contains a model-only preview, inherited settings, actual LLM
attribution when used, conflicts and an execution plan. Preview never launches
inversion. An explicit `/jobs` request uses `mode_hint="bounded_fwi"` and its
owner-bound `fwi_preparation_id`; it accepts no arbitrary paths or solver code.

`JobProgress` retains its existing RTM behavior and can also report completed
shots or FWI iterations. Live ETA is based on measured work and is distinct from
the pre-run runtime range. Artifacts, traces and manifests use the existing job
system. Checkpoint continuation is a local scientific proof, not a general
durable job, remote scheduler or migration service.

The vendored `reference/deepwave_marmousi/example_fwi.py` is the unmodified MIT
upstream source at commit `7dbaeda5fdfbff2a6d579dcc9f7f18488c5e6084`, SHA-256
`fd5f708df9b79d16a7e3be9e19861a602e5de9909fd1df9d6d4bf30f451a47ee`.
It is provenance material, not a public optimized inversion implementation.
The bounded backend uses only its first/simple inversion section; the advanced
frequency-filtered section is not enabled. See the adjacent existing LICENSE.
