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

The current foundation, bounded Array, resolution, cartography, and multi-fitter slices implement
one local epistemic loop:

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

This slice uses manual, synthetic input only. Cartographic and fitter execution are read-only local
diagnostics; `coverage_state` remains `NOT_ESTABLISHED`, completeness is never claimed, and post-cutoff surface
definitions are labeled as hindsight in the query lens. Fitter empirical validity is
`NOT_ESTABLISHED`, residual readback is not performed, and the Bayesian output is explicitly a
diagnostic index rather than a truth probability. It performs no network collection, entity merging,
automated claim extraction, forecasting, targeting, or external action. A claim
remains unresolved even when evidence is linked, and repeated dependent evidence is never counted
as independent corroboration. Candidate resolution is review history only: it never performs a
canonical entity merge.

## Quick start

Install [uv](https://docs.astral.sh/uv/), then:

```shell
uv sync --dev
make check
make demo
```

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
```

Commands emit JSON so their identifiers can be captured by scripts. Run `uv run readin --help` for
the complete interface.

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
