# READIN Architecture v0.1

**Status:** Initial implementation boundary
**System class:** Open-source multi-frame intelligence adapter and multi-fitter environment

## Product thesis

READIN organizes intelligence around persistent epistemic objects rather than documents, feeds,
searches, embeddings, chat sessions, or model outputs. Adding an entity creates a tracked asset with
an evolving, replayable epistemic field.

For an entity `e`, the intended state is:

```text
E_e(t) = (observations, claims, relations, hypotheses, beliefs,
          disagreements, uncertainties, aperture)
```

The current implementation opens the entity, tracking, frame, evidence-manifest, observation,
dependency, claim, evidence-link, relation, historical reconstruction, and reversible candidate
resolution layers, plus bounded cartographic, multi-fitter, belief, scenario,
discriminating-observation, forecast-evaluation design, frozen-baseline, readback-selection, and
descriptive-reference-residual, validity-update eligibility, and residual-readback eligibility
layers, plus prospective forecast-fitter specification registration.
These layers remain separate:
an observation is never silently promoted into a claim or belief, linked evidence
never resolves a claim by itself, a selected surface never becomes a completeness claim, a fitter
result never becomes evidence or model authority, a categorical belief revision never becomes a
truth probability, a scenario branch never becomes a forecast, a ranked observation candidate
never becomes collection authority, and descriptive residual arithmetic never becomes forecast
validation or a validity update without a separately opened evidence and update contract.

## Ownership boundary

| Layer | Owns | Does not own |
| --- | --- | --- |
| READIN | Asset lifecycle, adapters, persistence, intelligence queries, fitters, scenarios, UI | OFS Core semantics or authority |
| Epistemic Array | Frames, observations, claims, evidence, warrants, dependency, disagreement, blind regions | Application workflow or collection credentials |
| OFS, optional | Pinned conformance and execution resources | READIN tenancy, persistence, workflow, or action authority |

## Current event model

The ledger supports thirty events:

- `entity.created`
- `asset.tracking_started`
- `observer_frame.registered`
- `evidence.manifested`
- `observation.admitted`
- `evidence.dependency_declared`
- `claim.created`
- `evidence.linked`
- `relation.created`
- `entity.resolution_candidate_recorded`
- `entity.resolution_candidate_assessed`
- `cartography.surface_registered`
- `cartography.query_planned`
- `fitter.registered`
- `fitter.run_completed`
- `hypothesis.created`
- `belief.edge_created`
- `belief.revision_completed`
- `scenario.created`
- `scenario.run_completed`
- `collection.discrimination_plan_created`
- `collection.discrimination_run_completed`
- `forecast.evaluation_design_created`
- `forecast.baseline_completed`
- `forecast.readback_selection_plan_created`
- `forecast.readback_selection_completed`
- `forecast.residual_computed`
- `forecast.validity_update_assessed`
- `forecast.fitter_specification_registered`
- `residual.readback_completed`

Every event is append-only, schema-validated, timestamped, uniquely identified, and marked
`NO_AUTHORITY`. Projection fails closed when an asset or frame is unknown, an identifier is reused,
or a ledger record does not validate.

```text
entity.created --> asset.tracking_started -------------------------------+
                                                                         |
observer_frame.registered ----------------+                              |
                                          |                              |
evidence.manifested ----------------------+--> observation.admitted -----+
        |                                           |                    |
        +--> evidence.dependency_declared           +--> claim.created --+
                                                              |          |
evidence.manifested --------------------------> evidence.linked+          |
                                                              |          v
entity.created ---------------------------------> relation.created --> replay
                                                                         |
                                                           asset view + timeline

observer_frame.registered --> cartography.surface_registered
                                          |
tracked asset ----------------------------+--> cartography.query_planned
                                                     |
                                                     v
                                      read-only local-ledger traversal

cartography.query_planned --> fitter.run_completed --> receipt + result/abstention
                                  ^
                                  |
                         fitter.registered

claim.created --> hypothesis.created --> belief.revision_completed
                         |                         |
                         +--> belief.edge_created-+
                                                   |
                                                   v
                         scenario.created --> scenario.run_completed
                                                   |
cartography.query_planned + belief.revision_completed
                         --> collection.discrimination_plan_created
                         --> collection.discrimination_run_completed

scenario.run_completed + later observation.admitted
                         --> residual.readback_completed
                         --> eligibility abstention when no forecast baseline exists

scenario.created --> forecast.evaluation_design_created
                  --> predeclared target + leakage boundary
                  --> forecast.baseline_completed
                  --> frozen uncalibrated constant; residual scoring disabled
                  --> forecast.readback_selection_plan_created
later observation.admitted + admission cutoff
                  --> forecast.readback_selection_completed
                  --> exactly one selected or explicit abstention
                  --> forecast.residual_computed
                  --> descriptive arithmetic only; no validity or learning update
                  --> forecast.validity_update_assessed
                  --> explicit abstention; six blockers retained and no update applied
                  --> forecast.fitter_specification_registered
                  --> future-only specification; no training, execution, or retroactive effect
```

Candidate resolution is a sidecar to entity identity, not an entity mutation. A candidate records
`POSSIBLE_SAME_ENTITY` plus polarity-preserving signals. Manual assessments form an append-only,
linearly superseded history. `automatic_merge: false` and `merge_state: NOT_MERGED` are contract
constants even for `CONFIRMED_MATCH_NOT_MERGED`; no event in this slice can merge entities.
Signal verification is a separate axis: asserted, reference-validated, or exact entity-record
validated. A validated shared field supports candidacy only and never establishes identity.

## Bounded cartography

A cartographic surface is an explicitly named composite of one or more registered observer frames.
Its blind-region state is either `DECLARED`, with at least one stated blind region, or
`NOT_CHARACTERIZED`, with no implied knowledge of what is missing. Surface coverage is always
`NOT_ESTABLISHED` in this slice.

A cartographic query plan is persistent and backward-only. It binds one tracked asset to one or more
surfaces, a reconstruction mode and optional epistemic cutoff, and a relation-traversal limit of zero
to three hops. Observations, claims, evidence manifests, and dependency ancestry are always retained;
relations may be disabled. Missingness and conflict policies are fixed to `PRESERVE`, prediction is
`NOT_REQUESTED`, and execution is `PLANNED_READ_ONLY`.

Execution deterministically traverses the already-admitted local ledger. An observation is selected
only when its observer frame is on the chosen surface and it concerns a visited entity. A claim is
included only when at least one of its derivation observations is selected. A relation can extend the
traversal only when it originates at the current frontier and cites a selected claim. Evidence
dependency closure remains visible so derivatives do not appear independent.

For `AS_KNOWN_THEN`, the epistemic cutoff bounds ledger data. Surface and plan definitions form a
separate query lens; when either was recorded to the ledger after the cutoff, the result marks that
lens as hindsight using ledger-recorded time rather than a backdatable domain timestamp. Results
report excluded asset observations, known and uncharacterized blind regions, `NOT_ESTABLISHED`
coverage, unevaluated surface validity conditions, no completeness claim, no network access, and
`NO_AUTHORITY`.

## Bounded multi-fitter runtime

Phase 4 treats a fitter as an executable analytical observer over one immutable cartographic query
result. The initial runtime registers three deterministic reference diagnostics:

- a Bayesian diagnostic that groups dependent evidence before producing a Beta support index, which
  is explicitly not a truth probability;
- a graph diagnostic that reports relation topology without inferring influence, importance, or
  causality;
- a temporal diagnostic that reports observation cadence without inferring a trend, latent state,
  regime, trajectory, or forecast.

Every descriptor binds a versioned implementation digest, target metric, input/output contracts,
admissibility rules, and declared invalid conditions. Empirical validity remains `NOT_ESTABLISHED`
and is limited to the closed synthetic ledger. Bayesian execution requires exactly one claim and
declared dependency groups. Graph execution abstains when relations are absent. Temporal execution
is invalid when an `AS_KNOWN_THEN` input uses a hindsight-defined query lens.

Each completed run records the full requested fitter set, input state version, canonical input
digest, included and excluded identifiers, fitter implementation digest, assumptions, outcome
digest, and non-authority policy. Interrupted appends remain visible as `PARTIAL` run groups with
their missing fitters; retained results are never deleted to improve the demo.

The group view preserves `FIT`, `ABSTAINED`, and `INVALID` outcomes and labels method-specific
outputs as incommensurate when their target metrics differ. Consensus is `NOT_COMPUTED`, no fitter
is privileged, and no averaging or weighting is performed. Residuals remain `NOT_AVAILABLE`,
uncertainty remains `NOT_CALIBRATED`, prediction is `NOT_REQUESTED`, and all outputs remain
`NO_AUTHORITY`.

## Bounded belief and scenario runtime

Phase 5 introduces unresolved hypotheses, directed belief edges, categorical belief revisions, and
conditional scenario trees. A hypothesis explicitly binds zero or more claims as supporting or
challenging its proposition. A belief edge states only what signal should be introduced if its
source hypothesis is support-leading; it carries an assumption and `NOT_ESTABLISHED` causal status.
The projection rejects self-edges, cross-asset edges, duplicate directed pairs, and cycles.

Belief execution first groups evidence links by declared dependency ancestry, preventing repeated
derivatives from becoming independent support units. It then propagates categorical states in
topological order: `SUPPORT_LEADING`, `CHALLENGE_LEADING`, `CONFLICTED`, or `UNRESOLVED`. These are
diagnostic signal balances, not probabilities that hypotheses are true. Every revision binds its
asset state version, complete selected graph, claim links, dependency declarations, executable
implementation digest, and result digest. Probability is `NOT_COMPUTED`, uncertainty is
`NOT_CALIBRATED`, empirical validity is `NOT_ESTABLISHED`, and prediction is `NOT_REQUESTED`.

A scenario binds one immutable belief revision, explicit user-supplied assumptions and
interventions, a finite horizon, target entities, and a tree of conditional branches. Interventions
retain `NOT_ESTABLISHED` causal status. Exactly one root branch represents the unknown/unmodeled
region and cannot parent declared outcomes. Declared branch depth is bounded to four.

Scenario execution evaluates only whether each branch antecedent matches the bound categorical
revision and whether its parent matched. It does not run the Phase 4 diagnostics as forecast models,
assign likelihoods, simulate trajectories, identify causes, or predict outcomes. Results therefore
retain `NOT_RUN_NO_FORECAST_CAPABLE_FITTER`, `NOT_COMPUTED` likelihood,
`NOT_SIMULATED` trajectory, `NOT_REQUESTED` prediction, `NOT_ESTABLISHED` empirical validity, and
`NO_AUTHORITY`. Digest-bound receipts make structural evaluation replayable without promoting it to
a forecast.

## Bounded discriminating-observation planning

Phase 7 implements the architecture roadmap's narrow exit condition: identify which manually
declared observation would be most useful for resolving a specified ambiguity. It does not open the
broader active-collection surface.

A plan binds one tracked asset, one immutable belief revision, one persisted cartographic query,
two or more hypotheses present in that revision, and one or more manual observation candidates.
Each candidate names an observer frame, question, observation type, effort label, optional known
blind-region targets, and user-supplied expected hypothesis effects. Projection rejects unknown or
cross-asset bindings, blind targets absent from the query, incomplete effect matrices, duplicate
candidates, observer-frame access drift, and repeated execution.

The reference ranking is structural and ordinal. It counts how many declared outcomes and
hypothesis pairs are separated, gives greater ordinal separation to opposite support/challenge
effects than to a directional effect versus no effect, and uses declared blind-region alignment
only as the final structural key. Equal candidates retain equal rank; if no candidate separates any target
hypotheses, the runtime abstains. It does not assign outcome probabilities, compute expected
information gain, validate feasibility, establish source independence, or claim empirical utility.

The execution receipt binds the plan, belief revision, query result, candidate and hypothesis ids,
implementation, and outcome digest. Network access is false, collection remains `NOT_STARTED`,
acquisition remains `NOT_ATTEMPTED`, source independence remains `NOT_ESTABLISHED`, and every result
retains `NO_AUTHORITY`.

## Bounded forecast design, residual, validity eligibility, and prospective fitter specification

Phase 8A implements the prerequisite gate for the architecture roadmap's residual loop. A readback
binds one completed scenario run to one or more already-admitted observations concerning the same
asset. Every selected observation must be strictly later than the scenario horizon. The receipt
binds the scenario, scenario run, admitted observations, evidence manifests, observer frames,
asset state version, predeclared forecast-evaluation design, reference implementation, and outcome
digests.

Phase 8B adds the preceding evaluation-design gate. Before the scenario forecast origin, a user can
predeclare one numeric observation target, unit, absolute-error metric, residual sign convention,
training cutoff, horizon, and post-cutoff exclusion policy. Projection derives the forecast origin
and horizon from the bound scenario, requires the training cutoff not to follow design creation,
and allows only one design per scenario. The target and metric remain
`USER_DECLARED_NOT_VALIDATED` / `PREDECLARED_NOT_VALIDATED`. Fitter selection is `NOT_SELECTED`,
forecast execution is `NOT_STARTED`, prediction is `NOT_PRODUCED`, and calibration is
`NOT_ESTABLISHED`.

Phase 8C adds a separate frozen reference baseline. After design creation and strictly before
forecast origin, a user can declare one finite constant numeric value. The local deterministic
runtime copies the target, unit, field path, origin, horizon, cutoff, and leakage policy from the
design and binds them to a replay-verifiable receipt. The reference method selects no training
observations and produces only `PRODUCED_UNCALIBRATED_BASELINE`; calibration and empirical validity
remain `NOT_ESTABLISHED`. Residual scoring is `NOT_ENABLED`, and validity, weighting,
future-admissibility, and learning updates remain off. The constant is a benchmark, not an
observation, evidence item, calibrated model, or world-state claim.

Phase 8D adds the missing selection boundary between later observations and any future residual
arithmetic. After the baseline is frozen and still before forecast origin, a plan fixes the eligible
observer-frame identifiers, an observed-time window that begins strictly after the horizon, and a
ledger-admission cutoff at or after the window end. Execution occurs only after that cutoff and
classifies every observation concerning the asset by ledger admission, observed time, target type,
observer frame, and finite numeric target compatibility. The classifications are mutually
exclusive and retained in the result.

The selection cardinality is `EXACTLY_ONE`. One candidate produces `UNIQUE_MATCH_SELECTED`; zero
produces `ABSTAINED_NO_MATCH`; more than one produces `ABSTAINED_MULTIPLE_MATCHES`. Aggregation,
ranking, and post-hoc choice are prohibited. The receipt binds the plan, baseline, design, scenario,
eligible frames, complete classified input snapshot, implementation, and outcome. Because admitted
observations do not yet carry a separately validated unit field, unit equivalence remains
`USER_DECLARED_NOT_VERIFIED`. Selection does not compute a residual or enable scoring, calibration,
validity, weighting, admissibility, learning, collection, or action authority.

Phase 8E opens a separate, narrow arithmetic contract only after a Phase 8D run records
`UNIQUE_MATCH_SELECTED`. The deterministic runtime binds the selection run and plan, frozen
baseline, evaluation design, scenario, selected observation, observer frame, and evidence manifest.
It computes signed residual as observed minus predicted and absolute error as the absolute value of
that residual. The receipt binds every input digest, the exact reference implementation, and the
outcome digest. Replay recomputes the full snapshot and arithmetic and rejects input drift,
tampering, abstained selection, or a second residual for the same selection run.

The result is fixed to `sample_count: 1`, `COMPUTED_DESCRIPTIVE_REFERENCE_ONLY`, and
`NOT_ESTIMATED_SINGLE_READBACK`. Because observations do not carry an independently validated unit
binding, unit equivalence remains `USER_DECLARED_NOT_VERIFIED`. Calibration and empirical validity
remain `NOT_ESTABLISHED`; validity, weighting, and future-admissibility updates remain
`NOT_APPLIED`; learning remains `NOT_STARTED`. Network access is false and authority remains
`NO_AUTHORITY`. The number is a descriptive error for an uncalibrated reference constant, not a
forecast-skill estimate or model-validity claim.

Phase 8F adds a separate eligibility assessment after that residual. The runtime binds the residual,
readback selection, frozen baseline, evaluation design, scenario, asset state, reference
implementation, and outcome to a replay-verifiable receipt. It records exactly six blockers:
`NO_REGISTERED_FORECAST_FITTER`, `REFERENCE_BASELINE_NOT_TRAINED_MODEL`, `SINGLE_READBACK_ONLY`,
`UNIT_EQUIVALENCE_NOT_VERIFIED`, `NO_PREDECLARED_VALIDATION_CORPUS`, and
`UNCERTAINTY_NOT_ESTIMATED`. The resulting eligibility and decision are fixed to
`INELIGIBLE_VALIDITY_UPDATE` and `ABSTAINED`; `target_fitter_id` is null, and validity, weighting,
future-admissibility, and learning updates remain off. Replay rejects identity drift, receipt or
outcome tampering, an unsupported residual boundary, or a second assessment for the same residual.
This gate makes the stop condition inspectable; it does not establish model invalidity, forecast
validation, or authority.

Phase 8G registers one typed forecast-fitter specification after the historical assessment. The
specification declares a numeric target, one or more numeric pre-origin features, a linear-regression
model family, a squared-error objective, ledger-recorded temporal leakage basis, required temporal
split and negative controls, exact unit binding, and required point-prediction and uncertainty
outputs. These are contracts, not implemented capabilities. Training data remains `NOT_SELECTED`,
implementation `NOT_PROVIDED`, training `NOT_STARTED`, selection `NOT_SELECTED`, execution
`NOT_ENABLED`, prediction `NOT_PRODUCED`, validation corpus `NOT_PREDECLARED`, and empirical
validity `NOT_ESTABLISHED`. Applicability is `FUTURE_FORECASTS_ONLY`; retroactive application is
`PROHIBITED`, so the Phase 8F assessment and its no-fitter blocker remain historically unchanged.

Later readback observations must match the predeclared observation type and contain a numeric value
at the declared structured-field path. The receipt binds the complete evaluation design. These
checks establish target compatibility and temporal order only; they do not establish that any
prediction exists.

In the Phase 8A no-baseline branch, the current scenario runtime performs conditional branch evaluation with
`prediction_state: NOT_REQUESTED`; it does not produce a forecast baseline. The eligibility
algorithm therefore records `INELIGIBLE_NO_FORECAST_BASELINE`, retains the readback, and fixes the
residual to `NOT_COMPUTED`. Fitter-validity, weighting, and future-admissibility updates remain
`NOT_APPLIED`; learning remains `NOT_STARTED`. Projection recomputes the complete binding and rejects
tampered receipts, non-later observations, cross-asset observations, missing inputs, or a second
readback for the same scenario run.

The Phase 8E baseline-selection-residual branch and the Phase 8A no-baseline readback branch are
deliberately separate. If a frozen baseline exists, the Phase 8A readback command rejects execution.
Phase 8E arithmetic is reached only through the preregistered Phase 8D selector and never through the
no-baseline path. This prevents READIN from incorrectly recording
`INELIGIBLE_NO_FORECAST_BASELINE` or manufacturing a residual from an unsupported update path.

These slices do not satisfy the full Phase 8 exit condition. No trained or calibrated
forecast-capable fitter, validation corpus, uncertainty estimate, validity update, weighting update,
admissibility update, or empirical learning exists. The only computed residual is one descriptive
comparison against an uncalibrated user-declared constant. The workbench Readback tab presents the
frozen baseline, preregistered selection or abstention, descriptive arithmetic when eligible, the
validity-update abstention, or the no-baseline state, with no write control, network access,
collection, or action authority. Phase 8F makes this stop condition executable; it does not open an
update path. Phase 8G adds only a prospective fitter specification; no implementation, training,
future-design selection, forecast execution, or model evidence is present.

Claims are created with `epistemic_status: unresolved`. An evidence link records role or polarity,
dependency group, warrant, appraisal, and strength as separate axes. Strength is `UNASSESSED` until
an appraisal is completed. A `derives` link must name an artifact used by one of the claim's cited
observations. Relations have `UNASSESSED` confidence, every cited claim must connect the declared
source and target, and causal relations must be written explicitly as the provisional pair `CAUSES?`
and `CAUSAL_HYPOTHESIS`.

Evidence dependency declarations form an acyclic ancestry graph. A link may name a dependency group
only when its artifact is a declared member of that group. The projection reports dependent evidence
without claiming that ungrouped artifacts are independent. Observation-level dependency-group tags
are accepted only after the group has been declared and only for member artifacts. Manifest-based
verification is limited to derivative relationships bound by the descendant manifest.

## Historical reconstruction

Every asset-relevant event advances an explicit epistemic state version. Timeline queries expose two
non-interchangeable modes:

- `AS_KNOWN_THEN` excludes events recorded after an epistemic cutoff.
- `AS_RECONSTRUCTED_NOW` includes later-recorded events and marks them as hindsight.

The default is `AS_KNOWN_THEN`. Effective time and ledger-recorded time remain separate so later
knowledge cannot be silently inserted into a historical view. Event `occurred_at` values must be
non-decreasing in ledger order; this prevents a later append from being replayed as an earlier
admission. This is a local chronology invariant, not an externally trusted timestamp or
cryptographic time attestation.

## Persistence boundary

The initial reference store is a local POSIX JSONL ledger. Writes are locked, flushed, and synced.
The representation is intentionally simple enough to inspect and replay. It is not yet a distributed
event log, database, or service.

Raw source artifacts are represented by immutable evidence manifests with SHA-256 identity, media
type, byte size, source, license, access policy, transformations, and derivative references. Binary
artifact storage and live acquisition are later gated work.

## Planned slices

1. **Phase 0 foundation** — tracked assets, frames, evidence manifests, observations, and event
   replay. *(implemented)*
2. **Phase 1 bounded Array** — unresolved claims, relations, evidence links, dependency ancestry,
   asset versions, and hindsight-labeled reconstruction. *(implemented)*
3. **Phase 2 candidate resolution** — reversible entity candidates and manual assessments; no
   merge. *(implemented)*
4. **Phase 3 bounded cartography** — observer-frame surfaces, explicit blind regions, persistent
   backward query plans, and deterministic local traversal. *(implemented)*
5. **Phase 4 multi-fitter runtime** — bounded fitter inputs, digest-bound receipts, explicit
   admissibility/invalidity, partial groups, and preserved disagreement. *(implemented)*
6. **Phase 5 scenario and belief engine** — dependency-aware categorical revisions and conditional
   branches without destiny claims. *(implemented)*
7. **Phase 6 asset workbench** — dense operator interface over the inspectable epistemic field,
   using a compact deterministic read model and loopback-only read server. *(implemented)*
8. **Phase 7 discriminating-observation planning** — manual candidate observations, query-bound
   blind-region targets, ordinal structural ranking, ties, abstention, and no acquisition.
   *(implemented)*
9. **Phase 8 residual loop** — bind later observations to prior forecasts, compute residuals, and
   update fitter validity or weighting only when supported. *(Phase 8A readback eligibility and
   Phase 8B evaluation-design prerequisites, Phase 8C frozen constant baseline, Phase 8D
   preregistered exactly-one readback selection, and Phase 8E one-sample descriptive reference
   residual, plus Phase 8F replay-verifiable validity-update abstention implemented; trained or
   calibrated forecast models are not implemented. Phase 8G prospective fitter specification is
   also implemented, while training, future-design selection, validation-corpus scoring,
   uncertainty estimation, and updates remain unimplemented.)*

Each slice requires its own contract, positive and negative fixtures, validation path, claim ceiling,
and stop conditions.
