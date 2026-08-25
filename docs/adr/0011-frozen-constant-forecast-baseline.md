# ADR 0011: Frozen Constant Forecast Baseline Without Residual Scoring

- Status: Accepted for local reference implementation
- Date: 2026-08-25

## Context

ADR 0010 predeclares a numeric target, absolute-error metric, forecast origin, horizon, and
ledger-time leakage boundary. READIN still has no forecast baseline to which a later observation can
be compared. Adding a learned or externally hosted model would open training-data, selection,
calibration, model-service, and operational boundaries that are not justified by the current slice.

The next prerequisite can be narrower. A user can freeze one numeric constant after the evaluation
design is recorded and before forecast origin. The constant is useful only as a deterministic
benchmark for a later scoring contract. It is not an observation, evidence, a calibrated model, or
a claim about the world.

## Decision

Add the closed event `forecast.baseline_completed` and a deterministic local reference runtime.

- One baseline binds one predeclared forecast-evaluation design and its immutable scenario.
- The only method is `USER_DECLARED_CONSTANT`; it uses no training observations and returns the
  manually supplied finite numeric value.
- The method is a separate reference benchmark, not a registered fitter; fitter selection remains
  `NOT_SELECTED` and no eligible fitter id is created.
- Baseline execution must occur no earlier than design creation and strictly before forecast origin.
- The prediction unit, observation type, structured-field path, origin, horizon, cutoff, and leakage
  policy are copied from the bound design and reverified during replay.
- A digest-bound receipt preserves the design, scenario, empty input snapshot, implementation, and
  outcome bindings.
- Prediction state is `PRODUCED_UNCALIBRATED_BASELINE`; calibration and empirical validity remain
  `NOT_ESTABLISHED`.
- Residual scoring remains `NOT_ENABLED`; validity, weighting, and future-admissibility updates stay
  `NOT_APPLIED`; learning stays `NOT_STARTED`.
- A design may have at most one frozen baseline.
- If a baseline exists, the Phase 8A no-baseline readback runtime rejects execution rather than
  mislabeling the run as `INELIGIBLE_NO_FORECAST_BASELINE`.
- Runtime and replay are local and deterministic, network access is false, and authority remains
  `NO_AUTHORITY`.

## Consequences

READIN can now preserve a genuinely pre-outcome numeric comparison point without pretending that a
trained or calibrated forecasting model exists. Later work can add a separately closed residual
scoring event that compares this frozen value with a compatible post-horizon observation.

This Phase 8C slice does not compute a residual, estimate uncertainty, establish calibration or
forecast skill, validate the target or metric, update fitter validity or weighting, change future
admissibility, begin learning, contact a source, access a network, or grant operational, surveillance,
targeting, intervention, or action authority. It does not complete the Phase 8 residual-loop exit
condition.
