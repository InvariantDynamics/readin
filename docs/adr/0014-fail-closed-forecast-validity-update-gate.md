# ADR 0014: Fail-Closed Forecast Validity-Update Gate

- Status: Accepted for local reference implementation
- Date: 2026-08-26

## Context

ADR 0013 records one descriptive residual for a frozen, user-declared constant. The residual is
arithmetically valid inside its declared boundary, but it is not sufficient evidence for a fitter
validity, weighting, future-admissibility, or learning update. READIN needs an explicit executable
gate so that the absence of update warrant is retained as a result rather than left implicit.

## Decision

Add the closed event `forecast.validity_update_assessed` and a deterministic local eligibility
runtime.

- One assessment binds one Phase 8E descriptive forecast residual and its selection run, baseline,
  evaluation design, and scenario.
- The reference gate exposes six hard blockers: no registered forecast fitter; a user-declared
  constant rather than a trained model; one readback only; unverified unit equivalence; no
  predeclared validation corpus; and no uncertainty estimate.
- The gate records `INELIGIBLE_VALIDITY_UPDATE` and `ABSTAINED`. It does not infer model invalidity
  from insufficient evidence.
- No target fitter is available. Calibration and empirical validity remain `NOT_ESTABLISHED`;
  validity, weighting, and future-admissibility updates remain `NOT_APPLIED`; learning remains
  `NOT_STARTED`.
- The receipt binds all inputs, the reference implementation, and the outcome. Runtime and replay
  are local and deterministic, network access is false, and authority remains `NO_AUTHORITY`.

## Consequences

READIN can now show that a validity update was explicitly considered and withheld for inspectable,
replay-verifiable reasons. This is an abstention caused by missing warrant, not evidence that the
reference baseline is valid or invalid.

This Phase 8F slice does not register or train a forecast fitter, verify unit equivalence,
predeclare or aggregate a validation corpus, estimate uncertainty, establish calibration or
forecast skill, update a fitter, change weights or admissibility, begin learning, contact a source,
access a network, deploy a service, or grant operational or action authority. It does not complete
the Phase 8 residual-loop exit condition.
