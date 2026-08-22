# READIN Architecture v0.1

**Status:** Initial implementation boundary
**System class:** Open-source multi-frame intelligence adapter and multi-fitter environment

## Product thesis

READIN organizes intelligence around persistent epistemic objects rather than documents, feeds,
searches, embeddings, chat sessions, or model outputs. Adding an entity creates a tracked asset with
an evolving, replayable epistemic field.

For an entity `e`, the intended state is:

```text
E_e(t) = (observations, claims, relations, hypotheses, beliefs,
          disagreements, uncertainties, aperture)
```

The current implementation opens only the entity, tracking, frame, evidence-manifest, and
observation layers. Later layers must remain separate and must never silently promote an observation
into a claim or belief.

## Ownership boundary

| Layer | Owns | Does not own |
| --- | --- | --- |
| READIN | Asset lifecycle, adapters, persistence, intelligence queries, fitters, scenarios, UI | OFS Core semantics or authority |
| Epistemic Array | Frames, observations, claims, evidence, warrants, dependency, disagreement, blind regions | Application workflow or collection credentials |
| OFS, optional | Pinned conformance and execution resources | READIN tenancy, persistence, workflow, or action authority |

## Current event model

The first ledger supports five events:

- `entity.created`
- `asset.tracking_started`
- `observer_frame.registered`
- `evidence.manifested`
- `observation.admitted`

Every event is append-only, schema-validated, timestamped, uniquely identified, and marked
`NO_AUTHORITY`. Projection fails closed when an asset or frame is unknown, an identifier is reused,
or a ledger record does not validate.

```text
entity.created --> asset.tracking_started ----------------+
                                                         |
observer_frame.registered ----------------+              |
                                          |              |
evidence.manifested ----------------------+--------------+
                                                         |
                                                         v
                                                observation.admitted
                                                         |
                                                         v
                                                deterministic replay
                                                         |
                                                         v
                                                 inspectable asset view
```

## Persistence boundary

The initial reference store is a local POSIX JSONL ledger. Writes are locked, flushed, and synced.
The representation is intentionally simple enough to inspect and replay. It is not yet a distributed
event log, database, or service.

Raw source artifacts are represented by immutable evidence manifests with SHA-256 identity, media
type, byte size, source, license, access policy, transformations, and derivative references. Binary
artifact storage and live acquisition are later gated work.

## Planned slices

1. **Phase 0 foundation** — tracked assets, frames, evidence manifests, observations, and event
   replay. *(current)*
2. **Candidate resolution** — reversible entity candidates; no automatic merge.
3. **Claims and evidence links** — typed modality, polarity, warrant, dependency groups.
4. **Historical reconstruction** — time-indexed surface traversal and explicit blind regions.
5. **Multi-fitter runtime** — bounded fitter inputs, receipts, residuals, validity, disagreement.
6. **Scenario and belief engine** — conditional branches without destiny claims.
7. **Asset workbench** — dense operator interface over the inspectable epistemic field.

Each slice requires its own contract, positive and negative fixtures, validation path, claim ceiling,
and stop conditions.
