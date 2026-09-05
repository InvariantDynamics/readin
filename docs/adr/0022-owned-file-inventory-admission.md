# ADR 0022: Owned document and local-file ZIP inventories

## Status and scope

Accepted for H5. Extend native admission to operator-selected ZIP inventories under the existing
`DOCUMENT_COLLECTION` and `LOCAL_FILE_COLLECTION` catalog classes and `OWNED_DOCUMENT_METADATA`
grant scope. No filesystem scan, member extraction, content indexing, new per-file tracked assets,
provider connection, people collection, or automatic claims. H1-H4 records and retry semantics
remain unchanged.

## Decision

Register `DOCUMENT_COLLECTION_ZIP` → `document.inventory_metadata.imported` and
`LOCAL_FILE_COLLECTION_ZIP` → `file.inventory_metadata.imported`. Both use the same pure ZIP
central-directory metadata parser. The generic archive format supports any user-declared platform
label (`platform: null` in its descriptor); this is not a provider-specific export integration.
Grant matching still requires the exact catalog asset, platform, identifier, metadata scope,
observation type and local-export controls. Provider-specific H4 parsers remain platform-bound.

One import emits the existing three events: observer frame, raw-archive evidence manifest, and one
collection-level inventory observation. Its closed record contains:

- `inventory_kind: ZIP_CENTRAL_DIRECTORY_METADATA` and `content_verification: NOT_PERFORMED`;
- file entry count and total ZIP-declared uncompressed size;
- sorted entries with relative `entry_name`, declared `size_bytes`, and declared `crc32` only.

The archive SHA-256 identifies the supplied ZIP bytes. CRC32 is neither cryptographic file identity
nor content verification: READIN never opens or decompresses members, validates their CRCs, checks
local-header consistency, or verifies their declared sizes. It may inventory metadata even when
member content is corrupt or unsupported for extraction. Names do not authenticate document type,
account ownership, or collection completeness. Catalog association remains user-attested.

No compressed-size ratio limit is necessary because no member is decompressed. Limits are 64 MiB
raw input, 2048 total entries including directories, 512 characters per entry name, and 1 TiB total
declared uncompressed bytes. Directory entries are counted as skipped; all non-directory entries
are listed, including hidden files and OS metadata files. Empty/only-directory archives fail.

Reject traversal, absolute paths, empty/dot segments, backslashes, colons, Unicode control/format
characters, non-regular entry types, inconsistent file/directory modes, encrypted entries, and
case/Unicode aliases or file/directory path collisions. Do not echo rejected names in exceptions.
No extraction occurs even for accepted names. These checks are not a malware scanner.

`excluded_field_count` counts seven explicitly named unselected ZipInfo fields per admitted file:
date_time, compress_type, compress_size, external_attr, internal_attr, comment and extra. The receipt
states this basis and field list; it is not an exhaustive count of ZIP format fields, excluded
bytes, or independent sources. Other ZIP fields remain unselected too.

## Privacy and presentation

The existing owner-only source-file, non-symlink, outside-Git, grant-before-read, preview and explicit
attestation controls apply. The local archive's filesystem path is not recorded, but **relative
archive entry names are recorded**. Names may contain sensitive information: the operator must
review/sanitize the selected archive and preview before admission. No semantic name/secret detector
is claimed. The preview and receipt explicitly distinguish these two path behaviors.

The entire raw archive is read in order to hash it; member bytes are not decompressed or admitted.
Original ZIP retention remains user-managed. No source archive is copied, uploaded or deleted.
The ledger is append-only and retention days do not enforce erasure.

Evidence renders each snapshot as a filterable table, with declared-size/CRC labels and a distinct
file-entry count. One inventory with 100 file entries remains **one observation of one collection**.
Imports of changed archives are separate snapshots, not deduplicated documents or independent
corroboration. Source capability counts retain observation/asset semantics, not per-file inflation.

## Validation and follow-up

Positive/negative cases cover both classes, generic platform labels, closed output, unsafe and
ambiguous names, special files, encryption, bounds, no member/network access, private file controls,
grant-before-read, previews, retries and complete-prefix interruption. Workbench QA covers filters,
empty matches, long names, escaping and small-screen layout. Schema changes are additive; H4 parser
versions and generated historical events stay unchanged.

Next: scoped calendar/mail metadata contracts. A content-ingestion path would need separate output
fields, extraction limits, redaction and inspection controls; this metadata inventory does not
silently enable one. Live credentials, synchronization and connector lifecycle remain separate.
