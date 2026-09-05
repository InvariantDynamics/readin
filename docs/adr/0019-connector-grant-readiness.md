# ADR 0019: Connector grant readiness before source runners

## Status

Accepted as the second operational onboarding slice after local asset-catalog import.

## Context

The asset catalog can now represent the operator's self-owned or otherwise controlled accounts,
repositories, web properties, documents, devices, and other assets. That is still not enough to run
an operational source pipeline. A useful system needs to know what a connector may read, what it may
emit, what data it must exclude, how long raw material may be retained, and how access is revoked.

Those decisions cannot be hidden inside a provider adapter. They must be ledger-visible before any
OAuth flow, API call, export parser, monitor, or source runner is implemented.

## Decision

Add a closed connector grant manifest contract:

```text
readin.connector-grant-source.v0.1
```

The manifest references an existing asset-catalog entity by `entity_id`, `catalog_id`,
`asset_key`, asset class, platform, and account identifier. Import requires that the target entity is
already tracked and that these fields match its `asset_catalog_binding`.

The importer:

1. reads one owner-only local JSON manifest from outside Git checkouts;
2. validates the closed schema and cross-field grant invariants;
3. hashes the manifest bytes and manifests that digest as evidence;
4. registers one local connector-grant observer frame;
5. admits one immutable `asset_connector.grant_declared` observation on the target asset; and
6. rejects reuse of a `grant_id` with changed manifest bytes.

The command is:

```shell
uv run readin record-connector-grant \
  --ledger "/path/outside/git/events.jsonl" \
  --manifest "/path/outside/git/grant.json" \
  --attest
```

The grant records only readiness. It keeps:

- `grant_state`: `RECORDED_NOT_ACTIVE`;
- `collection_state`: `NOT_STARTED`;
- `credential_material`: `ABSENT`;
- `credential_storage`: `PROHIBITED`;
- `oauth_state`: `NOT_REQUIRED` or `NOT_REQUESTED`;
- `live_collection_state`: `DISABLED`;
- `network_access`: `false`;
- `external_action_state`: `PROHIBITED`;
- `people_targeting`: `PROHIBITED`; and
- `activation_requirement`: `SEPARATE_EXPLICIT_CONNECTOR_GRANT_REQUIRED`.

The workbench exposes the latest grant observation in the Setup view, including declared scopes,
permitted observation output types, minimization, retention, revocation, audit, and disabled
authority states.

## Deliberate limitations

- No token creation, token storage, OAuth redirect, browser-session reuse, API read, export parse,
  monitoring, scheduling, or network access.
- No claim extraction, identity merge, person-target dossier, social graph, follower graph, contact
  graph, private message read, or counterparty-data admission.
- No source-term approval beyond recorded user attestation or `REQUIRES_REVIEW`.
- No live connector runner. A later runner must consume this grant, produce its own execution
  receipt, and pass new negative tests before any source bytes can be admitted.

## Consequences

READIN now has a typed bridge from "asset cataloged" to "source access can be engineered." This
makes the next unit of work concrete: implement a specific local export parser or source runner that
refuses to execute unless a matching grant observation exists and its states are compatible.

The grant observation is not authority to collect. It is a preregistration artifact for future
implementation and review.
