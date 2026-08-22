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

The current implementation opens the entity, tracking, frame, evidence-manifest, observation,
dependency, claim, evidence-link, relation, historical reconstruction, and reversible candidate
resolution layers. These layers remain separate: an observation is never silently promoted into a
claim or belief, and linked
evidence never resolves a claim by itself.

## Ownership boundary

| Layer | Owns | Does not own |
| --- | --- | --- |
| READIN | Asset lifecycle, adapters, persistence, intelligence queries, fitters, scenarios, UI | OFS Core semantics or authority |
| Epistemic Array | Frames, observations, claims, evidence, warrants, dependency, disagreement, blind regions | Application workflow or collection credentials |
| OFS, optional | Pinned conformance and execution resources | READIN tenancy, persistence, workflow, or action authority |

## Current event model

The ledger supports eleven events:

- `entity.created`
- `asset.tracking_started`
- `observer_frame.registered`
- `evidence.manifested`
- `observation.admitted`
- `evidence.dependency_declared`
- `claim.created`
- `evidence.linked`
- `relation.created`
- `entity.resolution_candidate_recorded`
- `entity.resolution_candidate_assessed`

Every event is append-only, schema-validated, timestamped, uniquely identified, and marked
`NO_AUTHORITY`. Projection fails closed when an asset or frame is unknown, an identifier is reused,
or a ledger record does not validate.

```text
entity.created --> asset.tracking_started -------------------------------+
                                                                         |
observer_frame.registered ----------------+                              |
                                          |                              |
evidence.manifested ----------------------+--> observation.admitted -----+
        |                                           |                    |
        +--> evidence.dependency_declared           +--> claim.created --+
                                                              |          |
evidence.manifested --------------------------> evidence.linked+          |
                                                              |          v
entity.created ---------------------------------> relation.created --> replay
                                                                         |
                                                           asset view + timeline
```

Candidate resolution is a sidecar to entity identity, not an entity mutation. A candidate records
`POSSIBLE_SAME_ENTITY` plus polarity-preserving signals. Manual assessments form an append-only,
linearly superseded history. `automatic_merge: false` and `merge_state: NOT_MERGED` are contract
constants even for `CONFIRMED_MATCH_NOT_MERGED`; no event in this slice can merge entities.
Signal verification is a separate axis: asserted, reference-validated, or exact entity-record
validated. A validated shared field supports candidacy only and never establishes identity.

Claims are created with `epistemic_status: unresolved`. An evidence link records role or polarity,
dependency group, warrant, appraisal, and strength as separate axes. Strength is `UNASSESSED` until
an appraisal is completed. A `derives` link must name an artifact used by one of the claim's cited
observations. Relations have `UNASSESSED` confidence, every cited claim must connect the declared
source and target, and causal relations must be written explicitly as the provisional pair `CAUSES?`
and `CAUSAL_HYPOTHESIS`.

Evidence dependency declarations form an acyclic ancestry graph. A link may name a dependency group
only when its artifact is a declared member of that group. The projection reports dependent evidence
without claiming that ungrouped artifacts are independent. Observation-level dependency-group tags
are accepted only after the group has been declared and only for member artifacts. Manifest-based
verification is limited to derivative relationships bound by the descendant manifest.

## Historical reconstruction

Every asset-relevant event advances an explicit epistemic state version. Timeline queries expose two
non-interchangeable modes:

- `AS_KNOWN_THEN` excludes events recorded after an epistemic cutoff.
- `AS_RECONSTRUCTED_NOW` includes later-recorded events and marks them as hindsight.

The default is `AS_KNOWN_THEN`. Effective time and ledger-recorded time remain separate so later
knowledge cannot be silently inserted into a historical view. Event `occurred_at` values must be
non-decreasing in ledger order; this prevents a later append from being replayed as an earlier
admission. This is a local chronology invariant, not an externally trusted timestamp or
cryptographic time attestation.

## Persistence boundary

The initial reference store is a local POSIX JSONL ledger. Writes are locked, flushed, and synced.
The representation is intentionally simple enough to inspect and replay. It is not yet a distributed
event log, database, or service.

Raw source artifacts are represented by immutable evidence manifests with SHA-256 identity, media
type, byte size, source, license, access policy, transformations, and derivative references. Binary
artifact storage and live acquisition are later gated work.

## Planned slices

1. **Phase 0 foundation** — tracked assets, frames, evidence manifests, observations, and event
   replay. *(implemented)*
2. **Phase 1 bounded Array** — unresolved claims, relations, evidence links, dependency ancestry,
   asset versions, and hindsight-labeled reconstruction. *(implemented)*
3. **Phase 2 candidate resolution** — reversible entity candidates and manual assessments; no
   merge. *(implemented)*
4. **Extended cartography** — surface traversal, explicit blind regions, and query planning.
5. **Multi-fitter runtime** — bounded fitter inputs, receipts, residuals, validity, disagreement.
6. **Scenario and belief engine** — conditional branches without destiny claims.
7. **Asset workbench** — dense operator interface over the inspectable epistemic field.

Each slice requires its own contract, positive and negative fixtures, validation path, claim ceiling,
and stop conditions.
