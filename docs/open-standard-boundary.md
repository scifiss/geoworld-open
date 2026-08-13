# Open Standard and Protected Engine Boundary

This classification records the repository audit performed before the Standard/SDK implementation. The public and private repositories are complementary layers of one GeoWorld product, not separate products and not a simple superset relationship.

| Classification | Public/private functionality |
|---|---|
| **A. Public standard** | Eight-concept World Kernel; GeoSpec; capability, validity-domain, transition, render, observation, Provenance, and manifest contracts. |
| **B. Public SDK/infrastructure** | Registration, serialization, validation, artifact loading, checksum verification, conformance tools, benchmark evaluation, and optional HTTP client. |
| **C. Public benchmark** | Faulted reservoir, multi-fault structure, seismic/AVO, CO2 monitoring, state/observation, and renderer-neutral requests. |
| **D. Minimal public reference implementation** | Transparent analytic structural examples, simplified Aki-Richards/seismic examples, flagship synthetic state/evidence example, and algebraic acoustic impedance. |
| **E. Private differentiated implementation** | Production physics and rendering, vendor-derived/advanced algorithms, calibration, inversion/UQ, LLM/agent reasoning, prompts, RAG/knowledge, product API/auth/database/jobs, user projects, and deployment operations. |
| **F. Duplicated / needs consolidation** | Private World/manifest/capability schemas overlap conceptually with the public standard. Future private adapters should consume the public package rather than duplicate normative contracts. No private migration is performed in this task. |
| **G. Legacy** | The public ordered-operator workflow remains a supported bounded reference benchmark; private historical local-LLM/tunnel and earlier World abstractions remain non-normative. |

## Rules

- Public defines the interface; protected code defines differentiated implementation.
- Public code never imports `geoworld`.
- Protected capabilities may be called over the documented HTTP boundary and may return `unavailable` clearly.
- Public reference science remains independently runnable without the protected service.
- Agents act above the World and are not a ninth kernel concept.
- Heavy renderer code and advanced numerical methods are not required to publish their implementations to conform to the public request/result contracts.
