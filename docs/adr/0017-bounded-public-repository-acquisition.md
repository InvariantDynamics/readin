# ADR 0017: Bounded public-repository acquisition

## Status

Accepted for an experimental local H0 slice.

## Context

READIN through Phase 8G admits user-supplied manifests and observations but does not acquire or
retain source bytes. That is sufficient for synthetic contract work, but it cannot demonstrate a
real source-to-vault-to-ledger path. Opening a general URL fetcher, authenticated account connector,
person-search surface, or crawler would introduce a much larger authority, privacy, credential,
SSRF, parser, retention, and source-terms boundary.

The immediate evaluation need is narrower: prove that one real, public, organizational software
asset can be acquired and represented without treating source output as fact or creating authority.

## Decision

Add one explicit, user-invoked connector for exactly:

```text
GET https://api.github.com/repos/{declared-owner}/{declared-repository}
```

The connector accepts owner and repository slugs, never a URL. It sends no authorization header,
cookie, request body, or user-provided header. Proxies and redirects are disabled. The API version
and representation are pinned, only a bounded HTTP 200 JSON response is accepted, and no retry or
background schedule exists. A single 15-second monotonic admission budget begins before DNS,
deducts elapsed work from the HTTP open timeout, and applies shrinking transport timeouts to body
reads. The case policy's exclusive wall-clock cutoff is also enforced inside the connector.

Every invocation requires a newly initialized case directory containing:

- a closed policy document and SHA-256 binding;
- one tracked `SoftwareRepository` entity carrying the non-secret case binding;
- one public repository observer frame;
- an owner-only event ledger;
- a case-local, owner-only, content-addressed evidence vault; and
- one immutable acquisition receipt.

Before transport opens, READIN exclusively creates an owner-only network-attempt marker. The marker
consumes the case's request budget even if DNS, TLS, HTTP, or response validation fails; a failed
request cannot be silently retried in the same one-shot case. If no artifact is admitted, the
workbench reports only that the attempt budget was reserved and no artifact was admitted; the marker
does not prove transport began or completed.

The policy fixes one exact target, a 24-hour collection window, one network request, one artifact,
a response-byte ceiling, zero relation hops, a maximum 30-day retention review, no secondary use,
no account mutation, no contact, no publication, no automated identity merge, no consequential
use, and `NO_AUTHORITY`.

The general-purpose mutating CLI commands refuse ledgers carrying a real-asset case binding. Only
the declared case connector may append to such a ledger. Read commands and workbench launch validate
the policy and fail closed after its retention deadline; a missing policy does not turn a bound
ledger back into an ungoverned ledger.

The raw response bytes are hashed internally and stored before the manifest and observation are
appended. The observation binds the canonical acquisition-receipt digest. Normal reads revalidate
the complete policy-marker-receipt-artifact-manifest-observation tuple, re-hash the stored bytes, and
reproduce the allowlisted projection from those bytes. The ledger contains only that repository-level
projection. It excludes
contributors, commit authors, organization members, issues, pull requests, person targeting,
person-profile construction, and automatic traversal of URLs returned by GitHub. The raw response
does include GitHub's public repository-owner object. The ledger retains only its login, numeric
account ID, and account type to bind the repository identity and enforce the organizational-target
policy; a `USER_OWNED_ASSET` repository may therefore carry incidental metadata for a `User` owner.

The connector validates that the response identifies the requested repository and reports it as
public. This is evidence that GitHub returned a public representation at the acquisition time. It
is not proof of legal ownership, human identity, repository truth, historical completeness, or
absence of unobserved information.

## Filesystem and local-service controls

READIN-created case directories use mode `0700`; ledgers, artifacts, receipts, policies, and lock
files use mode `0600`. Ledger and vault operations reject symbolic links and non-regular targets.
Real cases are rejected inside Git checkouts. The workbench accepts only numeric `127.0.0.1` or
`::1` listener bindings, verifies the bound address is loopback, and rejects untrusted or malformed
`Host` and non-loopback `Origin` headers.

These controls do not provide full-disk encryption, secure erasure, backup control, Spotlight
exclusion, malware resistance, or protection from another process already running as the same macOS
user. Real cases should be placed outside Git and cloud-synchronized folders on a FileVault-enabled
Mac. The retention deadline is a review/stop gate; this slice does not automatically delete data.

## Deliberate limitations

This H0 slice is one-shot. Any attempted fetch consumes the budget, and a second attempt requires a
new case. ETag revalidation, repeated
acquisition receipts, case reconciliation after process failure, and atomic multi-event append are
deferred rather than weakening the existing duplicate-digest invariant.

DNS answers for the fixed GitHub API hostname are checked for public addresses before the request,
but the standard HTTP transport may resolve the hostname again. Local DNS or trust-store compromise
is outside this H0 threat boundary; the preflight check is defense in depth, not a claim of DNS
pinning.

The synchronous Python resolver and standard-library connection/header path cannot be forcibly
preempted by an in-process deadline. READIN checks the budget before and after these operations,
closes a response that returns late, and admits no late artifact; it does not claim a hard upper bound
on wall-clock process runtime. Strict preemption would require a supervised child process or a
different nonblocking transport.

## Explicit non-goals

- No authenticated GitHub account access or credential storage.
- No arbitrary URL fetch, search, crawl, page following, repository contents, archives, commits,
  contributors, issues, pull requests, events, or organization membership.
- No browser-session reuse, login, access-control bypass, CAPTCHA handling, or private-resource
  discovery.
- No person target, associate graph, identity resolution, automated claim extraction, model input,
  monitoring, alerting, targeting, publication, or external action.
- No implication that a public resource is owned by the operator. `USER_OWNED_ASSET` is available
  only as `USER_ATTESTED_NOT_VERIFIED`; the default makes no ownership claim.

Authenticated account connectors and governed self/consenting-person research require separately
reviewed contracts, scoped grants held outside the ledger, minimization rules for incidental people,
revocation and deletion handling, source-specific terms controls, and their own adversarial tests.

## Consequences

READIN can now demonstrate one real, auditable public acquisition without becoming a general OSINT
collector. The new boundary increases useful capability and attack surface, so its policy, vault,
transport, and workbench controls are mandatory parts of the slice. Existing synthetic ledgers and
event contracts remain replay-compatible.
