# ADR 0013: Descriptive Residual for a Frozen Reference Baseline

- Status: Accepted for local reference implementation
- Date: 2026-08-25

## Context

ADR 0012 can deterministically select exactly one observation from a preregistered readback
aperture. READIN still has no event that compares that observation with the frozen Phase 8C
constant. The arithmetic is well defined, but its interpretation is sharply bounded: the baseline
is user declared, uncalibrated, and empirically unvalidated; the observation contract does not carry
a separately validated unit binding; and one readback cannot establish forecast skill.

## Decision

Add the closed event `forecast.residual_computed` and a deterministic local reference runtime.

- One result binds one completed Phase 8D selection run in `UNIQUE_MATCH_SELECTED` state.
- Zero-match and multiple-match abstentions are ineligible and remain visible as abstentions.
- The runtime binds the selection plan, frozen baseline, evaluation design, scenario, selected
  observation, observer frame, and evidence manifest.
- Signed residual is computed as `observed - predicted`; absolute error is its absolute value.
- The metric remains the predeclared `ABSOLUTE_ERROR` with `LOWER_IS_BETTER` direction.
- Unit compatibility remains `USER_DECLARED_NOT_VERIFIED`; the result is therefore descriptive
  arithmetic, not validated measurement equivalence.
- The result is fixed to one readback and reports uncertainty as
  `NOT_ESTIMATED_SINGLE_READBACK`.
- Calibration and empirical validity remain `NOT_ESTABLISHED`; validity, weighting, and
  future-admissibility updates remain `NOT_APPLIED`; learning remains `NOT_STARTED`.
- The receipt binds all inputs, the implementation, and the outcome. Runtime and replay are local
  and deterministic, network access is false, and authority remains `NO_AUTHORITY`.

## Consequences

READIN can now retain the exact descriptive error between a frozen reference constant and one
uniquely selected later observation without converting that number into forecast validation or
model authority.

This Phase 8E slice does not verify unit equivalence, estimate uncertainty, establish calibration or
forecast skill, aggregate a validation corpus, update a fitter, change model weights or future
admissibility, begin learning, contact a source, access a network, deploy a service, or grant
operational, surveillance, targeting, intervention, or action authority. It does not complete the
Phase 8 residual-loop exit condition.
