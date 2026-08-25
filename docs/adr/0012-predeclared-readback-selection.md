# ADR 0012: Predeclared Readback Selection Without Residual Scoring

- Status: Accepted for local reference implementation
- Date: 2026-08-25

## Context

ADR 0011 allows READIN to freeze one uncalibrated constant baseline before forecast origin. A later
numeric observation could be compared with that baseline, but the current evaluation design does
not specify which observer frames are eligible, when the readback window closes, how long late
admissions remain eligible, or what to do when several observations match. Selecting those details
after the outcome is visible would permit observer, timing, and cardinality choices to be optimized
against the result.

The residual arithmetic is trivial; the selection boundary is not. READIN needs a preregistered and
replay-verifiable way to identify one eligible readback observation or abstain before any numeric
score is computed.

## Decision

Add the closed events `forecast.readback_selection_plan_created` and
`forecast.readback_selection_completed` plus a deterministic local selection runtime.

- One plan binds one Phase 8C baseline, its evaluation design, scenario, target, and one or more
  already-registered eligible observer frames.
- The plan is recorded no earlier than the baseline and strictly before forecast origin.
- It predeclares an observed-time window ending strictly after the scenario horizon and a
  ledger-admission cutoff at or after that window end.
- Candidate observations must concern the same asset, match the target observation type and one of
  the eligible frames, fall strictly after the horizon and no later than the observed-window end,
  be admitted no later than the ledger cutoff, and contain the declared finite numeric field.
- Unit compatibility remains `USER_DECLARED_NOT_VERIFIED` because the current observation contract
  does not carry a separately validated unit binding.
- Cardinality is fixed to `EXACTLY_ONE`. Zero candidates produce `ABSTAINED_NO_MATCH`; multiple
  candidates produce `ABSTAINED_MULTIPLE_MATCHES`. No aggregation, ranking, or post-hoc choice is
  permitted.
- Selection executes only at or after the admission cutoff and records mutually exclusive exclusion
  lists for post-cutoff admission, outside-window timing, type mismatch, frame mismatch, and invalid
  numeric target.
- The receipt binds the plan, design, baseline, scenario, observer frames, classified observation
  snapshot, implementation, and outcome digests.
- Residual remains `NOT_COMPUTED`; scoring remains `NOT_ENABLED`; calibration and empirical validity
  remain `NOT_ESTABLISHED`; validity, weighting, and future-admissibility updates remain
  `NOT_APPLIED`; learning remains `NOT_STARTED`.
- Runtime and replay are local and deterministic, network access is false, and authority remains
  `NO_AUTHORITY`.

## Consequences

READIN can now distinguish a uniquely eligible later observation from an ambiguous or absent
readback set without choosing after seeing values. The result is an eligibility decision, not a
residual, forecast validation, evidence item, or world-state claim.

This Phase 8D slice does not compute signed residual or absolute error, aggregate observers,
establish unit compatibility, estimate uncertainty, establish calibration or forecast skill, update
fitter validity or weighting, change future admissibility, begin learning, contact a source, access
a network, or grant operational, surveillance, targeting, intervention, or action authority. It
does not complete the Phase 8 residual-loop exit condition.
