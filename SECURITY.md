# Security Policy

## Supported versions

READIN is pre-alpha. Only the latest revision is supported.

## Reporting a vulnerability

Please report vulnerabilities through GitHub's private vulnerability reporting feature when it is
available for this repository. Do not include credentials, private source material, or personal data
in a public issue.

## Current security boundary

The Phase 0 through Phase 8G runtime remains a local reference implementation centered on manual and
synthetic input. The experimental real-asset H0 slice adds exactly one live path: a user-invoked,
credential-free request for one policy-declared public GitHub repository metadata record. The local
asset-catalog onboarding slice can also import an owner-only local JSON manifest of self or
controlled assets, but it performs no live source access. READIN is not a general URL client,
crawler, authenticated account connector, person-search system, or monitor.

H0 sends no credential or cookie, disables proxies and redirects, makes one bounded request, stores
exact response bytes in an owner-only case vault, and admits only an allowlisted repository-level
observation with `NO_AUTHORITY`. It does not retrieve contributors, commits, members, issues, pull
requests, repository contents, or private resources, and it does not create person targets or
profiles. The raw GitHub response contains public owner-account fields; the ledger keeps only the
owner login, numeric account ID, and account type needed for target binding and classification. See
`docs/adr/0017-bounded-public-repository-acquisition.md` for the complete boundary and limitations.

The request has one shrinking 15-second admission budget from before DNS through body completion,
plus the case policy's exclusive wall-clock cutoff. Synchronous DNS, connection, and HTTP-header work
inside the Python standard library cannot be preempted in-process; a late return is closed and rejected
without artifact admission, but elapsed process runtime can exceed that budget. Strict runtime
preemption would require a supervised child process or a different nonblocking transport.

Completed-case reads fail closed unless the policy, genesis binding, request marker, receipt digest,
raw artifact hash and size, evidence manifest, and admitted observation remain mutually consistent.
This is application-level tamper detection, not WORM storage or protection from a process already
running as the same macOS user.

Personal asset-catalog manifests must be stored outside Git checkouts and cloud-synchronized
folders. The importer rejects non-owner-only manifest files, records only a digest URI rather than
the manifest path, and admits asset declarations as user-declared observations with
`NO_AUTHORITY`. Connector states such as `OAUTH_REQUIRED_NOT_REQUESTED` and
`EXPORT_IMPORT_READY` are readiness labels only; they are not credentials, grants, sessions, API
tokens, source-term approval, private-message access, follower/contact graph access, monitoring, or
permission to investigate third parties.

Connector grant manifests are also owner-only local files outside Git checkouts. A recorded grant is
still `RECORDED_NOT_ACTIVE`: it stores no credential material, performs no OAuth flow, contacts no
provider, parses no export, starts no monitor, and authorizes no people targeting or external
action. It exists only to bind future source-runner implementation to explicit scopes,
minimization, allowed observation outputs, retention, revocation, audit, and redaction controls.

The loopback workbench has no authentication. It accepts only numeric `127.0.0.1` or `::1` listener
bindings, verifies the bound socket is loopback, validates `Host` and `Origin`, and refuses mutation
methods, but should still be treated as a same-user local presentation surface.
Schema validation, path checks, file permissions, and locking are integrity controls, not a security
sandbox. READIN does not provide disk encryption, secure erasure, malware isolation, or protection
from another process already running as the same macOS user.
