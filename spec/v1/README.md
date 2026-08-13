# GeoWorld Open Standard 1.0

GeoWorld Open 1.0 defines an executable interoperability boundary for semantic scientific Worlds and deterministic capabilities.

## Normative contracts

- World Kernel: `World`, `Entity`, `Relation`, `Representation`, `Field`, `WorldState`, `Observation`, `Provenance`.
- Scientific capabilities: `CapabilitySpec`, typed input/output variables, units, assumptions, references, and `ValidityDomain`.
- State transition: append-only `TransitionResult` plus complete typed Provenance.
- Rendering: renderer-neutral `RenderRequest` and `RenderSpec` for 2D, 3D, and 4D scenes.
- Artifacts: relative paths, byte counts, SHA-256 checksums, and a manifest.
- Service boundary: the HTTP API described by [`capability-api.yaml`](capability-api.yaml).

The Pydantic implementations under `geoworld_open.standard` and `geoworld_open.world` are the executable schema authority for this release. JSON schemas can be generated with `model_json_schema()`.

## Compatibility

An implementation is GeoWorld-compatible for a capability when it:

1. publishes a valid `CapabilitySpec`;
2. accepts and returns variables with the declared names, dimensions, units, and dtype families;
3. does not mutate caller input;
4. records valid state transitions and Provenance where state changes;
5. returns artifacts conforming to the public manifest or render-result contracts;
6. passes the applicable checks in `geoworld_open.conformance`.

Compatibility does not imply scientific suitability outside the declared validity domain.

## Extension model

Third parties implement `PhysicsCapability`, register it with `CapabilityRegistry`, and run the conformance suite against representative inputs. Implementations may remain local, live in another package, or be protected behind the HTTP capability API. No implementation may require `geoworld-open` to import private GeoWorld source.
