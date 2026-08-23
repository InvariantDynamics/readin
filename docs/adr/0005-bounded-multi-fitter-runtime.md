# ADR 0005: Bounded Multi-Fitter Runtime Without Compulsory Consensus

- Status: Accepted for local reference implementation
- Date: 2026-08-23

## Context

READIN needs to execute one bounded query through heterogeneous analytical observers while retaining
their method-specific assumptions, invalidity, abstention, and disagreement. Treating each output as
a confidence score, averaging unlike metrics, or forcing every fitter to answer would erase the
epistemic distinctions the runtime exists to preserve.

The architecture calls for Bayesian, graph, and temporal fitters, an explicit `admissible()` gate,
FitResults, execution receipts, residual readback, and a validity atlas. This slice opens only the
local diagnostic execution and receipt boundary. It does not open forecasting, readback-driven
validity updates, external model services, or operational action.

## Decision

Add two closed events: `fitter.registered` and `fitter.run_completed`.

- A registered fitter is one of three built-in deterministic reference diagnostics: Bayesian claim
  support, relation topology, or observation cadence.
- Descriptors bind the exact implementation digest, target metric, versioned input/output contracts,
  admissibility rules, and explicit invalid conditions.
- Bayesian execution requires exactly one bounded claim and declared dependency groups. Repeated
  members of one group count as one diagnostic support or challenge unit, and conflicts remain
  explicit.
- Graph execution requires at least one relation and makes no influence, importance, or causal claim.
- Temporal execution requires at least two observations and rejects a hindsight-defined historical
  query lens rather than silently accepting leakage.
- A run outcome is `FIT`, `ABSTAINED`, or `INVALID`. Only an admissible run may contain a FitResult.
- Every receipt binds the complete requested fitter set, cartographic input digest, asset state
  version, input and exclusion identifiers, fitter digest, assumptions, outcome digest, and execution
  policy.
- Interrupted append sequences remain inspectable as `PARTIAL`; completed and missing fitter IDs are
  explicit.
- Multi-fitter views retain method-specific outputs. They do not average them, privilege a fitter,
  or compute consensus.
- Empirical validity is `NOT_ESTABLISHED`, uncertainty is `NOT_CALIBRATED`, residuals are
  `NOT_AVAILABLE`, prediction is `NOT_REQUESTED`, network access is false, and authority is
  `NO_AUTHORITY`.

## Consequences

The same query can now execute reproducibly across heterogeneous local diagnostics. READIN can
represent a model refusing or being invalid for an input, distinguish incommensurate outputs, and
audit partial execution without inventing consensus.

These mechanics establish contract conformance only. They do not establish probabilistic
calibration, model accuracy, scientific validity, source coverage, forecasting capability, causal
identification, residual-based model weighting, production readiness, or action authority. A future
residual loop requires later observations, predeclared error metrics, leakage controls, readback
events, and a separate ADR.
