# ADR 0009: Fail-Closed Residual Readback Eligibility Without a Forecast Baseline

- Status: Accepted for local reference implementation
- Date: 2026-08-24

## Context

The architecture roadmap calls for a residual loop in which a forecast is compared with later
observations and the resulting residual can update fitter validity, weighting, or future
admissibility. The current READIN scenario runtime does not produce a forecast: it evaluates
user-declared conditional branch antecedents and fixes `prediction_state` to `NOT_REQUESTED`.
Manufacturing a residual from that structural result would confuse scenario logic with a calibrated
prediction and would create unsupported learning claims.

The bounded prerequisite can still be implemented and inspected. READIN can bind an earlier
scenario run to later admitted observations, prove their temporal order, test forecast-baseline
eligibility, and retain an explicit abstention.

## Decision

Add the closed event `residual.readback_completed` and a deterministic local eligibility runtime.

- A readback binds exactly one completed scenario run to one or more unique, already-admitted
  observations about the same tracked asset.
- Every selected observation must be strictly later than the bound scenario's declared horizon.
- The execution receipt binds the scenario and run digests, sorted observation, artifact, and frame
  identifiers, the complete observation snapshot digest, asset state version, implementation
  digest, and outcome digest.
- The Phase 8A runtime accepts only the current `NOT_REQUESTED` prediction state and records
  `INELIGIBLE_NO_FORECAST_BASELINE`.
- Residual is `NOT_COMPUTED`; validity, weighting, and future-admissibility updates are
  `NOT_APPLIED`; learning is `NOT_STARTED`.
- Projection recomputes all bindings, rejects drift or tampering, and allows at most one readback per
  scenario run.
- Network access is false and authority remains `NO_AUTHORITY`.
- The read-only workbench adds a Readback view that exposes the eligibility decision and the updates
  not taken.

## Consequences

READIN can now preserve the chronology and provenance needed for later residual calibration without
pretending that a structural scenario run was a forecast. This makes the missing forecast baseline
inspectable rather than silently skipping the residual stage.

This is Phase 8A, not completion of the Phase 8 residual loop. It establishes no forecast accuracy,
residual value, empirical fitter validity, calibration, weighting policy, admissibility rule,
learning effect, operational utility, surveillance authority, targeting authority, or action
authority. A forecast-capable fitter and separately validated update contract remain gated future
work.
