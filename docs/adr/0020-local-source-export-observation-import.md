# ADR 0020: Grant-bound local profile observation import

## Status

Accepted for the H3 local import slice.

## Decision

Add `readin.local-source-export.v0.1`, a closed prepared JSON batch contract, and
`import-local-source-export`. The initial `GENERIC_JSON_OBSERVATION_BATCH` parser admits only
`social.profile_metadata`: platform, account identifier, display name, and an optional profile URL.
It is a prepared interchange format, not a LinkedIn, Google Takeout, or other native archive parser.
Additional record shapes require explicit versioned contracts and positive/negative tests.

The input must be one owner-only regular local file outside Git, with no symlink components, at
most 1 MiB, and 1–200 uniquely keyed rows. Duplicate JSON keys and non-finite values are rejected.
Field validation errors report the field path and rule without echoing rejected values.

An import requires an existing tracked social-account catalog asset and exactly one matching
connector-grant observation. The runner checks the stored grant contract, provenance and evidence
digest, catalog binding, `LOCAL_EXPORT_ONLY` access, profile metadata scope, permitted output, and
disabled credential/network/action states. An OAuth-readiness grant is insufficient. Each row must
match the catalog platform and account identifier; its optional HTTPS URL must match the catalog
source URI and contain no credentials, query, or fragment.

`--preview` validates the source, grant, and candidate replay and returns counts, admitted field
names, source digest, and deterministic observation IDs without writing. `--attest` is required
for admission. This command invocation is the explicit request for this bounded local import; it
does not activate or mutate the historical H2 readiness grant. H2's `CONTRACTED_NOT_ENABLED` output
state remains historical preregistration, while the H3 receipt records actual local admission.

The importer registers one source observer frame, manifests the exact prepared file digest, and
admits one immutable observation per row. Each row retains a shared import receipt, original
observed time, grant-observation identity and digest, source digest and size, parser/version, and
record key. All rows share a source artifact and frame; their number is not independent evidence.
Prepared file provenance does not authenticate a native provider export. Missing fields are
unknown and ownership/source accuracy remain user-attested. No claim is created.

Event IDs are deterministic. Same-byte retries skip verified existing events; changing bytes
under the same export ID is rejected, including after a frame-only or manifest-only interrupted
import. The ledger validates an entire batch under one exclusive lock before writing any of it.
This prevents partial admission on validation failure and interleaving by cooperative writers.
The JSONL write is not crash-atomic: a truncated final line still needs ledger recovery, and
concurrent identical imports can return a conflict that is resolved by retrying.

Only `USER_MANAGED_NOT_RECORDED` raw export retention is supported. Delete-after-import and
not-applicable policies fail closed. READIN neither copies nor deletes the source file and records
no filesystem source path. Retention days remain declarations, not enforced expiration; admitted
rows and evidence identities remain in the append-only ledger. No secure erasure is claimed.

The workbench displays imported record counts separately from catalog/grant observations, marks
incomplete observation batches, and shows actual imported profile fields in Evidence. Setup and
Evidence remain read-only; the CLI performs admission.

## Limits

This slice has no native ZIP/CSV parser, OAuth, token storage, provider API calls, monitoring,
contact/message/relationship imports, claim extraction, or external action. It does not load real
accounts automatically. Closed field names reduce accidental admission; schema validation cannot
prove the meaning of operator-entered strings. The operator must exclude private counterparty
content and credentials before admission. Browser content is escaped and no supplied URLs are
fetched. READIN-originated records remain `NO_AUTHORITY`.

## Verification

Tests cover preview without mutation, grant mismatch, account binding, prohibited fields, unsafe
paths and JSON, conflicting IDs, partial retries, batch validation failure, CLI admission, and
workbench receipt replay. `make check` validates the event contracts and existing runtime.
