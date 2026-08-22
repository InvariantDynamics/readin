# ADR 0002: Bounded Phase 1 Epistemic Array Semantics

- Status: Accepted for local reference implementation
- Date: 2026-08-21

## Context

Phase 0 can preserve entities, observer frames, evidence manifests, and observations, but it cannot
represent the analytical step from observations to a contestable claim. It also cannot prevent
multiple derivatives of one source from appearing to be independent corroboration or distinguish
what was known at a past cutoff from what is reconstructed with later knowledge.

## Decision

Add four closed event contracts: `evidence.dependency_declared`, `claim.created`,
`evidence.linked`, and `relation.created`.

- Every claim begins `unresolved` and cites admitted observations.
- An evidence link records role, dependency group, warrant, appraisal, and strength independently.
- Evidence dependency ancestry is acyclic. Manifest-verified ancestry must be bound by the
  descendant artifact's transformation inputs and must describe a derivative relationship.
- Observation dependency-group tags must reference an already declared group containing the
  observation's source artifact.
- The presence of a dependency group yields `DEPENDENT_EVIDENCE_PRESENT`. The absence of a group
  yields `INDEPENDENCE_NOT_ESTABLISHED`, never an independence claim.
- A `derives` evidence link must name an artifact used by a claim derivation observation.
- Every claim cited by a relation must connect its declared source and target. Confidence remains
  `UNASSESSED`.
- Causal relations are rejected unless expressed as the provisional `CAUSES?` relation with
  `CAUSAL_HYPOTHESIS` semantics.
- Asset-relevant events advance an epistemic state version.
- Historical views distinguish `AS_KNOWN_THEN` from `AS_RECONSTRUCTED_NOW`, and the latter marks
  later-recorded events as hindsight.
- Ledger event times are non-decreasing, preventing later appends from backdating admission order.
  The local ledger does not provide external timestamp attestation.
- All records and projections remain `NO_AUTHORITY`.

## Consequences

The runtime can now represent a small inspectable claim graph and replay its history without
promoting observations, repetition, or analyst input into truth. The implementation is intentionally
manual and local. It does not extract claims, assign confidence, infer source independence, run a
fitter, acquire live data, or authorize action.

Future contracts must preserve these separations or supersede this ADR with explicit migration and
negative tests.
