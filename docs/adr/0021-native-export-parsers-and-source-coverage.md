# ADR 0021: Native local export parsers and explicit source coverage

## Status

Accepted for H4. H3's prepared JSON contract and historical records are unchanged.

## Decision

Add native file admission with three explicit parser selectors:

| Parser | Catalog class / platform | Grant scope | Admitted record |
| --- | --- | --- | --- |
| `LINKEDIN_PROFILE_CSV` | `SOCIAL_ACCOUNT` / LinkedIn | `ACCOUNT_PROFILE_METADATA` | `social.profile_metadata` |
| `LINKEDIN_PROFILE_ZIP` | `SOCIAL_ACCOUNT` / LinkedIn | `ACCOUNT_PROFILE_METADATA` | `social.profile_metadata` |
| `GITHUB_REPOSITORY_JSON` | `SOFTWARE_REPOSITORY` / GitHub | `OWNED_REPOSITORY_METADATA` | `github.public_repository_metadata.imported` |

`prepare-native-source-grant` prints a fresh, schema-validated H2 grant template based on an
existing catalog asset and parser. It does not write files or ledger events, or attest provider
terms. The operator reviews it, stores it privately outside Git, and records it through the H2
command. Grants remain local-export contracts, not OAuth or provider sessions.

`import-native-source-export` requires an asset, grant, parser, local source file, and explicit
operator-declared observation time. `--preview` validates and reports selected values, original
source digest, selected fields, exclusions, and identity-binding limitations without writing.
`--attest` admits the exact same selected record shape under the compatible grant.

H3's private byte reader and grant validator are reused. The latter now accepts explicit parser
class/scope/output parameters with unchanged H3 defaults. Native grant validation happens before
source bytes are read. The normalized parser result is closed under
`readin.native-source-record.v0.1`; record extension requires schema and test changes.

## Source-specific semantics

LinkedIn accepts a UTF-8 (optional BOM), header-first CSV containing exactly one row, with unique
headers including `First Name` and `Last Name`. Only these names become `display_name`; all other
columns are excluded and counted. This supported layout is tested with synthetic fixtures, not a
claim that every language or future provider export version uses identical headers. Unsupported
layouts fail visibly rather than being heuristically interpreted.

Profile.csv contains no independently authenticated account binding in this contract. The selected
catalog asset is explicitly `USER_ATTESTED_CATALOG_ASSOCIATION`; its handle is not manufactured as
source-reported profile content. The CSV's address, birthday, biography, and other fields do not
enter the observation.

For ZIP input, hash the original archive and selected member separately. Read exactly one member
whose basename is Profile.csv, including a member nested in an export directory. Reject ambiguous
matches, traversal or absolute paths, symlinks, encrypted/unsupported selected members, malformed
archives, and excessive sizes/compression. Limits: 64 MiB archive, 2048 entries, 1 MiB selected
member, 100:1 selected-member compression ratio. No files are extracted. Unrelated archive members
are counted but never decompressed or admitted. Their names and contents are not ledger fields.

Saved GitHub JSON reuses the existing pure `parse_public_repository_response` validator, with no
call to its network acquisition function. The catalog identifier must be `owner/repository`; URL,
identity and public visibility must match. The native record keeps only stable repository identity,
visibility, default branch, language, repository flags, and available star/fork/open-issue counts.
Owner contact data, contributors, relationship lists, descriptions, URLs, and unselected fields
are excluded. A saved file provides `SOURCE_IDENTIFIER_MATCHED_NOT_AUTHENTICATED`, not proof that
READIN contacted GitHub. H0's HTTP acquisition assertions and case policy are not reused.

## Evidence, repeatability, and coverage

Each import registers a native-source observer frame, manifests original source bytes, and admits
one record carrying a receipt. The receipt retains grant-observation identity/digest, parser/version,
source digest/size, selected member digest when applicable, field selection and exclusion counts,
operator-declared time basis, and explicit identity-binding state. No filesystem source paths are
recorded. The source file remains user-managed; no copy, deletion, expiration, or authentication of
provider origin is claimed. Exclusion counts measure top-level columns/keys, not bytes or people.

Deterministic IDs bind grant, parser, and original source digest. Identical retries preserve existing
events; a changed observation time under the same import identity is rejected after admission.
Complete-prefix interruption can resume; a truncated JSONL line still needs ledger recovery.
New source bytes yield a new import. Global evidence-digest uniqueness may reject the same file
under a different grant, rather than duplicate it as independent evidence.

The Sources workbench tab and `list-source-capabilities` report all 11 catalog classes. Parser
availability, compatible grants, imported-record counts, and broader coverage are separate fields.
A ready grant does not prove a file is present or valid. Only listed class/provider/format pairs
are supported. Native imports and H3 records are counted separately from setup declarations. H0's
public one-shot runner is reported separately. Account synchronization, monitoring, and full signal
coverage are not implemented; source coverage remains `NOT_ESTABLISHED`.

## Path toward broader operational coverage

The next increments should reuse this admission/coverage mechanism: owned document metadata and
local asset inventory; then a separately scoped calendar/mail metadata parser; then a connector
execution contract with explicit credentials, refresh/revocation, receipts, retry and rate limits.
Financial or device sources need their own field contracts. Catalog representation alone does not
make these sources operational. Claims, entity merging, forecasts, and actions remain separate.

## Source references

- [LinkedIn: Download your data](https://www.linkedin.com/help/linkedin/answer/a1339364/downloading-your-account-data)
  documents the export flow and profile category. It is not a stable CSV header specification.
- [GitHub: Repository REST endpoints](https://docs.github.com/en/rest/repos/repos#get-a-repository)
  documents the native repository response shape. H4 imports a saved response only.

## Validation

Positive and negative tests cover native formats, BOM/quoted CSV, identity/visibility mismatches,
excluded fields and member contents, archive ambiguity and path safety, limits, preview without
writes, repeated admission, grant-template round trips, and actual versus potential source coverage.
