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
resolution layers, plus bounded cartographic and multi-fitter layers. These layers remain separate:
an observation is never silently promoted into a claim or belief, linked evidence never resolves a
claim by itself, a selected surface never becomes a completeness claim, and a fitter result never
becomes evidence or model authority.

## Ownership boundary

| Layer | Owns | Does not own |
| --- | --- | --- |
| READIN | Asset lifecycle, adapters, persistence, intelligence queries, fitters, scenarios, UI | OFS Core semantics or authority |
| Epistemic Array | Frames, observations, claims, evidence, warrants, dependency, disagreement, blind regions | Application workflow or collection credentials |
| OFS, optional | Pinned conformance and execution resources | READIN tenancy, persistence, workflow, or action authority |

## Current event model

The ledger supports fifteen events:

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
- `cartography.surface_registered`
- `cartography.query_planned`
- `fitter.registered`
- `fitter.run_completed`

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

observer_frame.registered --> cartography.surface_registered
                                          |
tracked asset ----------------------------+--> cartography.query_planned
                                                     |
                                                     v
                                      read-only local-ledger traversal

cartography.query_planned --> fitter.run_completed --> receipt + result/abstention
                                  ^
                                  |
                         fitter.registered
```

Candidate resolution is a sidecar to entity identity, not an entity mutation. A candidate records
`POSSIBLE_SAME_ENTITY` plus polarity-preserving signals. Manual assessments form an append-only,
linearly superseded history. `automatic_merge: false` and `merge_state: NOT_MERGED` are contract
constants even for `CONFIRMED_MATCH_NOT_MERGED`; no event in this slice can merge entities.
Signal verification is a separate axis: asserted, reference-validated, or exact entity-record
validated. A validated shared field supports candidacy only and never establishes identity.

## Bounded cartography

A cartographic surface is an explicitly named composite of one or more registered observer frames.
Its blind-region state is either `DECLARED`, with at least one stated blind region, or
`NOT_CHARACTERIZED`, with no implied knowledge of what is missing. Surface coverage is always
`NOT_ESTABLISHED` in this slice.

A cartographic query plan is persistent and backward-only. It binds one tracked asset to one or more
surfaces, a reconstruction mode and optional epistemic cutoff, and a relation-traversal limit of zero
to three hops. Observations, claims, evidence manifests, and dependency ancestry are always retained;
relations may be disabled. Missingness and conflict policies are fixed to `PRESERVE`, prediction is
`NOT_REQUESTED`, and execution is `PLANNED_READ_ONLY`.

Execution deterministically traverses the already-admitted local ledger. An observation is selected
only when its observer frame is on the chosen surface and it concerns a visited entity. A claim is
included only when at least one of its derivation observations is selected. A relation can extend the
traversal only when it originates at the current frontier and cites a selected claim. Evidence
dependency closure remains visible so derivatives do not appear independent.

For `AS_KNOWN_THEN`, the epistemic cutoff bounds ledger data. Surface and plan definitions form a
separate query lens; when either was recorded to the ledger after the cutoff, the result marks that
lens as hindsight using ledger-recorded time rather than a backdatable domain timestamp. Results
report excluded asset observations, known and uncharacterized blind regions, `NOT_ESTABLISHED`
coverage, unevaluated surface validity conditions, no completeness claim, no network access, and
`NO_AUTHORITY`.

## Bounded multi-fitter runtime

Phase 4 treats a fitter as an executable analytical observer over one immutable cartographic query
result. The initial runtime registers three deterministic reference diagnostics:

- a Bayesian diagnostic that groups dependent evidence before producing a Beta support index, which
  is explicitly not a truth probability;
- a graph diagnostic that reports relation topology without inferring influence, importance, or
  causality;
- a temporal diagnostic that reports observation cadence without inferring a trend, latent state,
  regime, trajectory, or forecast.

Every descriptor binds a versioned implementation digest, target metric, input/output contracts,
admissibility rules, and declared invalid conditions. Empirical validity remains `NOT_ESTABLISHED`
and is limited to the closed synthetic ledger. Bayesian execution requires exactly one claim and
declared dependency groups. Graph execution abstains when relations are absent. Temporal execution
is invalid when an `AS_KNOWN_THEN` input uses a hindsight-defined query lens.

Each completed run records the full requested fitter set, input state version, canonical input
digest, included and excluded identifiers, fitter implementation digest, assumptions, outcome
digest, and non-authority policy. Interrupted appends remain visible as `PARTIAL` run groups with
their missing fitters; retained results are never deleted to improve the demo.

The group view preserves `FIT`, `ABSTAINED`, and `INVALID` outcomes and labels method-specific
outputs as incommensurate when their target metrics differ. Consensus is `NOT_COMPUTED`, no fitter
is privileged, and no averaging or weighting is performed. Residuals remain `NOT_AVAILABLE`,
uncertainty remains `NOT_CALIBRATED`, prediction is `NOT_REQUESTED`, and all outputs remain
`NO_AUTHORITY`.

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
4. **Phase 3 bounded cartography** — observer-frame surfaces, explicit blind regions, persistent
   backward query plans, and deterministic local traversal. *(implemented)*
5. **Phase 4 multi-fitter runtime** — bounded fitter inputs, digest-bound receipts, explicit
   admissibility/invalidity, partial groups, and preserved disagreement. *(implemented)*
6. **Phase 5 scenario and belief engine** — conditional branches without destiny claims.
7. **Phase 6 asset workbench** — dense operator interface over the inspectable epistemic field.

Each slice requires its own contract, positive and negative fixtures, validation path, claim ceiling,
and stop conditions.
