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

The initial slice is local-first and manual-input only:

- typed tracked-asset creation;
- observer-frame registration;
- immutable observation admission;
- append-only JSONL event persistence;
- deterministic asset-state replay;
- schema validation and fail-closed referential checks.

No live adapters, credentials, network acquisition, automated entity merge, claim extraction,
model inference, forecast, external database, service deployment, or autonomous action exists in
this slice.

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
