# READIN

READIN is a provenance-preserving, multi-frame intelligence environment for maintaining and
navigating evolving epistemic fields around entities of interest.

The durable object is a **tracked asset**: an organization, person, technology, program, concept,
location, event, market, publication, capability, narrative, or other typed entity whose observable
state is reconstructed over time.

READIN is not an OSINT scraper, a conventional knowledge graph, or a single-model research agent.
Every incoming datum is admitted as an observation produced from a bounded observer frame. Claims,
beliefs, forecasts, and model results remain separate from observations and from one another.

## Architecture boundary

```text
READIN
  tracked assets | collection | cartography | multi-fitters | scenarios | product surfaces
      |
Epistemic Array
  observations | claims | evidence | frames | provenance | dependency | disagreement
      |
OFS (optional)
  pinned conformance contracts | distributed execution | resource coordination
```

READIN remains useful without OFS. It will integrate with OFS only through accepted immutable
contracts and receipts; it does not redefine OFS Core.

## Current executable slice

The current foundation, bounded Array, resolution, cartography, multi-fitter, belief, scenario,
asset-workbench, discriminating-observation, forecast-evaluation design, frozen-baseline,
readback-selection, and residual-readback eligibility slices implement one local epistemic loop:

1. Create a typed entity and start tracking it as an asset.
2. Register an observer frame.
3. Manifest an immutable source artifact with its digest and access policy.
4. Admit an immutable observation from that frame and artifact.
5. Declare evidence ancestry so repeated derivatives cannot masquerade as independent support.
6. Create a typed, unresolved claim derived from admitted observations.
7. Link supporting, challenging, or contextual evidence with separate warrant, appraisal, and
   strength fields.
8. Create a typed entity relation backed by a claim.
9. Append all changes to a schema-validated event ledger.
10. Replay the ledger into an inspectable asset view or a hindsight-labeled historical timeline.
11. Record a possible same-entity candidate with supporting and challenging signals.
12. Append manual assessments without merging or mutating either entity.
13. Register an observer-frame cartographic surface with explicit blind-region state.
14. Persist a backward query plan with a selected surface, traversal bound, and reconstruction mode.
15. Execute that plan deterministically against the local ledger while reporting aperture exclusions
    and hindsight introduced by the query lens.
16. Register deterministic Bayesian, graph, and temporal diagnostic fitters with closed
    admissibility and validity boundaries.
17. Execute one cartographic query across those heterogeneous fitters with digest-bound receipts.
18. Retain method-specific outputs, invalidity, abstention, and partial run groups without averaging
    them into consensus.
19. Create unresolved hypotheses with explicit claim polarity bindings.
20. Connect hypotheses through assumption-bound directed edges while rejecting cycles.
21. Produce a dependency-aware categorical belief revision with a digest-bound receipt.
22. Create an assumption- and intervention-bound scenario tree with a required unknown branch.
23. Evaluate branch antecedents against one immutable belief revision without assigning likelihoods
    or simulating trajectories.
24. Project the replayed ledger into a compact operator view that retains claim status, dependency
    ancestry, blind regions, fitter invalidity, categorical belief state, and unknown branches.
25. Inspect that projection through a loopback-only, read-only browser workbench.
26. Declare manual candidate observations against a specified ambiguity, belief revision, and
    cartographic blind-region context.
27. Rank only their user-supplied structural effects on competing hypotheses, preserving ties and
    abstaining when no candidate discriminates.
28. Inspect the result as a “Next observation” view without querying, acquiring, or contacting a
    source.
29. Predeclare one numeric forecast-evaluation target, metric, training cutoff, forecast origin, and
    post-cutoff exclusion policy before the scenario horizon begins.
30. Keep fitter selection `NOT_SELECTED`; optionally freeze one separate user-declared constant
    benchmark after design creation and before forecast origin.
31. Preserve that benchmark as `PRODUCED_UNCALIBRATED_BASELINE`, with no training observations,
    calibration, empirical validity, residual scoring, or learning update.
32. Before forecast origin, predeclare eligible readback observer frames, an observed-time window
    strictly after the horizon, and a ledger-admission cutoff.
33. Admit later manual observations while preserving both their observed times and ledger-admission
    times.
34. After the cutoff, deterministically select exactly one compatible readback or abstain on zero or
    multiple matches without ranking, aggregation, or post-hoc choice.
35. Retain the digest-bound selection with unit equivalence unverified and no residual,
    fitter-validity, weighting, future-admissibility, or learning update.
36. In the separate no-baseline branch, bind a later observation to the earlier scenario run and
    retain the existing ineligible-baseline abstention.

This slice uses manual, synthetic input only. Cartographic, fitter, belief, and scenario execution is
local and deterministic; the workbench has no write endpoint and refuses non-loopback bindings.
`coverage_state` remains `NOT_ESTABLISHED`, completeness is never claimed,
and post-cutoff surface definitions are labeled as hindsight in the query lens. Fitter and scenario
empirical validity is `NOT_ESTABLISHED`. Phase 8B predeclares an evaluation design and temporal
leakage boundary, but does not select a fitter, execute a forecast, or produce a prediction. Its
target and metric remain user-declared and unvalidated. Phase 8A retains a later observation
readback, but the
reference scenario run has `prediction_state: NOT_REQUESTED`; therefore the forecast baseline is
`NOT_AVAILABLE`, residual is `NOT_COMPUTED`, validity and weighting updates are `NOT_APPLIED`, and
learning is `NOT_STARTED`. Together these are prerequisite gates, not the full Phase 8 residual
loop. Phase 8C can instead freeze one finite, user-declared constant before forecast origin. The
reference method uses no training observations and records `PRODUCED_UNCALIBRATED_BASELINE`, while
calibration and empirical validity remain `NOT_ESTABLISHED`. Residual scoring remains `NOT_ENABLED`;
when this baseline exists, the Phase 8A no-baseline readback command fails closed until a separate
scoring contract is implemented. Phase 8D preregisters a deterministic exactly-one readback
aperture. It separates observation time from ledger-admission time and abstains on zero or multiple
compatible observations. Even one selected observation remains `NOT_COMPUTED` for residuals and
cannot update validity or learning. Bayesian and belief outputs are explicitly diagnostic rather than
truth probabilities.
Scenario branches are
user-defined conditional structures: likelihood is `NOT_COMPUTED`, trajectories are
`NOT_SIMULATED`, and the unknown/unmodeled region remains visible. Phase 7 ranking is an ordinal
structural heuristic over user-supplied, unvalidated expected effects; it does not compute expected
information gain, source feasibility, source independence, or probabilities. The slice performs no
network collection, entity merging, automated claim extraction, learned or external forecasting,
targeting, or external action.
A claim remains unresolved even when evidence is linked, and repeated dependent evidence is never
counted as independent corroboration. Candidate resolution is review history only: it never performs
a canonical entity merge.

## Quick start

Install [uv](https://docs.astral.sh/uv/), then:

```shell
uv sync --dev
make check
make demo
make workbench
```

`make workbench` creates the closed synthetic Phase 8D ledger in a temporary directory and serves
the bounded workbench at `http://127.0.0.1:4173`. It takes no external action and removes the
temporary ledger when stopped.

Or create a local ledger manually:

```shell
uv run readin init --ledger .readin/events.jsonl
uv run readin create-entity --ledger .readin/events.jsonl \
  --type Organization --name "Example Research Cooperative"
uv run readin register-frame --ledger .readin/events.jsonl \
  --name "Public filings" --class regulatory_filing
uv run readin show-timeline --ledger .readin/events.jsonl \
  --asset <entity-id> --mode AS_KNOWN_THEN
uv run readin register-cartographic-surface --ledger .readin/events.jsonl \
  --name "Public filings" --description "Registered public-filing frames" \
  --frame <frame-id> --blind-region-state NOT_CHARACTERIZED
uv run readin plan-cartographic-query --ledger .readin/events.jsonl \
  --asset <entity-id> --surface <surface-id> --mode AS_KNOWN_THEN \
  --epistemic-cutoff <ISO-8601-cutoff-at-or-after-tracking>
uv run readin run-cartographic-query --ledger .readin/events.jsonl --query <query-id>
uv run readin register-reference-fitter --ledger .readin/events.jsonl \
  --class BAYESIAN
uv run readin run-fitters --ledger .readin/events.jsonl \
  --query <query-id> --fitter <fitter-id>
uv run readin show-multi-fitter-run --ledger .readin/events.jsonl \
  --run-group <run-group-id>
uv run readin show-belief-revision --ledger .readin/events.jsonl \
  --revision <belief-revision-id>
uv run readin show-scenario-run --ledger .readin/events.jsonl \
  --run <scenario-run-id>
uv run readin show-discrimination-run --ledger .readin/events.jsonl \
  --run <discrimination-run-id>
uv run readin create-forecast-evaluation-design --ledger .readin/events.jsonl \
  --scenario <scenario-id> --name "Evaluation design" \
  --observation-type <later-observation-type> --field <numeric-field> \
  --unit <unit> --training-cutoff <ISO-8601-cutoff-before-forecast-origin>
uv run readin show-forecast-evaluation-design --ledger .readin/events.jsonl \
  --design <forecast-evaluation-design-id>
# Phase 8C baseline branch:
uv run readin run-forecast-baseline --ledger .readin/events.jsonl \
  --design <forecast-evaluation-design-id> --value <finite-number> \
  --occurred-at <ISO-8601-time-before-forecast-origin>
uv run readin show-forecast-baseline --ledger .readin/events.jsonl \
  --baseline <forecast-baseline-id>
# Phase 8D readback selection branch, preregistered before forecast origin:
uv run readin create-readback-selection-plan --ledger .readin/events.jsonl \
  --baseline <forecast-baseline-id> --name "Readback aperture" \
  --frame <observer-frame-id> --observed-window-end <ISO-8601-time-after-horizon> \
  --ledger-admission-cutoff <ISO-8601-time-at-or-after-window-end> \
  --occurred-at <ISO-8601-time-before-forecast-origin>
uv run readin run-readback-selection --ledger .readin/events.jsonl \
  --plan <readback-selection-plan-id> \
  --occurred-at <ISO-8601-time-at-or-after-admission-cutoff>
uv run readin show-readback-selection-run --ledger .readin/events.jsonl \
  --run <readback-selection-run-id>
# Phase 8A no-baseline branch only; omit run-forecast-baseline:
uv run readin run-residual-readback --ledger .readin/events.jsonl \
  --scenario-run <scenario-run-id> --observation <later-observation-id>
uv run readin show-residual-readback --ledger .readin/events.jsonl \
  --readback <readback-id>
uv run readin show-workbench --ledger .readin/events.jsonl --asset <entity-id>
uv run readin workbench --ledger .readin/events.jsonl --host 127.0.0.1 --port 4173
```

Data commands emit JSON so their identifiers can be captured by scripts; `workbench` starts the
local server until interrupted. Run `uv run readin --help` for the complete interface.

## Governing rules

- Observation does not imply fact.
- Repetition does not imply independent support.
- Missing does not imply absent.
- Translation is lossy until demonstrated otherwise.
- Fitter disagreement is retained rather than averaged away.
- Every READIN-originated event declares `NO_AUTHORITY`.
- Collection involving people is limited to public, licensed, user-owned, or otherwise authorized
  sources.

See [Architecture](docs/architecture-v0.1.md), [Contributing](CONTRIBUTING.md), and
[Security](SECURITY.md).

## Status

Pre-alpha. Contract conformance and local tests establish only that this reference slice behaves as
specified. They do not establish claim truth, intelligence accuracy, source independence,
scientific validity, operational readiness, or action authority.

## License

Apache License 2.0.
