# ADR 0004: Bounded Backward Cartography Over the Local Ledger

- Status: Accepted for local reference implementation
- Date: 2026-08-22

## Context

READIN needs to reconstruct what is locally observable about a tracked asset through selected
observer frames without implying that the selected frames cover the asset, that missing data is
absence, or that a present-day analytical lens existed at a historical cutoff. A network search or
forward prediction would introduce acquisition and model boundaries that are not open in this slice.

## Decision

Add two closed events: `cartography.surface_registered` and `cartography.query_planned`.

- A surface is a named composite of registered observer frames.
- Its blind-region state is either declared with one or more regions, or explicitly not
  characterized. Coverage remains `NOT_ESTABLISHED` and completeness is never claimed.
- Surface validity conditions are retained but remain `NOT_EVALUATED` by this local traversal.
- A query plan is backward-only, binds one tracked asset to registered surfaces, and records a
  reconstruction mode plus an optional epistemic cutoff.
- Relation traversal is optional and bounded to zero through three hops. Claims extend a traversal
  only when they derive from an observation selected by the surface.
- Observations, unresolved claims, evidence links, manifests, and evidence-dependency ancestry are
  preserved. Missingness and conflicts are not resolved by query execution.
- `AS_KNOWN_THEN` bounds ledger data at the cutoff. Surface or plan definitions recorded to the
  ledger after the cutoff are separately labeled as hindsight in the query lens using ledger time,
  not a backdatable domain timestamp.
- Execution is a deterministic read-only projection of the local immutable ledger. It performs no
  network access and writes no execution event.
- Prediction is `NOT_REQUESTED`; all events and views remain `NO_AUTHORITY`.

## Consequences

READIN can now run an auditable backward traversal across explicitly bounded observer-frame surfaces
and report what the aperture excludes. It cannot claim collection coverage, infer that missing
observations are absent facts, search external sources, rank entities, predict trajectories, run a
fitter, merge identities, or authorize action.

Live acquisition, forward simulation, fitter execution, or external action each require a separate
versioned contract, validation path, negative fixtures, and authority review.
