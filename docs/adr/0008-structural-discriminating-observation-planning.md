# ADR 0008: Structural Discriminating-Observation Planning Without Acquisition

- Status: Accepted for local reference implementation
- Date: 2026-08-23

## Context

The architecture roadmap calls for active collection that can identify which new observation would
best resolve a specified ambiguity. READIN does not yet have source adapters, validated outcome
models, calibrated probabilities, collection authorization, or evidence that any candidate source
is feasible or independent. Opening query execution or acquisition would exceed the current local,
manual, `NO_AUTHORITY` boundary.

The narrow exit condition can still be implemented and inspected if the input and claim ceiling are
explicit: a user declares possible observations and their expected structural effects on competing
hypotheses, and READIN deterministically shows whether those declarations distinguish the
hypotheses.

## Decision

Add two closed events: `collection.discrimination_plan_created` and
`collection.discrimination_run_completed`.

- A plan binds a tracked asset, immutable belief revision, persisted cartographic query, competing
  hypotheses, manual candidate observations, and optional targets drawn from that query's known
  blind regions.
- Every expected outcome and hypothesis effect is `USER_SUPPLIED_NOT_VALIDATED`. Candidate
  feasibility is not validated and source independence is not established.
- The reference algorithm computes an ordinal structural score from declared pairwise hypothesis
  separation, discriminating-outcome count, and blind-region alignment. It does not compute outcome
  probability or expected information gain.
- Equal structural score keys retain ties. When no candidate separates the declared hypotheses, the
  runtime abstains rather than manufacturing a recommendation.
- Projection recomputes all scores and verifies digest-bound plan, belief, query, candidate,
  hypothesis, implementation, and outcome receipts.
- Collection remains `NOT_STARTED`, acquisition remains `NOT_ATTEMPTED`, network access is false,
  and authority remains `NO_AUTHORITY`.
- The Phase 6 workbench adds a read-only “Next observation” tab. It exposes the ambiguity, ordinal
  rank components, ties or abstention, and the no-collection boundary. It adds no mutation control.

## Consequences

READIN can now show which user-declared observation is structurally more discriminating for a
specified ambiguity and can preserve tied or non-discriminating alternatives. The result is
replayable and inspectable, but it is not a validated acquisition recommendation.

This slice does not establish candidate feasibility, source availability, source independence,
collection cost, outcome likelihood, expected information gain, empirical ranking validity,
collection authority, operational utility, surveillance authority, targeting authority, or action
authority. Live querying, source contact, acquisition, scheduling, credentials, and adapters remain
separate gated work.
