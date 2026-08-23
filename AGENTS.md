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

The Phase 0 through bounded Phase 4 slices are local-first and manual-input only:

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
- append-only JSONL event persistence;
- deterministic asset-state replay;
- schema validation and fail-closed referential checks.

No live adapters, credentials, network acquisition, entity merge, automated claim
extraction, external model service, forecast, external database, service deployment, or autonomous action
exists in this slice. Resolution assessments never mutate canonical entity identity. Claims,
relations, candidate dispositions, surfaces, and query plans are manually recorded epistemic
objects, not machine truth determinations. A cartographic result never establishes source coverage
or completeness, and execution cannot access the network. Reference fitter outputs are local
diagnostics with `NOT_ESTABLISHED` empirical validity, `NOT_CALIBRATED` uncertainty, no residual
readback, and no model or action authority.

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
