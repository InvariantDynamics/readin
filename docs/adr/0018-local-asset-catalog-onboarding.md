# ADR 0018: Local asset-catalog onboarding

## Status

Accepted for the first operational onboarding slice after the H0 public-repository case.

## Context

READIN can now prove one exact-target, credential-free public repository acquisition, but that does
not yet make the system usable against an operator's real world. Before social accounts, files,
domains, financial exports, mailboxes, calendars, or other asset classes can be connected, READIN
needs a control plane that separates four states:

- an asset exists and is in scope;
- a sensor or connector could eventually read something about it;
- an operator has supplied a local export or manual declaration; and
- a live authenticated source has been explicitly granted, reviewed, and admitted.

Collapsing those states into a login button would erase the current evidence and authority boundary.
It would also mix account credentials, source terms, incidental third-party personal data, retention
rules, and model interpretation before there is a stable contract.

## Decision

Add a closed local manifest contract:

```text
readin.asset-catalog-source.v0.1
```

The manifest declares self-owned, operator-administered, public self-presentation, or otherwise
authorized assets. It supports social accounts and other asset classes, but only as catalog entries
and connector intents. It does not connect to platforms, store credentials, run OAuth, scrape web
pages, traverse social graphs, monitor changes, create person targets, or perform external action.

The importer:

1. reads one owner-only local JSON manifest from outside Git checkouts;
2. validates the closed schema and cross-field connector states;
3. hashes the manifest bytes and manifests that digest as evidence;
4. registers one local-manifest observer frame;
5. creates deterministic tracked-asset entities for each declared asset;
6. admits one immutable `asset_catalog.user_declared_profile` observation per asset; and
7. records connector intent states such as `DECLARED_NOT_CONNECTED`,
   `EXPORT_IMPORT_READY`, `OAUTH_REQUIRED_NOT_REQUESTED`, and `LIVE_COLLECTION_DISABLED`.

The import command is:

```shell
uv run readin import-asset-catalog \
  --ledger "/path/outside/git/events.jsonl" \
  --manifest "/path/outside/git/source.json" \
  --attest
```

If the ledger does not exist, READIN creates it as an owner-only JSONL ledger. Re-importing an
unchanged manifest skips existing semantic objects rather than duplicating the catalog. A changed
manifest may add new source evidence and observations, but it does not grant collection authority.

The workbench exposes the new catalog as source setup:

- asset class, platform, account identifier, source URI, and authorization basis;
- connector kind and connection state;
- credential, OAuth, terms-review, live-collection, network, people-targeting, and external-action
  gates; and
- the manifest evidence digest that grounded the declaration.

## Deliberate limitations

- No live social account connection or OAuth token creation.
- No credential storage, browser-session reuse, private-resource discovery, account mutation, or
  authenticated API read.
- No people dossier generation, person targeting, contact graph, follower graph, private messages,
  or relationship traversal.
- No claim extraction, model fitting, forecast execution, monitoring, alerting, publication, or
  consequential decision support.
- No weakening of the H0 case gate: asset-catalog imports cannot append to a policy-bound H0 case
  ledger.

## Consequences

READIN now has an operational bridge from "I have real-world sensors/assets" to "the system can see
and organize the authorized asset surface." This makes the local workbench useful before live
connectors exist, while preserving the `NO_AUTHORITY` boundary and forcing future authenticated
connectors to arrive through separate, reviewed contracts.

Future connector slices should consume this catalog state rather than inventing target scope at
runtime. Each live connector still needs its own grant contract, minimization plan, retained-source
policy, revocation/deletion handling, source-terms review, incidental-person controls, and negative
tests.
