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

The current foundation, bounded Array, resolution, cartography, multi-fitter, belief, scenario,
asset-workbench, discriminating-observation, forecast-evaluation design, frozen-baseline,
readback-selection, descriptive-reference-residual, validity-update eligibility, and
prospective forecast-fitter specification and residual-readback eligibility slices
implement one local epistemic loop:

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
19. Create unresolved hypotheses with explicit claim polarity bindings.
20. Connect hypotheses through assumption-bound directed edges while rejecting cycles.
21. Produce a dependency-aware categorical belief revision with a digest-bound receipt.
22. Create an assumption- and intervention-bound scenario tree with a required unknown branch.
23. Evaluate branch antecedents against one immutable belief revision without assigning likelihoods
    or simulating trajectories.
24. Project the replayed ledger into a compact operator view that retains claim status, dependency
    ancestry, blind regions, fitter invalidity, categorical belief state, and unknown branches.
25. Inspect that projection through a loopback-only, read-only browser workbench.
26. Declare manual candidate observations against a specified ambiguity, belief revision, and
    cartographic blind-region context.
27. Rank only their user-supplied structural effects on competing hypotheses, preserving ties and
    abstaining when no candidate discriminates.
28. Inspect the result as a “Next observation” view without querying, acquiring, or contacting a
    source.
29. Predeclare one numeric forecast-evaluation target, metric, training cutoff, forecast origin, and
    post-cutoff exclusion policy before the scenario horizon begins.
30. Keep fitter selection `NOT_SELECTED`; optionally freeze one separate user-declared constant
    benchmark after design creation and before forecast origin.
31. Preserve that benchmark as `PRODUCED_UNCALIBRATED_BASELINE`, with no training observations,
    calibration, empirical validity, residual scoring, or learning update.
32. Before forecast origin, predeclare eligible readback observer frames, an observed-time window
    strictly after the horizon, and a ledger-admission cutoff.
33. Admit later manual observations while preserving both their observed times and ledger-admission
    times.
34. After the cutoff, deterministically select exactly one compatible readback or abstain on zero or
    multiple matches without ranking, aggregation, or post-hoc choice.
35. Retain the digest-bound selection with unit equivalence unverified and no residual,
    fitter-validity, weighting, future-admissibility, or learning update.
36. Only for a unique selection, compute signed residual as observed minus predicted and absolute
    error against the frozen constant, while leaving unit equivalence, uncertainty, calibration,
    empirical validity, validity updates, weighting, future admissibility, and learning unopened.
37. Assess whether that descriptive residual can support a validity update, retain all six blocking
    conditions, and abstain without selecting a fitter or applying any update.
38. Register a future-only linear-regression fitter specification with typed target, feature,
    temporal, control, and output requirements, while leaving implementation, training, selection,
    execution, prediction, and validation unopened.
39. In the separate no-baseline branch, bind a later observation to the earlier scenario run and
    retain the existing ineligible-baseline abstention.

This slice uses manual, synthetic input only. Cartographic, fitter, belief, and scenario execution is
local and deterministic; the workbench has no write endpoint and refuses non-loopback bindings.
`coverage_state` remains `NOT_ESTABLISHED`, completeness is never claimed,
and post-cutoff surface definitions are labeled as hindsight in the query lens. Fitter and scenario
empirical validity is `NOT_ESTABLISHED`. Phase 8B predeclares an evaluation design and temporal
leakage boundary, but does not select a fitter, execute a forecast, or produce a prediction. Its
target and metric remain user-declared and unvalidated. Phase 8A retains a later observation
readback, but the
reference scenario run has `prediction_state: NOT_REQUESTED`; therefore the forecast baseline is
`NOT_AVAILABLE`, residual is `NOT_COMPUTED`, validity and weighting updates are `NOT_APPLIED`, and
learning is `NOT_STARTED`. Together these are prerequisite gates, not the full Phase 8 residual
loop. Phase 8C can instead freeze one finite, user-declared constant before forecast origin. The
reference method uses no training observations and records `PRODUCED_UNCALIBRATED_BASELINE`, while
calibration and empirical validity remain `NOT_ESTABLISHED`. Residual scoring remains `NOT_ENABLED`;
when this baseline exists, the Phase 8A no-baseline readback command fails closed. Phase 8D
preregisters a deterministic exactly-one readback aperture. It separates observation time from
ledger-admission time and abstains on zero or multiple compatible observations. Even one selected
observation remains `NOT_COMPUTED` for residuals and cannot update validity or learning at the
selection boundary. Phase 8E separately records one
`COMPUTED_DESCRIPTIVE_REFERENCE_ONLY` result after a unique selection: prediction `0.75`, observed
value `1.0`, signed residual `0.25`, and absolute error `0.25` in the synthetic fixture. The unit
binding remains user-declared and unverified, uncertainty is not estimated from one readback,
calibration and empirical validity remain unestablished, and no validity, weighting,
future-admissibility, or learning update follows. Phase 8F makes that boundary executable: it binds
the residual to a replay-verifiable eligibility receipt and records
`INELIGIBLE_VALIDITY_UPDATE` / `ABSTAINED` because no forecast fitter, trained model, validation
corpus, verified unit equivalence, multi-sample evidence, or uncertainty estimate exists. It does
not select a fitter or establish model invalidity. Bayesian and belief outputs are explicitly
diagnostic rather than truth probabilities. Phase 8G then records one prospective
`LINEAR_REGRESSION` specification. It is registered after the historical assessment and cannot
rewrite it. No training data, temporal split, negative controls, implementation, design selection,
execution, prediction, validation corpus, uncertainty estimate, or model-validity result exists.
Scenario branches are
user-defined conditional structures: likelihood is `NOT_COMPUTED`, trajectories are
`NOT_SIMULATED`, and the unknown/unmodeled region remains visible. Phase 7 ranking is an ordinal
structural heuristic over user-supplied, unvalidated expected effects; it does not compute expected
information gain, source feasibility, source independence, or probabilities. The slice performs no
network collection, entity merging, automated claim extraction, learned or external forecasting,
targeting, or external action. The separately bounded H0 real-asset path described below is the sole
network exception; it does not alter any fitter, belief, scenario, identity, or action boundary.
A claim remains unresolved even when evidence is linked, and repeated dependent evidence is never
counted as independent corroboration. Candidate resolution is review history only: it never performs
a canonical entity merge.

## Experimental real-asset H0

H0 can acquire one real public GitHub repository metadata response into a local READIN case. This is
an exact-target evidence-custody test, not an open-ended search or people-investigation feature.

The case policy is application-write-once and digest-bound. It permits one user-invoked,
credential-free request,
one artifact, zero relation hops, a maximum 512 KiB response, a 24-hour collection window, and a
maximum 30-day retention review. Proxies, redirects, retries, schedules, cookies, tokens, account
writes, person targeting, person-profile construction, and automatic external-link traversal are
absent. Raw GitHub response bytes can contain incidental public owner-account metadata. The
allowlisted ledger projection retains only the owner's login, numeric account ID, and account type
needed to bind and classify the repository target; it does not collect contributors or traverse to
people. Raw bytes are stored in an owner-only content-addressed vault, and the ledger retains
`NO_AUTHORITY`, `BOUNDED` coverage, and `NOT_MADE` completeness.

For a completed case, normal CLI and workbench reads revalidate the policy and request marker,
re-hash the raw artifact, verify the digest-bound acquisition receipt, and reproduce the allowlisted
observation from the stored bytes. A missing or contradictory custody component fails closed.

Generic mutating READIN commands cannot append to a policy-bound case ledger. The workbench and
normal read commands also fail closed after the retention deadline or if the policy is missing.

READIN reserves the one-request budget before opening the network connection. A DNS, TLS, HTTP, or
validation failure therefore consumes that case; initialize a reviewed new case rather than retrying
the failed one. If the durable reservation exists without an admitted artifact, the workbench reports
`NETWORK_ATTEMPT_RESERVED_NO_ADMISSION` and `NO_ARTIFACT_ADMITTED`; the reservation alone does not
prove that transport completed.

The connector applies one 15-second aggregate monotonic admission budget beginning before its DNS
preflight, deducts elapsed DNS/connect time from the HTTP timeout, and applies shrinking socket
timeouts to response-body reads. The policy cutoff is also passed into the connector and is exclusive:
a response completing at or after that instant is rejected. Python's synchronous resolver and
standard-library HTTP header processing cannot be forcibly interrupted by this in-process check; if
either returns late, READIN closes/rejects the response and admits no artifact. This is a no-late-
admission control, not a hard process-runtime guarantee.

The default subject class is `PUBLIC_ORGANIZATION_ASSET`, which makes no ownership claim. Use
`USER_OWNED_ASSET` only for an asset you own or administer; READIN records that as
`USER_ATTESTED_NOT_VERIFIED`, not proof of ownership.

```shell
cd /path/to/readin
uv sync --dev

READIN_CASE_DIR="$HOME/.local/share/readin/cases/invariantdynamics-readin"

uv run readin init-github-public-repository-case \
  --case-dir "$READIN_CASE_DIR" \
  --owner InvariantDynamics \
  --repository readin \
  --purpose "Evaluate one bounded public repository acquisition through READIN" \
  --subject-class PUBLIC_ORGANIZATION_ASSET \
  --retention-days 30 \
  --attest

uv run readin collect-github-public-repository-case \
  --case-dir "$READIN_CASE_DIR"

uv run readin show-workbench \
  --ledger "$READIN_CASE_DIR/events.jsonl"

uv run readin workbench \
  --case-dir "$READIN_CASE_DIR" \
  --host 127.0.0.1 \
  --port 4173 \
  --open-browser
```

The command validates the case, starts the loopback-only service, and opens
`http://127.0.0.1:4173`. Keep that Terminal window open while using the workbench; press
`Control-C` there to stop it. Do not open `src/readin/workbench_assets/index.html` directly: it is a
served interface asset, not a standalone application. Direct file opening now displays a launch
diagnostic instead of a broken shell.

For a policy-bound H0 ledger, the workbench opens on the **Case** view. That view reports the
declared purpose, exact target, source restrictions, request and artifact budgets, retention review,
minimization exclusions, validated custody chain, and the allowlisted repository observation.
**Evidence** shows admitted observations and manifests; **Timeline** shows the asset-affecting event
history. These are read models over validated local records, not new collection or truth claims.

The command stores real source data, so put the case outside Git and cloud-synchronized folders on
a FileVault-enabled Mac. The retention timestamp stops later collection but does not auto-delete
the case. Review and remove the exact case directory yourself when it is no longer needed. A second
acquisition requires a new case in H0.

See [ADR 0017](docs/adr/0017-bounded-public-repository-acquisition.md) and
[Security](SECURITY.md) before adding any other connector or target class.

## Local personal asset catalog onboarding

READIN can now start with your own asset surface before any live connector is granted. Create a
private local manifest outside Git and cloud-synchronized folders, then import it into a private
ledger:

```shell
READIN_ASSET_DIR="$HOME/.local/share/readin/personal-catalog"
mkdir -p "$READIN_ASSET_DIR"
chmod 700 "$READIN_ASSET_DIR"

$EDITOR "$READIN_ASSET_DIR/source.json"
chmod 600 "$READIN_ASSET_DIR/source.json"

uv run readin import-asset-catalog \
  --ledger "$READIN_ASSET_DIR/events.jsonl" \
  --manifest "$READIN_ASSET_DIR/source.json" \
  --attest

uv run readin workbench \
  --ledger "$READIN_ASSET_DIR/events.jsonl" \
  --host 127.0.0.1 \
  --port 4173 \
  --open-browser
```

Minimal manifest shape:

Replace `catalog_id` with a fresh lowercase UUID, for example:

```shell
uuidgen | tr 'A-F' 'a-f'
```

```json
{
  "schema_version": "readin.asset-catalog-source.v0.1",
  "catalog_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "catalog_name": "Personal asset surface",
  "declared_at": "2026-09-04T12:00:00Z",
  "owner": {
    "label": "Local operator",
    "attestation": "USER_ATTESTED_NOT_VERIFIED",
    "scope": "SELF_OR_CONTROLLED_ASSETS_ONLY"
  },
  "purpose": {
    "kind": "PERSONAL_ASSET_CATALOG",
    "statement": "Build a local inventory of accounts and assets before any live connector.",
    "secondary_use": "PROHIBITED"
  },
  "authority": {
    "state": "NO_AUTHORITY",
    "collection": "NOT_GRANTED",
    "external_actions": "PROHIBITED",
    "credential_storage": "PROHIBITED",
    "network_access": false,
    "people_targeting": "PROHIBITED"
  },
  "source": {
    "kind": "USER_DECLARED_LOCAL_MANIFEST",
    "network_access": false,
    "credential_material": "ABSENT",
    "path_retention": "NOT_RECORDED_IN_LEDGER"
  },
  "assets": [
    {
      "asset_class": "SOCIAL_ACCOUNT",
      "display_name": "My LinkedIn account",
      "platform": "LinkedIn",
      "account_identifier": "my-handle",
      "source_uri": "https://www.linkedin.com/in/my-handle/",
      "authorization_basis": "USER_OWNED_ACCOUNT_ATTESTED",
      "collection_mode": "API_CONNECTION_REQUIRES_SEPARATE_GRANT",
      "connector_intent": {
        "connector_kind": "OAUTH_API",
        "connection_state": "OAUTH_REQUIRED_NOT_REQUESTED",
        "credential_state": "NONE",
        "oauth_state": "NOT_REQUESTED",
        "live_collection_state": "DISABLED",
        "external_action_state": "PROHIBITED",
        "terms_review_state": "REQUIRES_REVIEW"
      }
    },
    {
      "asset_class": "WEB_PROPERTY",
      "display_name": "My public website",
      "platform": "HTTPS",
      "account_identifier": "example.com",
      "source_uri": "https://example.com/",
      "authorization_basis": "USER_ADMINISTERED_ASSET_ATTESTED",
      "collection_mode": "LOCAL_EXPORT_IMPORT_ONLY",
      "connector_intent": {
        "connector_kind": "PUBLIC_WEB",
        "connection_state": "EXPORT_IMPORT_READY",
        "credential_state": "NONE",
        "oauth_state": "NOT_REQUIRED",
        "live_collection_state": "DISABLED",
        "external_action_state": "PROHIBITED",
        "terms_review_state": "USER_ATTESTED_ALLOWED"
      }
    }
  ]
}
```

This command hashes the manifest as local evidence, creates tracked asset records, and admits one
immutable `asset_catalog.user_declared_profile` observation per asset. It does not contact the
listed services. OAuth, social APIs, private messages, follower graphs, contacts, monitoring,
person-target dossiers, and external actions remain unavailable until a later connector contract
explicitly grants and tests them.

See [ADR 0018](docs/adr/0018-local-asset-catalog-onboarding.md) for the full onboarding boundary.

### Record connector grant readiness

After an asset is in the catalog, record a separate connector grant manifest before building any
source-specific runner:

```shell
uv run readin record-connector-grant \
  --ledger "$READIN_LEDGER" \
  --manifest "$READIN_PRIVATE_DIR/linkedin-grant.json" \
  --attest
```

The grant manifest references the `entity_id` and `asset_key` returned by
`import-asset-catalog`. It records:

- connector kind and version;
- scope names, source surfaces, and minimization state;
- allowed observation types that a later parser may emit;
- retention, revocation, audit, and redaction requirements; and
- hard gates for credentials, OAuth, network access, live collection, external action, and people
  targeting.

Example grant manifest for a future read-only profile connector:

```json
{
  "schema_version": "readin.connector-grant-source.v0.1",
  "grant_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  "declared_at": "2026-09-04T12:05:00Z",
  "owner": {
    "label": "Local operator",
    "attestation": "USER_ATTESTED_NOT_VERIFIED",
    "scope": "SELF_OR_CONTROLLED_ASSETS_ONLY"
  },
  "asset": {
    "entity_id": "<asset-entity-id-from-import>",
    "catalog_id": "<catalog-id-from-import>",
    "asset_key": "<asset-key-from-import>",
    "asset_class": "SOCIAL_ACCOUNT",
    "platform": "LinkedIn",
    "account_identifier": "operator"
  },
  "provider": {
    "platform": "LinkedIn",
    "connector_kind": "OAUTH_API",
    "connector_name": "LinkedIn read-only profile setup",
    "connector_version": "0.0.0-contract-only",
    "terms_review_state": "REQUIRES_REVIEW",
    "terms_reference_uri": "https://www.linkedin.com/legal/user-agreement"
  },
  "purpose": {
    "kind": "CONNECTOR_READINESS_ASSESSMENT",
    "statement": "Record a future read-only connector boundary for the operator account.",
    "secondary_use": "PROHIBITED"
  },
  "grant": {
    "grant_kind": "OAUTH_API_REQUIRES_SEPARATE_TOKEN_FLOW",
    "grant_state": "RECORDED_NOT_ACTIVE",
    "authorization_basis": "USER_OWNED_ACCOUNT_ATTESTED",
    "access_mode": "API_CONNECTION_REQUIRES_SEPARATE_TOKEN_FLOW",
    "collection_state": "NOT_STARTED",
    "credential_material": "ABSENT",
    "credential_storage": "PROHIBITED",
    "oauth_state": "NOT_REQUESTED",
    "live_collection_state": "DISABLED",
    "network_access": false,
    "external_action_state": "PROHIBITED",
    "people_targeting": "PROHIBITED",
    "activation_requirement": "SEPARATE_EXPLICIT_CONNECTOR_GRANT_REQUIRED"
  },
  "authority": {
    "state": "NO_AUTHORITY",
    "collection": "NOT_STARTED",
    "external_actions": "PROHIBITED",
    "credential_storage": "PROHIBITED",
    "network_access": false,
    "people_targeting": "PROHIBITED"
  },
  "source": {
    "kind": "USER_DECLARED_LOCAL_GRANT_MANIFEST",
    "network_access": false,
    "credential_material": "ABSENT",
    "path_retention": "NOT_RECORDED_IN_LEDGER"
  },
  "scopes": [
    {
      "scope_name": "profile_metadata",
      "source_surface": "Self profile metadata",
      "data_category": "ACCOUNT_PROFILE_METADATA",
      "access_intent": "READ_ONLY_IF_SEPARATELY_ENABLED",
      "minimization": "MINIMUM_NECESSARY",
      "private_counterparty_data": "EXCLUDED",
      "claim_extraction": "PROHIBITED"
    }
  ],
  "allowed_observation_types": [
    {
      "observation_type": "social.profile_metadata",
      "admission_state": "CONTRACTED_NOT_ENABLED",
      "claim_extraction": "PROHIBITED",
      "external_action_state": "PROHIBITED"
    }
  ],
  "retention": {
    "local_retention_days": 30,
    "raw_export_retention": "NOT_APPLICABLE",
    "path_retention": "NOT_RECORDED_IN_LEDGER"
  },
  "revocation": {
    "state": "MANUAL_REVOCATION_REQUIRED_IF_ACTIVATED",
    "operator_action": "If later activated, revoke access at the provider and remove local token material."
  },
  "audit": {
    "receipt_required": true,
    "path_retention": "NOT_RECORDED_IN_LEDGER",
    "token_storage": "PROHIBITED",
    "execution_log": "REQUIRED_BEFORE_COLLECTION",
    "redaction_policy": "REQUIRED_BEFORE_COUNTERPARTY_DATA"
  }
}
```

`record-connector-grant` appends a local grant frame, evidence manifest, and immutable
`asset_connector.grant_declared` observation. It does not request OAuth, store tokens, contact the
provider, parse exports, or collect account data. It exists to make the next implementation step
typed and reviewable before any sensor runner is written.

See [ADR 0019](docs/adr/0019-connector-grant-readiness.md) for the connector-grant boundary.

## Import a local profile export (H3)

The first working import path accepts a **prepared JSON profile batch** for one cataloged social
account. Native provider ZIP and CSV archives are not yet supported. Copy only your platform,
account identifier, display name, and optional catalog-matched profile URL into this format.
Provider origin and accuracy remain user-supplied, not independently verified.

First record a **new** grant using the H2 manifest above with these changes:

- Use a new `grant_id` (never reuse an ID with changed content).
- Set `provider.connector_kind` to `SOCIAL_EXPORT` and give it a local-export connector name.
- Set `grant.grant_kind` to `LOCAL_EXPORT_ONLY`, `grant.access_mode` to
  `LOCAL_EXPORT_IMPORT_ONLY`, and `grant.oauth_state` to `NOT_REQUIRED`.
- Keep `ACCOUNT_PROFILE_METADATA` scope and `social.profile_metadata` as the output.
- Set `retention.raw_export_retention` to `USER_MANAGED_NOT_RECORDED`.

Store this prepared export as an owner-only file outside Git and cloud-synchronized folders.
Replace the example IDs with your export ID, recorded local-export grant ID, and catalog entity
ID. Platform, account identifier, and optional URL must match that catalog asset exactly.

```json
{
  "schema_version": "readin.local-source-export.v0.1",
  "export_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
  "grant_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  "asset_entity_id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
  "prepared_at": "2026-09-04T12:10:00Z",
  "parser": "GENERIC_JSON_OBSERVATION_BATCH",
  "handling": {
    "owner_attestation": "SELF_OR_CONTROLLED_ASSETS_ONLY",
    "private_counterparty_data": "EXCLUDED",
    "credential_material": "ABSENT",
    "network_access": false,
    "raw_export_retention": "USER_MANAGED_NOT_RECORDED"
  },
  "observations": [
    {
      "record_key": "profile-1",
      "observation_type": "social.profile_metadata",
      "observed_at": "2026-09-04T12:00:00Z",
      "structured_payload": {
        "platform": "LinkedIn",
        "account_identifier": "operator",
        "display_name": "Example operator",
        "profile_url": "https://www.linkedin.com/in/operator/"
      }
    }
  ]
}
```

Preview, then import using the same paths and grant:

```shell
uv run readin import-local-source-export \
  --ledger "/path/outside/git/events.jsonl" \
  --grant "your-local-export-grant-id" \
  --source "/path/outside/git/profile-export.json" \
  --preview

uv run readin import-local-source-export \
  --ledger "/path/outside/git/events.jsonl" \
  --grant "your-local-export-grant-id" \
  --source "/path/outside/git/profile-export.json" \
  --attest

uv run readin workbench \
  --ledger "/path/outside/git/events.jsonl" --open-browser
```

Preview performs all import checks without writing. Admission returns a receipt with source
SHA-256, record count, and observation IDs. Identical retries return `ALREADY_IMPORTED` without
duplicating observations. Refresh the workbench: **Setup → Imported source records** shows the
receipt; **Evidence → Imported profile records** shows the values and evidence identities.

The source stays under your control; READIN does not copy or delete it. Declared retention days
are not an automated expiration mechanism, and admitted observations remain in the ledger.
See [ADR 0020](docs/adr/0020-local-source-export-observation-import.md) for the exact contract.

## Quick start

Install [uv](https://docs.astral.sh/uv/), then:

```shell
uv sync --dev
make check
make demo
make workbench
```

`make workbench` creates the closed synthetic Phase 8G ledger in a temporary directory and serves
the bounded workbench at `http://127.0.0.1:4173`. It takes no external action and removes the
temporary ledger when stopped.

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
uv run readin show-belief-revision --ledger .readin/events.jsonl \
  --revision <belief-revision-id>
uv run readin show-scenario-run --ledger .readin/events.jsonl \
  --run <scenario-run-id>
uv run readin show-discrimination-run --ledger .readin/events.jsonl \
  --run <discrimination-run-id>
uv run readin create-forecast-evaluation-design --ledger .readin/events.jsonl \
  --scenario <scenario-id> --name "Evaluation design" \
  --observation-type <later-observation-type> --field <numeric-field> \
  --unit <unit> --training-cutoff <ISO-8601-cutoff-before-forecast-origin>
uv run readin show-forecast-evaluation-design --ledger .readin/events.jsonl \
  --design <forecast-evaluation-design-id>
# Phase 8C baseline branch:
uv run readin run-forecast-baseline --ledger .readin/events.jsonl \
  --design <forecast-evaluation-design-id> --value <finite-number> \
  --occurred-at <ISO-8601-time-before-forecast-origin>
uv run readin show-forecast-baseline --ledger .readin/events.jsonl \
  --baseline <forecast-baseline-id>
# Phase 8D readback selection branch, preregistered before forecast origin:
uv run readin create-readback-selection-plan --ledger .readin/events.jsonl \
  --baseline <forecast-baseline-id> --name "Readback aperture" \
  --frame <observer-frame-id> --observed-window-end <ISO-8601-time-after-horizon> \
  --ledger-admission-cutoff <ISO-8601-time-at-or-after-window-end> \
  --occurred-at <ISO-8601-time-before-forecast-origin>
uv run readin run-readback-selection --ledger .readin/events.jsonl \
  --plan <readback-selection-plan-id> \
  --occurred-at <ISO-8601-time-at-or-after-admission-cutoff>
uv run readin show-readback-selection-run --ledger .readin/events.jsonl \
  --run <readback-selection-run-id>
# Phase 8E descriptive arithmetic, only after UNIQUE_MATCH_SELECTED:
uv run readin run-forecast-residual --ledger .readin/events.jsonl \
  --selection-run <readback-selection-run-id> \
  --occurred-at <ISO-8601-time-at-or-after-selection>
uv run readin show-forecast-residual --ledger .readin/events.jsonl \
  --residual <forecast-residual-id>
# Phase 8F fail-closed validity-update eligibility gate:
uv run readin assess-forecast-validity-update --ledger .readin/events.jsonl \
  --residual <forecast-residual-id> \
  --occurred-at <ISO-8601-time-at-or-after-residual>
uv run readin show-forecast-validity-assessment --ledger .readin/events.jsonl \
  --assessment <forecast-validity-assessment-id>
# Phase 8G prospective-only fitter specification:
uv run readin register-forecast-fitter-specification --ledger .readin/events.jsonl \
  --asset <entity-id> --name "Linear forecast candidate" \
  --model-family LINEAR_REGRESSION \
  --target-observation-type <observation-type> --target-field <numeric-field> \
  --target-unit <unit> \
  --feature-json '{"name":"prior_value","observation_type":"<observation-type>","structured_field_path":["<numeric-field>"],"unit":"<unit>"}'
uv run readin show-forecast-fitter-specification --ledger .readin/events.jsonl \
  --specification <forecast-fitter-specification-id>
# Phase 8A no-baseline branch only; omit run-forecast-baseline:
uv run readin run-residual-readback --ledger .readin/events.jsonl \
  --scenario-run <scenario-run-id> --observation <later-observation-id>
uv run readin show-residual-readback --ledger .readin/events.jsonl \
  --readback <readback-id>
uv run readin show-workbench --ledger .readin/events.jsonl --asset <entity-id>
uv run readin workbench --ledger .readin/events.jsonl --host 127.0.0.1 --port 4173 --open-browser
```

Data commands emit JSON so their identifiers can be captured by scripts; `workbench` starts the
local server until interrupted. `--case-dir` may be used instead of `--ledger` when the ledger is
the case's canonical `events.jsonl`. Run `uv run readin --help` for the complete interface.

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
