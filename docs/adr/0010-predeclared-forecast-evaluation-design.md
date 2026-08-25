# ADR 0010: Predeclared Forecast-Evaluation Design Without Forecast Execution

- Status: Accepted for local reference implementation
- Date: 2026-08-24

## Context

ADR 0009 allows READIN to bind a scenario run to later observations and abstain when the run has no
forecast baseline. A future residual cannot be interpreted safely unless the measured outcome,
metric, temporal cutoff, forecast origin, horizon, and leakage policy were declared before the
outcome was observed. Choosing those fields after readback would permit hindsight leakage and
metric selection against the result.

READIN still has no registered forecast-capable fitter, calibrated prediction contract, or evidence
that a forecast model is valid. The next bounded slice must establish the evaluation design without
claiming that a forecast exists.

## Decision

Add the closed event `forecast.evaluation_design_created`.

- One design binds one tracked asset and scenario before the scenario's forecast origin.
- The design predeclares one observation type, numeric structured-field path, unit, absolute-error
  metric, and `OBSERVED_MINUS_PREDICTED` residual convention.
- The training cutoff uses ledger-recorded time and cannot follow design creation. Inputs recorded
  after that cutoff are excluded by contract.
- Forecast origin and horizon end are derived from the immutable scenario and reverified during
  replay.
- The target and metric remain user-declared and unvalidated.
- Only one design may bind a bounded scenario.
- Fitter selection remains `NOT_SELECTED`, forecast execution `NOT_STARTED`, prediction
  `NOT_PRODUCED`, calibration `NOT_ESTABLISHED`, and empirical validity `NOT_ESTABLISHED`.
- Phase 8A readback now requires a design, verifies that every later observation matches its type and
  contains the declared numeric target, and binds the design digest into the receipt.
- Authority remains `NO_AUTHORITY`; no network access, source contact, or external action is added.

## Consequences

READIN can distinguish a genuinely predeclared evaluation target from a target selected after the
outcome was known. Later observations can be checked for temporal and structural compatibility with
that design, giving a future forecast runtime a deterministic scoring contract.

This slice does not register or select a forecast-capable fitter, execute a forecast, generate a
prediction, compute a residual, estimate uncertainty, establish calibration, update fitter validity
or weighting, change future admissibility, or begin empirical learning. The full Phase 8 exit
condition remains unmet.
