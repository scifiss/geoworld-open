# Seismic Explorer client

The public Seismic Explorer surface contains portable request/response contracts,
an authenticated HTTP client, and Studio presentation. It has no file-reader or
filesystem-path capability and cannot launch a numerical solver.

Studio shows a dataset summary, the current bounded view, selection, and optional
analysis. Display clipping is labeled display-only. Dataset headers, provenance,
raw metadata, and read details stay under the collapsed Advanced section.

The client exposes:

- `list_seismic_datasets()` for backend-approved opaque dataset identities;
- `get_seismic_view(...)` for sections, cube slices, traces, and subvolumes;
- `continue_seismic_explorer(...)` for typed, stateful view changes and analysis.

The private backend controls allowed roots, format adapters, geometry validation,
lazy reads, indexing, and conversation state. Regular post-stack 2D/3D is the V1
boundary; prestack, irregular geometry, AVO, FWI, and preprocessing are rejected.
