# ADR 0007: Read-Only Local Asset Workbench

- Status: Accepted for local reference implementation
- Date: 2026-08-23

## Context

READIN has replayable tracked assets, provenance-preserving observations, unresolved claims,
dependency ancestry, bounded cartography, heterogeneous fitter diagnostics, categorical belief
revisions, and non-predictive scenarios. Those structures are inspectable through JSON commands but
do not yet form a coherent operator workflow. Phase 6 needs an actual product surface without
opening live acquisition, network model execution, write authority, or service deployment.

Exposing the entire internal projection as a browser API would couple the interface to every domain
record and make epistemic boundaries difficult to verify. Adding a general application server or a
frontend framework would also expand the slice beyond its local inspection purpose.

## Decision

Add a closed presentation projection, static interface, and standard-library HTTP server.

- `readin.workbench.v0.1` is a compact read model derived deterministically from one replayed local
  ledger. It does not add or mutate epistemic records.
- The read model retains claim status, evidence dependency groups, observer-frame blind regions,
  aperture exclusions, fitter invalidity and abstention, lack of consensus, categorical belief
  interpretation, and the required unknown scenario branch.
- Every response carries `NO_AUTHORITY`; the projection fixes coverage, completeness, probability,
  prediction, trajectory, empirical-validity, and consensus ceilings.
- The HTTP server binds only to `localhost`, `127.0.0.1`, or `::1`. It has no connector, credential,
  collection, external model, or outbound-network facility.
- The browser API exposes one read endpoint, `GET /api/workbench`. Static assets are packaged with
  the Python distribution. POST, PUT, PATCH, and DELETE return `405 Method Not Allowed`.
- Browser controls are limited to catalog selection, local filtering, tab navigation, and replay
  refresh. No UI control can create, revise, run, merge, publish, target, or act.
- The workbench can be emitted as JSON with `show-workbench` or served locally with `workbench`.
- The presentation projection is tested directly as its Phase 6 contract. It introduces no new
  event type and therefore does not change the closed event schema.

## Consequences

An operator can now inspect the current shape of a tracked asset across frames, claims, evidence,
relations, fitters, beliefs, scenarios, and timeline while the most important epistemic limits
remain continuously visible. The UI is a deterministic local read-back, not a live intelligence
service or scientific validation surface.

This slice does not establish source coverage, completeness, claim truth, evidence independence,
entity identity, calibrated probability, fitter validity, causal identification, scenario
likelihood, simulated trajectory, forecast accuracy, operational readiness, surveillance
authority, targeting authority, or action authority. Deployment, authentication, live adapters,
write APIs, remote storage, and external model services require separate decisions and explicit
authorization.
