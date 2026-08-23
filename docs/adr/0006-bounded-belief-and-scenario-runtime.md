# ADR 0006: Categorical Belief Revisions and Non-Predictive Scenario Branches

- Status: Accepted for local reference implementation
- Date: 2026-08-23

## Context

READIN needs to represent hypotheses, dependency-aware belief change, and conditional scenarios
without collapsing claims into truth, categorical diagnostics into probabilities, or scenario
branches into forecasts. The architecture requires a bounded directed acyclic belief graph,
dependency-aware propagation, scenario assumptions and interventions, model disagreement, and a
visible unknown/unmodeled branch.

The Phase 4 reference fitters are descriptive local diagnostics. None has established forecasting
validity or an output contract suitable for future trajectories. Invoking them as scenario forecast
models would violate their registered invalid conditions.

## Decision

Add five closed events: `hypothesis.created`, `belief.edge_created`,
`belief.revision_completed`, `scenario.created`, and `scenario.run_completed`.

- A hypothesis is unresolved and belongs to one tracked asset. It binds claims with explicit
  supporting or challenging polarity but does not resolve those claims.
- A belief edge is directed, assumption-bound, and restricted to one asset. It may support or
  challenge a target only when its source is `SUPPORT_LEADING`. Its causal status is always
  `NOT_ESTABLISHED`.
- The belief graph is acyclic. Replay rejects self-edges, cross-asset edges, duplicate directed
  pairs, incomplete upstream selections, and cycles.
- Direct evidence signals are grouped by declared dependency ancestry before counting. Ungrouped
  evidence remains `INDEPENDENCE_NOT_ESTABLISHED` rather than being presumed independent.
- Belief propagation returns only `SUPPORT_LEADING`, `CHALLENGE_LEADING`, `CONFLICTED`, or
  `UNRESOLVED`. These mean diagnostic signal balance, not belief probability or truth.
- Every belief receipt binds the asset state version, selected graph, claim and evidence-link IDs,
  dependency IDs, canonical input digest, executable implementation digest, and output digest.
- A scenario binds one immutable belief revision, user-supplied unvalidated assumptions,
  interventions with `NOT_ESTABLISHED` causal status, target entities, a finite horizon, and a
  bounded branch tree.
- Exactly one root branch preserves the unknown/unmodeled region. It cannot be removed, conditioned,
  or used as a parent for declared outcomes. Branch depth is limited to four.
- Scenario execution evaluates antecedent matching and parent gating only. Declared outcomes remain
  `CONDITIONAL_NOT_PREDICTED` and `USER_DEFINED_NOT_SIMULATED`.
- Phase 4 fitters are not run as forecast models. Fitter execution remains
  `NOT_RUN_NO_FORECAST_CAPABLE_FITTER`, likelihood is `NOT_COMPUTED`, trajectory is
  `NOT_SIMULATED`, prediction is `NOT_REQUESTED`, empirical validity is `NOT_ESTABLISHED`, and
  authority is `NO_AUTHORITY`.
- Every scenario receipt binds the exact scenario, belief revision, branch, assumption,
  intervention, implementation, input state, and output digests.

## Consequences

READIN can now replay an auditable dependency-aware categorical revision and inspect a conditional
scenario tree without inventing probability, simulation, prediction, or consensus. Invalid graph
structure, tampered receipts, promoted probability fields, removed unknown branches, and altered
branch evaluations fail closed.

This slice does not establish hypothesis truth, calibrated belief, causal identification, scenario
likelihood, future trajectory, forecast accuracy, decision quality, residual validity, production
readiness, surveillance authority, targeting authority, or action authority. A future forecasting
slice requires separately registered forecast-capable fitters, temporal leakage controls,
predeclared metrics, later-observation readback, residuals, validity updates, and a new ADR.
