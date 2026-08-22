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

## First executable slice

The current foundation implements one local epistemic loop:

1. Create a typed entity and start tracking it as an asset.
2. Register an observer frame.
3. Manifest an immutable source artifact with its digest and access policy.
4. Admit an immutable observation from that frame and artifact.
5. Append all changes to a schema-validated event ledger.
6. Replay the ledger into an inspectable asset view.

This slice uses manual, synthetic input only. It performs no network collection, entity merging,
claim extraction, model inference, prediction, targeting, or external action.

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
specified. They do not establish intelligence accuracy, source independence, scientific validity,
operational readiness, or action authority.

## License

Apache License 2.0.
