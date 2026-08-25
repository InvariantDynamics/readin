# READIN Project Instructions

## Boundary

READIN is an open-source intelligence application built on Epistemic Array principles. It is
not OFS Core and must not redefine OFS.

- READIN owns tracked assets, collection workflows, persistence, fitters, scenarios, and product
  surfaces.
- Epistemic Array owns the semantics of situated observations, claims, evidence, warrants,
  disagreement, dependencies, blind regions, and epistemic state.
- OFS is an optional execution and conformance runtime. Consume it only through an explicitly
  accepted immutable revision, schema or file digests, and validation receipt.
- Do not edit adjacent repositories from this repository.

## Evidence and authority

- An observation is not a fact, a claim is not a belief, and a model result is not evidence.
- Preserve observer frame, source artifact identity, acquisition method, dependency ancestry,
  uncertainty, missingness, and invalidation conditions.
- More documents do not imply more independent observers.
- Preserve disagreement and abstention. Do not average incompatible fitter results into false
  consensus.
- READIN-originated records carry `NO_AUTHORITY`. No record grants permission for surveillance,
  intervention, targeting, or external action.
- Human-entity collection is limited to public, licensed, user-owned, or otherwise authorized
  sources, with access policy and auditability.

## Current slice

The Phase 0 through bounded Phase 8D slices are local-first and manual-input only:

- typed tracked-asset creation;
- observer-frame registration;
- immutable observation admission;
- unresolved claim creation from admitted observations;
- typed entity relations backed by claims;
- evidence polarity, warrant, appraisal, and strength as separate axes;
- explicit evidence-dependency groups with cycle rejection;
- asset state-version history and hindsight-labeled reconstruction;
- reversible possible-identity candidates with polarity-preserving signals;
- append-only manual candidate assessments with explicit supersession;
- observer-frame cartographic surfaces with explicit blind-region and non-coverage state;
- persisted backward query plans with bounded relation traversal;
- deterministic, read-only local-ledger query execution with query-lens hindsight labels;
- deterministic Bayesian, graph, and temporal reference diagnostics;
- explicit fitter admissibility, invalidity, and abstention;
- digest-bound execution receipts and partial multi-fitter run preservation;
- method-specific disagreement views with no compulsory consensus;
- unresolved hypotheses with explicit claim polarity bindings;
- acyclic, assumption-bound belief edges;
- dependency-aware categorical belief revisions with no probability claim;
- assumption- and intervention-bound scenario trees with a required unknown branch;
- structural branch-antecedent evaluation without likelihoods or simulated trajectories;
- deterministic read-only workbench projection over one replayed local ledger;
- loopback-only static asset workbench with no write endpoint;
- manual, ambiguity-bound candidate-observation plans;
- deterministic ordinal structural-discrimination ranking with ties and abstention;
- digest-bound discrimination receipts with collection and acquisition fixed off;
- preregistered numeric forecast-evaluation targets and metrics;
- ledger-recorded training cutoffs with post-cutoff input exclusion;
- evaluation-design fitter selection remains `NOT_SELECTED`; a separate baseline event does not
  register or select a fitter;
- one user-declared constant reference baseline frozen before forecast origin;
- no training observations used by the baseline and no learned or external model execution;
- baseline calibration and empirical validity fixed at `NOT_ESTABLISHED`;
- readback observer frames, observation-time window, and ledger-admission cutoff preregistered
  before forecast origin;
- deterministic exactly-one readback selection with explicit no-match and multiple-match
  abstention;
- mutually exclusive exclusion accounting with aggregation, ranking, and post-hoc selection
  prohibited;
- residual scoring fixed at `NOT_ENABLED`, with validity, weighting, future-admissibility, and
  learning updates fixed off;
- later manual-observation binding to an earlier scenario horizon;
- fail-closed forecast-baseline eligibility with digest-bound readback receipts;
- residual, validity, weighting, future-admissibility, and learning updates fixed off when no
  forecast baseline exists;
- append-only JSONL event persistence;
- deterministic asset-state replay;
- schema validation and fail-closed referential checks.

No live adapters, credentials, network acquisition, entity merge, automated claim
extraction, learned or external forecast model, external database, service deployment, or autonomous
action exists in this slice. Resolution assessments never mutate canonical entity identity. Claims,
relations, candidate dispositions, surfaces, and query plans are manually recorded epistemic
objects, not machine truth determinations. A cartographic result never establishes source coverage
or completeness, and execution cannot access the network. Reference fitter outputs are local
diagnostics with `NOT_ESTABLISHED` empirical validity, `NOT_CALIBRATED` uncertainty, and no model or
action authority. Belief states are categorical diagnostic signal balances,
not probabilities or truth determinations. Scenario interventions have `NOT_ESTABLISHED` causal
status, the unmodeled region cannot be removed, and scenario execution performs no fitter forecast,
likelihood assignment, trajectory simulation, prediction, or action.
The Phase 6 workbench is a local presentation and replay surface only. It binds to loopback,
refuses mutation methods, performs no authentication or remote service exposure, and does not add
scientific, operational, surveillance, targeting, or action authority.
The Phase 7 planner ranks only user-declared expected effects. It performs no source query,
acquisition, expected-information-gain calculation, probability calculation, feasibility
validation, source-independence validation, or collection recommendation with action authority.
Phase 8A records a readback only after one or more admitted observations fall strictly after the
bound scenario horizon. Because the current scenario runtime produces structural branch evaluation
rather than a forecast, the readback must remain `INELIGIBLE_NO_FORECAST_BASELINE`, residual must
remain `NOT_COMPUTED`, and all validity, weighting, future-admissibility, and learning updates remain
off. This prerequisite gate does not satisfy the full Phase 8 residual-loop exit condition.
Phase 8B adds only the missing evaluation-design prerequisite: one user-declared numeric target,
absolute-error metric, training cutoff, forecast origin, and post-cutoff exclusion policy recorded
before the scenario begins. It requires later readback observations to match that target, but keeps
fitter selection `NOT_SELECTED`, execution `NOT_STARTED`, prediction `NOT_PRODUCED`, and calibration
`NOT_ESTABLISHED`. It does not create a forecast-capable fitter or satisfy the Phase 8 exit condition.
Phase 8C adds one frozen `USER_DECLARED_CONSTANT` benchmark after design creation and before forecast
origin. It uses no training observations and records `PRODUCED_UNCALIBRATED_BASELINE`, while
calibration and empirical validity remain `NOT_ESTABLISHED`. Residual scoring stays `NOT_ENABLED`;
all validity, weighting, future-admissibility, and learning updates remain off. If this baseline is
present, the Phase 8A no-baseline readback command fails closed until a separate residual-scoring
contract exists. The benchmark is not an observation, evidence, calibrated model, or action signal.
Phase 8D adds a separate preregistered readback-selection plan after the baseline and before forecast
origin. It fixes eligible observer frames, an observation-time window strictly after the horizon,
and a ledger-admission cutoff. After the cutoff, the deterministic selector returns
`UNIQUE_MATCH_SELECTED`, `ABSTAINED_NO_MATCH`, or `ABSTAINED_MULTIPLE_MATCHES`. It never ranks,
aggregates, or chooses among multiple candidates. A unique selection still leaves unit equivalence
`USER_DECLARED_NOT_VERIFIED`, residual `NOT_COMPUTED`, scoring `NOT_ENABLED`, and every validity,
weighting, future-admissibility, and learning update off. It is a selection contract, not a scoring
contract or authority grant.

## Contract changes

- Keep schemas closed with `additionalProperties: false` unless an ADR opens a specific extension
  point.
- Add positive and negative tests with every contract change.
- Version breaking contract changes.
- Keep entity resolution candidates reversible and review-required until a later contract says
  otherwise.
- Never remove a failure, counterexample, invalid observation, or abstention to improve a demo.

## Validation

Run:

```shell
make check
```

Before reporting completion, include exact results and `git status --short --branch`.
