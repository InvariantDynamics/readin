const state = {
  snapshot: null,
  selectedAssetId: null,
  activeTab: "case",
  search: "",
};

const byId = (id) => document.getElementById(id);

const escapeHtml = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

const shortId = (value) => (value ? value.slice(0, 8) : "—");
const titleCase = (value) =>
  String(value ?? "").toLowerCase().replaceAll("_", " ").replaceAll(".", " ");
const formatBytes = (value) => {
  const bytes = Number(value);
  if (!Number.isFinite(bytes)) return "—";
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(bytes < 10240 ? 1 : 0)} KB`;
};
const formatDate = (value) => {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) return String(value);
  return parsed.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
};

function stateClass(value) {
  const text = String(value ?? "");
  if (text.includes("INVALID") || text.includes("PROHIBITED")) return "is-danger";
  if (
    text.includes("NOT_") ||
    text.includes("UNKNOWN") ||
    text.includes("UNRESOLVED") ||
    text.includes("DEPENDENT")
  ) {
    return "is-warning";
  }
  if (
    text.includes("SUPPORT") ||
    text.includes("MATCHED") ||
    text.includes("VERIFIED") ||
    text.includes("ADMITTED") ||
    text.includes("READY") ||
    text === "FIT"
  ) {
    return "is-good";
  }
  return "is-info";
}

function stateTag(value) {
  return `<span class="state-tag ${stateClass(value)}">${escapeHtml(value)}</span>`;
}

function sectionCard(title, meta, body, wide = false) {
  return `<section class="section-card${wide ? " is-wide" : ""}">
    <div class="section-title"><h3>${escapeHtml(title)}</h3><span>${escapeHtml(meta)}</span></div>
    ${body}
  </section>`;
}

function factList(items) {
  return `<dl class="fact-list">${items
    .map(
      ([label, value]) => `<div class="fact-row">
        <dt>${escapeHtml(label)}</dt>
        <dd>${escapeHtml(value)}</dd>
      </div>`,
    )
    .join("")}</dl>`;
}

function emptyState() {
  return byId("empty-state-template").content.firstElementChild.outerHTML;
}

function renderCatalog() {
  const catalog = state.snapshot?.catalog ?? [];
  const filtered = catalog.filter((item) => {
    const haystack = `${item.canonical_name} ${item.entity_type} ${item.asset_class ?? ""} ${item.platform ?? ""} ${item.connection_state ?? ""} ${item.id}`.toLowerCase();
    return haystack.includes(state.search.toLowerCase());
  });
  byId("asset-count").textContent = String(catalog.length);
  byId("asset-list").innerHTML = filtered.length
    ? filtered
        .map(
          (item) => `<button class="asset-item${item.id === state.selectedAssetId ? " is-active" : ""}"
            type="button" data-asset-id="${escapeHtml(item.id)}">
            <span class="asset-item-name">${escapeHtml(item.canonical_name)}</span>
            <span class="asset-item-meta">
              <span>${escapeHtml(item.asset_class ?? item.entity_type)}</span>
              <span>${escapeHtml(item.platform ?? "local")} · ${item.counts.observations} obs</span>
            </span>
            <span class="asset-item-connection">
              ${stateTag(item.connection_state ?? "UNBOUND")}
            </span>
          </button>`,
        )
        .join("")
    : `<div class="empty-state"><span class="empty-glyph">∅</span><h3>No matching assets</h3></div>`;

  document.querySelectorAll("[data-asset-id]").forEach((button) => {
    button.addEventListener("click", () => loadSnapshot(button.dataset.assetId));
  });
}

function renderHeader(asset) {
  byId("asset-type").textContent = asset.identity.entity_type;
  byId("asset-id-short").textContent = shortId(asset.identity.id);
  byId("asset-name").textContent = asset.identity.canonical_name;
  byId("asset-aliases").textContent = asset.identity.aliases.length
    ? `Aliases: ${asset.identity.aliases.join(", ")}`
    : "No aliases recorded";
  byId("state-version").textContent = asset.tracking.state_version;

  const caseFile = state.snapshot.case;
  const metrics = caseFile
    ? [
        [asset.counts.observations, "Observations"],
        [asset.counts.claims, "Claims"],
        [asset.counts.evidence_manifests, "Artifacts"],
        [caseFile.budgets.network_requests_used, "Requests used"],
        [state.snapshot.generated_from.event_count, "Ledger events"],
        [asset.counts.relations, "Relations"],
      ]
    : [
        [asset.counts.observations, "Observations"],
        [asset.counts.claims, "Claims"],
        [asset.counts.observer_frames, "Frames"],
        [asset.counts.dependency_edges, "Dependencies"],
        [asset.counts.hypotheses, "Hypotheses"],
        [asset.counts.scenarios, "Scenarios"],
      ];
  byId("metric-strip").innerHTML = metrics
    .map(
      ([value, label]) => `<div class="metric">
        <span class="metric-value">${escapeHtml(value)}</span>
        <span class="metric-label">${escapeHtml(label)}</span>
      </div>`,
    )
    .join("");
}

function renderLimits() {
  const labels = {
    coverage_state: "Coverage",
    completeness_claim: "Completeness",
    probability_state: "Probability",
    prediction_state: "Prediction",
    trajectory_state: "Trajectory",
    empirical_validity_state: "Empirical validity",
    consensus_state: "Consensus",
    collection_state: "Collection",
    acquisition_state: "Acquisition",
    source_independence_state: "Source independence",
    residual_state: "Residual",
    validity_update_state: "Validity update",
    learning_state: "Learning",
  };
  byId("limit-list").innerHTML = Object.entries(state.snapshot.epistemic_limits)
    .map(
      ([key, value]) => `<div class="limit-row">
        <dt>${escapeHtml(labels[key] ?? titleCase(key))}</dt>
        <dd>${escapeHtml(value)}</dd>
      </div>`,
    )
    .join("");
}

function renderCase(asset) {
  const caseFile = state.snapshot.case;
  if (!caseFile) {
    return `<div class="case-view">
      <section class="case-hero is-unbound">
        <div>
          <span class="eyebrow">Local ledger</span>
          <h2>No policy-bound real-asset case</h2>
          <p>This ledger can be inspected locally, but it has no H0 case policy or acquisition-custody chain.</p>
        </div>
        ${stateTag("NO_AUTHORITY")}
      </section>
    </div>`;
  }

  const observation = asset.evidence.observations.find(
    (item) => item.provenance.adapter === "github-public-rest",
  );
  const repositoryEnvelope = observation?.content?.structured_payload?.repository;
  const repository = repositoryEnvelope?.repository;
  const owner = repositoryEnvelope?.owner;
  const custody = `<ol class="custody-chain">${caseFile.custody.checks
    .map(
      (item, index) => `<li>
        <span class="custody-index">${String(index + 1).padStart(2, "0")}</span>
        <div><strong>${escapeHtml(item.component)}</strong><small>${escapeHtml(item.detail)}</small></div>
        ${stateTag(item.state)}
      </li>`,
    )
    .join("")}</ol>`;
  const exclusions = [
    ["Contributors", caseFile.minimization.contributors],
    ["Commit authors", caseFile.minimization.commit_authors],
    ["Organization members", caseFile.minimization.organization_members],
    ["Issues and pull requests", caseFile.minimization.issues_and_pull_requests],
    ["External URL following", caseFile.minimization.automatic_external_url_following],
  ];
  const exclusionRows = `<ul class="exclusion-list">${exclusions
    .map(
      ([label, value]) => `<li><span>${escapeHtml(label)}</span>${stateTag(value)}</li>`,
    )
    .join("")}</ul>`;
  const repositoryBody = repository
    ? `<div class="repository-summary">
        <p>${escapeHtml(repository.description || "No source description returned.")}</p>
        <div class="repository-stat-grid">
          <div><strong>${escapeHtml(repository.language || "—")}</strong><span>Language</span></div>
          <div><strong>${escapeHtml(repository.license_spdx_id || "—")}</strong><span>License</span></div>
          <div><strong>${escapeHtml(repository.default_branch)}</strong><span>Default branch</span></div>
          <div><strong>${escapeHtml(repository.open_issues_count)}</strong><span>Open issues</span></div>
          <div><strong>${escapeHtml(repository.stargazers_count)}</strong><span>Stars</span></div>
          <div><strong>${escapeHtml(repository.forks_count)}</strong><span>Forks</span></div>
        </div>
        ${factList([
          ["Owner", `${owner?.login ?? "—"} · ${owner?.type ?? "—"}`],
          ["Visibility", repository.visibility],
          ["Created", formatDate(repository.created_at)],
          ["Last source update", formatDate(repository.updated_at)],
          ["Last push", formatDate(repository.pushed_at)],
          ["Verification", repositoryEnvelope.verification_state],
        ])}
      </div>`
    : emptyState();

  return `<div class="case-view">
    <section class="case-hero">
      <div>
        <span class="eyebrow">Validated local case · ${escapeHtml(shortId(caseFile.case_id))}</span>
        <h2>${escapeHtml(caseFile.purpose.statement)}</h2>
        <p>${escapeHtml(caseFile.target.github.request_url)}</p>
      </div>
      <div class="case-status">
        <span>Collection result</span>
        ${stateTag(caseFile.collection.result)}
      </div>
    </section>

    <section class="case-summary-strip" aria-label="Case boundaries">
      <div><strong>${caseFile.budgets.network_requests_used}/${caseFile.budgets.max_network_requests}</strong><span>Network requests</span></div>
      <div><strong>${caseFile.budgets.artifacts_admitted}/${caseFile.budgets.max_artifacts}</strong><span>Artifacts admitted</span></div>
      <div><strong>${caseFile.budgets.max_relation_hops}</strong><span>Relation hops</span></div>
      <div><strong>${escapeHtml(caseFile.source.authentication_mode)}</strong><span>Authentication</span></div>
      <div><strong>${formatBytes(caseFile.evidence?.size)}</strong><span>Retained bytes</span></div>
    </section>

    <div class="overview-grid case-grid">
      ${sectionCard(
        "Case contract",
        caseFile.state,
        factList([
          ["Purpose class", caseFile.purpose.kind],
          ["Subject class", caseFile.target.subject_class],
          ["Authorization basis", caseFile.target.authorization_basis],
          ["Declared", formatDate(caseFile.declared_at)],
          ["Retention review", formatDate(caseFile.retention.delete_at)],
          ["Secondary use", caseFile.purpose.secondary_use],
        ]),
      )}
      ${sectionCard(
        "Source scope",
        "EXACT TARGET ONLY",
        factList([
          ["Connector", caseFile.source.connector],
          ["Allowed host", caseFile.source.allowed_host],
          ["Access policy", caseFile.source.access_policy],
          ["Authentication", caseFile.source.authentication_mode],
          ["Redirects", caseFile.source.redirect_policy],
          ["Proxy", caseFile.source.proxy_policy],
        ]),
      )}
      ${sectionCard("Evidence custody", caseFile.custody.state, custody, true)}
      ${sectionCard("Observed repository record", observation ? formatDate(observation.observed_at) : "none", repositoryBody, true)}
      ${sectionCard("Excluded by policy", "MINIMIZATION", exclusionRows)}
      ${sectionCard(
        "Interpretation boundary",
        "NO_AUTHORITY",
        `<div class="boundary-copy">
          <p>This is one source-reported repository response from one public endpoint.</p>
          <p>It is an immutable observation, not a verified fact, independent source, resolved identity, claim, belief, prediction, or permission to act.</p>
        </div>`,
      )}
    </div>
  </div>`;
}

function renderAudit() {
  const caseFile = state.snapshot.case;
  const audit = caseFile?.audit;
  if (!audit) {
    return `<div class="case-view">
      <section class="case-hero is-unbound">
        <div>
          <span class="eyebrow">Audit</span>
          <h2>No H0 audit chain is available</h2>
          <p>This ledger was not opened through a policy-bound real-asset case read gate.</p>
        </div>
        ${stateTag("NO_AUTHORITY")}
      </section>
    </div>`;
  }

  const files = `<ul class="record-list">${audit.files
    .map(
      (item) => `<li class="record-row audit-file-row">
        <div class="record-primary">${escapeHtml(item.label)}<small>${formatBytes(item.size)}</small></div>
        <div class="record-secondary">${escapeHtml(item.path)}
          <small>${item.sha256 ? `sha256:${escapeHtml(item.sha256)}` : "no digest recorded"}</small>
        </div>
        ${stateTag(item.state)}
      </li>`,
    )
    .join("")}</ul>`;
  const events = `<ol class="audit-sequence">${audit.ledger_events
    .map(
      (item) => `<li>
        <span class="audit-index">${String(item.index).padStart(2, "0")}</span>
        <div>
          <strong>${escapeHtml(item.event_type)}</strong>
          <small>${escapeHtml(item.payload_label)}</small>
          <small>${escapeHtml(item.occurred_at)}</small>
        </div>
        <div class="audit-event-state">
          <small>${escapeHtml(shortId(item.event_id))}</small>
          ${stateTag(item.authority_state)}
        </div>
      </li>`,
    )
    .join("")}</ol>`;
  const response = caseFile.evidence
    ? `<div class="aperture-grid">
        <div class="aperture-cell"><strong>${escapeHtml(caseFile.evidence.http_status)}</strong><span>HTTP status</span></div>
        <div class="aperture-cell"><strong>${escapeHtml(caseFile.evidence.media_type)}</strong><span>Media type</span></div>
        <div class="aperture-cell"><strong>${formatBytes(caseFile.evidence.size)}</strong><span>Artifact size</span></div>
        <div class="aperture-cell"><strong>${escapeHtml(caseFile.source.authentication_mode)}</strong><span>Credential state</span></div>
      </div>
      ${factList([
        ["Receipt", caseFile.evidence.receipt_id],
        ["Receipt digest", `sha256:${caseFile.evidence.receipt_sha256}`],
        ["Artifact digest", `sha256:${caseFile.evidence.artifact_sha256}`],
        ["Acquired", formatDate(caseFile.evidence.acquired_at)],
      ])}`
    : `<div class="collection-boundary">
        <div><span>Receipt</span><strong>No source artifact admitted</strong></div>
        <div class="collection-boundary-states">
          ${stateTag(caseFile.collection.result)}
          ${stateTag(caseFile.collection.attempt_state)}
        </div>
        <p>The one-request marker exists, but no artifact is available to inspect in this case.</p>
      </div>`;

  return `<div class="case-view audit-view">
    <section class="case-summary-strip audit-summary" aria-label="Audit summary">
      <div><strong>${escapeHtml(audit.read_gate)}</strong><span>Read gate</span></div>
      <div><strong>${escapeHtml(audit.sequence_state)}</strong><span>Ledger sequence</span></div>
      <div><strong>${escapeHtml(audit.event_count)}</strong><span>Ledger events</span></div>
      <div><strong>${escapeHtml(audit.raw_artifact_preview)}</strong><span>Raw artifact preview</span></div>
      <div><strong>${escapeHtml(audit.authority_state)}</strong><span>Authority</span></div>
    </section>
    <div class="overview-grid">
      ${sectionCard("Local case paths", "owner-local files", factList([
        ["Case directory", audit.case_dir],
        ["Ledger", audit.ledger_path],
      ]), true)}
      ${sectionCard("Case files", "validated after read gate", files, true)}
      ${sectionCard("Receipt and response", caseFile.collection.result, response, true)}
      ${sectionCard("Ledger event sequence", audit.sequence_state, events, true)}
    </div>
  </div>`;
}

function renderSetup(asset) {
  const setup = asset.governance.source_setup;
  const catalog = state.snapshot.asset_catalog;
  const grant = asset.governance.connector_grant;
  if (!setup) {
    return `<div class="case-view">
      <section class="case-hero is-unbound">
        <div>
          <span class="eyebrow">Source setup</span>
          <h2>No asset-catalog binding</h2>
          <p>This asset was not imported from a local personal-asset manifest. It can still be inspected as a tracked asset, but no connector intent is recorded.</p>
        </div>
        ${stateTag(asset.governance.state)}
      </section>
    </div>`;
  }

  const nextAction =
    setup.collection_mode === "LOCAL_EXPORT_IMPORT_ONLY"
      ? "Next mechanism: add a source-specific local export parser and admit selected records as observations."
      : setup.collection_mode === "API_CONNECTION_REQUIRES_SEPARATE_GRANT"
        ? grant
          ? "Next mechanism: implement a source-specific connector runner behind this recorded grant; live collection is still disabled."
          : "Next mechanism: create a separate connector grant contract before any OAuth or API read can occur."
        : "Next mechanism: enter or attach source observations manually through the local ledger.";
  const classes = catalog.asset_class_counts ?? {};
  const connections = catalog.connection_state_counts ?? {};
  const classRows = Object.entries(classes)
    .map(
      ([label, value]) => `<li class="record-row">
        <div class="record-primary">${escapeHtml(titleCase(label))}</div>
        <div class="record-secondary">Declared asset class</div>
        ${stateTag(value)}
      </li>`,
    )
    .join("");
  const connectionRows = Object.entries(connections)
    .map(
      ([label, value]) => `<li class="record-row">
        <div class="record-primary">${escapeHtml(label)}</div>
        <div class="record-secondary">Connector state count</div>
        ${stateTag(value)}
      </li>`,
    )
    .join("");

  const setupBody = `<div class="collection-boundary">
    <div><span>${escapeHtml(setup.platform)}</span><strong>${escapeHtml(setup.account_identifier)}</strong></div>
    <div class="collection-boundary-states">
      ${stateTag(setup.connection_state)}
      ${stateTag(setup.credential_state)}
      ${stateTag(setup.live_collection_state)}
    </div>
    <p>${escapeHtml(nextAction)}</p>
  </div>
  ${factList([
    ["Asset class", setup.asset_class],
    ["Connector kind", setup.connector_kind],
    ["Collection mode", setup.collection_mode],
    ["Authorization basis", setup.authorization_basis],
    ["Owner attestation", setup.owner_attestation],
    ["Terms review", setup.terms_review_state],
    ["OAuth", setup.oauth_state],
    ["Network access", String(setup.network_access)],
    ["External action", setup.external_action_state],
    ["People targeting", setup.people_targeting],
    ["Connector grant", setup.connector_grant_state],
    ["Grant access mode", setup.connector_grant_access_mode ?? "not recorded"],
    ["Source URI", setup.source_uri ?? "not declared"],
    ["Source digest", `sha256:${setup.source_digest_sha256}`],
  ])}`;

  const scopeRows = grant
    ? grant.scopes
        .map(
          (scope) => `<li class="record-row">
            <div class="record-primary">${escapeHtml(scope.scope_name)}<small>${escapeHtml(scope.source_surface)}</small></div>
            <div class="record-secondary">${escapeHtml(scope.data_category)}<small>${escapeHtml(scope.access_intent)}</small></div>
            ${stateTag(scope.private_counterparty_data)}
          </li>`,
        )
        .join("")
    : "";
  const outputRows = grant
    ? grant.allowed_observation_types
        .map(
          (output) => `<li class="record-row">
            <div class="record-primary">${escapeHtml(output.observation_type)}</div>
            <div class="record-secondary">Claim extraction ${escapeHtml(output.claim_extraction)}</div>
            ${stateTag(output.admission_state)}
          </li>`,
        )
        .join("")
    : "";
  const grantBody = grant
    ? `<div class="collection-boundary">
        <div><span>${escapeHtml(grant.connector_name)}</span><strong>${escapeHtml(grant.grant_kind)}</strong></div>
        <div class="collection-boundary-states">
          ${stateTag(grant.grant_state)}
          ${stateTag(grant.collection_state)}
          ${stateTag(grant.live_collection_state)}
        </div>
        <p>Grant manifest recorded as evidence-backed observation ${escapeHtml(grant.observation_id)}. It stores no credentials and authorizes no runtime collection.</p>
      </div>
      ${factList([
        ["Access mode", grant.access_mode],
        ["OAuth", grant.oauth_state],
        ["Credential material", grant.credential_material],
        ["Credential storage", grant.credential_storage],
        ["Terms review", grant.terms_review_state],
        ["Network access", String(grant.network_access)],
        ["External action", grant.external_action_state],
        ["People targeting", grant.people_targeting],
        ["Activation requirement", grant.activation_requirement],
        ["Revocation", grant.revocation.state],
        ["Grant digest", `sha256:${grant.source_digest_sha256}`],
      ])}
      <h3>Declared scopes</h3>
      <ul class="record-list">${scopeRows}</ul>
      <h3>Permitted observation outputs</h3>
      <ul class="record-list">${outputRows}</ul>`
    : `<div class="collection-boundary">
        <div><span>No connector grant manifest recorded</span><strong>NOT_RECORDED</strong></div>
        <div class="collection-boundary-states">
          ${stateTag("NOT_RECORDED")}
          ${stateTag("NOT_STARTED")}
          ${stateTag("LIVE_COLLECTION_DISABLED")}
        </div>
        <p>The asset is tracked, but no source-specific scope, minimization, retention, revocation, or output contract has been admitted yet.</p>
      </div>`;

  const pipeline = `<ol class="audit-sequence">
    <li><span class="audit-index">01</span><div><strong>Declare asset</strong><small>Private local manifest, owner-attested, schema validated</small></div>${stateTag("DONE")}</li>
    <li><span class="audit-index">02</span><div><strong>Manifest source</strong><small>SHA-256 evidence identity; source path not recorded in ledger</small></div>${stateTag("ADMITTED")}</li>
    <li><span class="audit-index">03</span><div><strong>Track asset</strong><small>Entity and tracking records replay into the catalog</small></div>${stateTag("TRACKED")}</li>
    <li><span class="audit-index">04</span><div><strong>Record connector intent</strong><small>Capabilities are represented as states, not credentials or sessions</small></div>${stateTag(setup.connection_state)}</li>
    <li><span class="audit-index">05</span><div><strong>Record connector grant</strong><small>Scope, minimization, retention, revocation, and output observations are contracted separately</small></div>${stateTag(setup.connector_grant_state)}</li>
    <li><span class="audit-index">06</span><div><strong>Gate live sensors</strong><small>OAuth, account APIs, monitoring, and external action remain unavailable until a later connector runner is explicitly enabled</small></div>${stateTag("LIVE_COLLECTION_DISABLED")}</li>
  </ol>`;

  return `<div class="overview-grid">
    ${sectionCard("Asset source setup", setup.connection_state, setupBody, true)}
    ${sectionCard("Connector grant readiness", grant ? grant.grant_state : "NOT_RECORDED", grantBody, true)}
    ${sectionCard("Operational ingestion path", "manifest → catalog → observations", pipeline, true)}
    ${sectionCard("Catalog asset classes", `${catalog.asset_count} declared`, `<ul class="record-list">${classRows}</ul>`)}
    ${sectionCard("Connector states", catalog.live_collection_state, `<ul class="record-list">${connectionRows}</ul>`)}
  </div>`;
}

function renderOverview(asset) {
  const frameRows = asset.observer_frames.length
    ? `<ul class="record-list">${asset.observer_frames
        .map(
          (frame) => `<li class="record-row">
            <div class="record-primary">${escapeHtml(frame.name)}<small>${escapeHtml(frame.frame_class)}</small></div>
            <div class="record-secondary">${escapeHtml(frame.blind_regions.join(" · ") || "No blind regions recorded")}
              <small>${frame.observation_count} admitted observation(s) · ${escapeHtml(frame.access_scope)}</small>
            </div>
            ${stateTag(frame.validity_conditions.length ? "BOUNDED" : "NOT_EVALUATED")}
          </li>`,
        )
        .join("")}</ul>`
    : emptyState();

  const query = asset.cartography.latest_query;
  const aperture = query?.aperture;
  const apertureBody = query
    ? `<div class="aperture-grid">
        <div class="aperture-cell"><strong>${aperture.selected_observer_frame_count}</strong><span>Selected frames</span></div>
        <div class="aperture-cell"><strong>${aperture.included_observation_count}</strong><span>Included observations</span></div>
        <div class="aperture-cell"><strong>${aperture.excluded_asset_observation_count}</strong><span>Excluded observations</span></div>
        <div class="aperture-cell"><strong>${aperture.visited_entity_count}</strong><span>Visited entities</span></div>
      </div>
      <ul class="blind-list">${query.blind_regions.known
        .map((item) => `<li>${escapeHtml(item)}</li>`)
        .join("")}</ul>`
    : emptyState();

  const fitter = asset.fitters.latest_run;
  const fitterBody = fitter
    ? `<div class="fitter-grid">
        <div class="fitter-cell"><strong>${fitter.outcome_counts.FIT}</strong><span>Fit</span></div>
        <div class="fitter-cell"><strong>${fitter.outcome_counts.INVALID}</strong><span>Invalid</span></div>
        <div class="fitter-cell"><strong>${fitter.outcome_counts.ABSTAINED}</strong><span>Abstained</span></div>
        <div class="fitter-cell"><strong>${fitter.consensus.state}</strong><span>Consensus</span></div>
      </div>
      <ul class="record-list">${fitter.runs
        .map(
          (run) => `<li class="record-row">
            <div class="record-primary">${escapeHtml(run.fitter_class)}<small>${escapeHtml(run.name)}</small></div>
            <div class="record-secondary">${escapeHtml(run.target_metric)}<small>${escapeHtml(run.admissibility)}</small></div>
            ${stateTag(run.outcome)}
          </li>`,
        )
        .join("")}</ul>`
    : emptyState();

  const activeHypotheses = asset.belief.hypotheses.length
    ? `<ul class="record-list">${asset.belief.hypotheses
        .map(
          (item) => `<li class="record-row">
            <div class="record-primary">${escapeHtml(item.name)}<small>${shortId(item.id)}</small></div>
            <div class="record-secondary">${escapeHtml(item.statement)}<small>Probability ${escapeHtml(item.probability_state)}</small></div>
            ${stateTag(item.state)}
          </li>`,
        )
        .join("")}</ul>`
    : emptyState();

  return `<div class="overview-grid">
    ${sectionCard("Observer frames", `${asset.observer_frames.length} registered`, frameRows, true)}
    ${sectionCard("Cartographic aperture", query ? shortId(query.id) : "none", apertureBody)}
    ${sectionCard("Multi-fitter state", fitter?.disagreement.primary_status ?? "no run", fitterBody)}
    ${sectionCard("Active hypotheses", `${asset.belief.hypotheses.length} unresolved`, activeHypotheses, true)}
  </div>`;
}

function renderClaims(asset) {
  if (!asset.claims.length) return emptyState();
  const rows = asset.claims
    .map(
      (item) => `<li class="record-row">
        <div class="record-primary">${escapeHtml(item.predicate)}<small>${shortId(item.id)} · ${escapeHtml(item.modality)}</small></div>
        <div class="record-secondary">${escapeHtml(item.object_label)}
          <small>${escapeHtml(item.independence_status)} · ${item.dependency_groups.length} dependency group(s)</small>
        </div>
        ${stateTag(item.epistemic_status)}
      </li>`,
    )
    .join("");
  return sectionCard("Claims", "unresolved epistemic objects", `<ul class="record-list">${rows}</ul>`, true);
}

function renderEvidence(asset) {
  const observations = asset.evidence.observations.length
    ? `<ul class="record-list">${asset.evidence.observations
        .map(
          (item) => `<li class="record-row">
            <div class="record-primary">${escapeHtml(titleCase(item.observation_type))}<small>${shortId(item.id)} · immutable ${escapeHtml(item.immutable)}</small></div>
            <div class="record-secondary">${escapeHtml(item.provenance.source_uri)}<small>${formatDate(item.observed_at)} · ${escapeHtml(item.provenance.adapter)} ${escapeHtml(item.provenance.adapter_version)}</small></div>
            ${stateTag(item.epistemic.missingness_state)}
          </li>`,
        )
        .join("")}</ul>`
    : emptyState();
  const manifests = asset.evidence.manifests.length
    ? `<ul class="record-list">${asset.evidence.manifests
        .map(
          (item) => `<li class="record-row">
            <div class="record-primary">${escapeHtml(item.source_label)}<small>${shortId(item.id)}</small></div>
            <div class="record-secondary">${escapeHtml(item.source_uri)}<small>${formatBytes(item.size)} · ${escapeHtml(item.media_type)} · ${formatDate(item.acquired_at)}</small><small>sha256:${escapeHtml(item.sha256)} · ${item.transformation_count} transform(s)</small></div>
            ${stateTag(item.access_policy)}
          </li>`,
        )
        .join("")}</ul>`
    : emptyState();
  const dependencies = asset.evidence.dependencies.length
    ? `<ul class="record-list">${asset.evidence.dependencies
        .map(
          (item) => `<li class="record-row">
            <div class="record-primary">${escapeHtml(item.relationship)}<small>${shortId(item.id)}</small></div>
            <div class="record-secondary">Dependency group ${shortId(item.group_id)}</div>
            ${stateTag(item.verification_status)}
          </li>`,
        )
        .join("")}</ul>`
    : emptyState();
  return `<div class="overview-grid">
    ${sectionCard("Admitted observations", `${asset.evidence.observations.length} immutable`, observations, true)}
    ${sectionCard("Evidence manifests", `${asset.evidence.manifests.length} immutable`, manifests, true)}
    ${sectionCard("Dependency ancestry", `${asset.evidence.dependencies.length} edges`, dependencies, true)}
  </div>`;
}

function renderRelations(asset) {
  if (!asset.relations.length && !asset.resolution_candidates.length) return emptyState();
  const relations = asset.relations.length
    ? `<ul class="record-list">${asset.relations
        .map(
          (item) => `<li class="record-row">
            <div class="record-primary">${escapeHtml(item.relation_type)}<small>${shortId(item.id)}</small></div>
            <div class="record-secondary">${escapeHtml(item.source_label)} → ${escapeHtml(item.target_label)}<small>${item.claim_ids.length} backing claim(s)</small></div>
            ${stateTag(item.relation_semantics)}
          </li>`,
        )
        .join("")}</ul>`
    : emptyState();
  const candidates = asset.resolution_candidates.length
    ? `<ul class="record-list">${asset.resolution_candidates
        .map(
          (item) => `<li class="record-row">
            <div class="record-primary">${escapeHtml(item.candidate_label)}<small>${shortId(item.id)}</small></div>
            <div class="record-secondary">Reversible candidate review<small>${escapeHtml(item.merge_state)}</small></div>
            ${stateTag(item.disposition)}
          </li>`,
        )
        .join("")}</ul>`
    : emptyState();
  return `<div class="overview-grid">
    ${sectionCard("Typed relations", `${asset.relations.length} retained`, relations, true)}
    ${sectionCard("Identity candidates", `${asset.resolution_candidates.length} not merged`, candidates, true)}
  </div>`;
}

function renderBelief(asset) {
  if (!asset.belief.hypotheses.length) return emptyState();
  const revision = asset.belief.latest_revision;
  const rows = asset.belief.hypotheses
    .map(
      (item) => `<li class="record-row">
        <div class="record-primary">${escapeHtml(item.name)}<small>${shortId(item.id)}</small></div>
        <div class="record-secondary">${escapeHtml(item.statement)}<small>${escapeHtml(revision?.interpretation ?? "No revision")}</small></div>
        ${stateTag(item.state)}
      </li>`,
    )
    .join("");
  return sectionCard(
    "Categorical belief revision",
    revision ? `${shortId(revision.id)} · probability ${revision.probability_state}` : "not executed",
    `<ul class="record-list">${rows}</ul>`,
    true,
  );
}

function renderScenarios(asset) {
  if (!asset.scenarios.length) return emptyState();
  return `<div class="overview-grid">${asset.scenarios
    .map(
      (scenario) => sectionCard(
        scenario.name,
        `${scenario.horizon_days} days · likelihood ${scenario.likelihood_state}`,
        `<ul class="record-list">${scenario.branches
          .map(
            (branch) => `<li class="record-row">
              <div class="record-primary">${escapeHtml(branch.name)}<small>${escapeHtml(branch.kind)}</small></div>
              <div class="record-secondary">${escapeHtml(branch.outcome_statement)}<small>${escapeHtml(branch.outcome_state)}</small></div>
              ${stateTag(branch.antecedent_state)}
            </li>`,
          )
          .join("")}</ul>`,
        true,
      ),
    )
    .join("")}</div>`;
}

function renderCollection(asset) {
  const plan = asset.collection.latest_discrimination;
  if (!plan) return emptyState();
  const rows = plan.candidates.length
    ? `<ul class="record-list">${plan.candidates
        .map(
          (candidate) => `<li class="record-row">
            <div class="record-primary">${escapeHtml(candidate.name)}
              <small>${candidate.rank ? `rank ${candidate.rank}` : "not ranked"} · effort ${escapeHtml(candidate.effort)}</small>
            </div>
            <div class="record-secondary">${escapeHtml(candidate.question)}
              <small>${escapeHtml(candidate.observer_frame_name)} · separation ${candidate.directional_separation_units} · distinguished pairs ${candidate.distinguished_hypothesis_pair_units} · discriminating outcomes ${candidate.discriminating_outcome_count} · blind-region alignment ${candidate.blind_region_alignment_count}</small>
            </div>
            ${stateTag(candidate.discrimination_state)}
          </li>`,
        )
        .join("")}</ul>`
    : emptyState();
  const boundary = `<div class="collection-boundary">
    <div><span>Ambiguity</span><strong>${escapeHtml(plan.ambiguity_statement)}</strong></div>
    <div class="collection-boundary-states">
      ${stateTag(plan.collection_state)}
      ${stateTag(plan.acquisition_state)}
      ${stateTag(plan.source_independence_state)}
    </div>
    <p>Manual expected effects are ranked by a structural ordinal heuristic. Expected information gain and probabilities are not computed. No source was queried or acquired.</p>
  </div>`;
  return `<div class="overview-grid">
    ${sectionCard(plan.name, plan.recommendation_state, boundary, true)}
    ${sectionCard("Candidate observations", `${plan.candidates.length} manually declared`, rows, true)}
  </div>`;
}

function renderReadback(asset) {
  const item = asset.readback.latest;
  const selection = asset.readback.latest_selection;
  const residual = asset.readback.latest_forecast_residual;
  const validity = asset.readback.latest_validity_assessment;
  const design = asset.forecasting.latest_evaluation_design;
  const baseline = asset.forecasting.latest_baseline;
  const fitterSpecification = asset.forecasting.latest_fitter_specification;
  if (!item && !selection && !design) return emptyState();
  const baselineRow = baseline
    ? `<ul class="record-list"><li class="record-row">
        <div class="record-primary">${escapeHtml(baseline.prediction_value)} ${escapeHtml(baseline.unit)}<small>${escapeHtml(baseline.method_name)} · ${escapeHtml(baseline.method_state)}</small></div>
        <div class="record-secondary">Frozen before ${escapeHtml(baseline.forecast_origin)}<small>No training observations used · residual scoring ${escapeHtml(baseline.residual_scoring_state)}</small></div>
        ${stateTag(baseline.prediction_state)}
      </li></ul>`
    : "";
  const designBody = design
    ? `<div class="collection-boundary">
        <div><span>Predeclared target</span><strong>${escapeHtml(design.structured_field_path.map(titleCase).join(" → "))} · ${escapeHtml(design.unit)}</strong></div>
        <div class="collection-boundary-states">
          ${stateTag(design.preregistration_state)}
          ${stateTag(design.fitter_selection_state)}
          ${stateTag(design.prediction_state)}
        </div>
        <p>${baseline ? residual ? validity ? "A user-declared constant baseline was compared with one unique readback. The validity-update gate explicitly abstained because the evidence remains insufficient." : "A user-declared constant baseline was frozen before forecast origin. One descriptive residual has been computed against the uniquely selected readback, but calibration and empirical validity remain unestablished." : "A user-declared constant baseline was frozen before forecast origin. It used no training observations and remains uncalibrated and empirically unvalidated; residual scoring is still disabled." : `${escapeHtml(design.metric_name)} was recorded before the forecast origin using a ledger-recorded training cutoff. Post-cutoff input is excluded. The target and metric remain user-declared and unvalidated; no forecast-capable fitter is registered.`}</p>
      </div>
      <ul class="record-list"><li class="record-row">
        <div class="record-primary">${escapeHtml(titleCase(design.observation_type))}<small>${escapeHtml(design.target_semantics)}</small></div>
        <div class="record-secondary">Training cutoff ${escapeHtml(design.training_cutoff)}<small>Forecast origin ${escapeHtml(design.forecast_origin)} · horizon end ${escapeHtml(design.horizon_end)}</small></div>
        ${stateTag(design.forecast_capable_fitter_state)}
      </li></ul>${baselineRow}`
    : emptyState();
  if (selection) {
    const frameNames = selection.eligible_observer_frames.map((frame) => frame.name).join(" · ");
    const aperture = `<div class="collection-boundary">
      <div><span>Eligible observer frames</span><strong>${escapeHtml(frameNames)}</strong></div>
      <div class="collection-boundary-states">
        ${stateTag(selection.preregistration_state)}
        ${stateTag(selection.cardinality)}
        ${stateTag(selection.execution_state)}
      </div>
      <p>Observed after ${escapeHtml(selection.horizon_end)} through ${escapeHtml(selection.observed_window_end)} and admitted to the ledger by ${escapeHtml(selection.ledger_admission_cutoff)}. Zero or multiple matches require abstention; aggregation, ranking, and post-hoc selection are prohibited.</p>
    </div>
    <ul class="record-list"><li class="record-row">
      <div class="record-primary">${escapeHtml(titleCase(selection.target_observation_type))}<small>${escapeHtml(selection.structured_field_path.map(titleCase).join(" → "))} · ${escapeHtml(selection.unit)}</small></div>
      <div class="record-secondary">Unit equivalence is not independently verified<small>${escapeHtml(selection.unit_match_state)}</small></div>
      ${stateTag(selection.aggregation_policy)}
    </li></ul>`;
    const excluded = selection.excluded_counts ?? {
      after_admission_cutoff: 0,
      outside_observed_window: 0,
      observation_type_mismatch: 0,
      frame_mismatch: 0,
      invalid_target: 0,
    };
    const selectionResult = `<div class="aperture-grid">
      <div class="aperture-cell"><strong>${selection.candidate_count ?? "—"}</strong><span>Compatible candidates</span></div>
      <div class="aperture-cell"><strong>${excluded.outside_observed_window}</strong><span>Outside time window</span></div>
      <div class="aperture-cell"><strong>${excluded.frame_mismatch}</strong><span>Frame mismatch</span></div>
      <div class="aperture-cell"><strong>${excluded.after_admission_cutoff}</strong><span>Admitted after cutoff</span></div>
    </div>
    <ul class="record-list"><li class="record-row">
      <div class="record-primary">${selection.selected_target_value ?? "No value selected"}<small>${selection.selected_observation_id ? shortId(selection.selected_observation_id) : "Selector abstained or has not run"}</small></div>
      <div class="record-secondary">No ranking or aggregation performed<small>${escapeHtml(selection.ranking_state)} · ${escapeHtml(selection.aggregation_state)}</small></div>
      ${stateTag(selection.selection_state)}
    </li></ul>`;
    const residualResult = residual
      ? `<div class="aperture-grid">
          <div class="aperture-cell"><strong>${escapeHtml(residual.prediction_value)}</strong><span>Predicted</span></div>
          <div class="aperture-cell"><strong>${escapeHtml(residual.observed_value)}</strong><span>Observed</span></div>
          <div class="aperture-cell"><strong>${escapeHtml(residual.signed_residual)}</strong><span>Observed − predicted</span></div>
          <div class="aperture-cell"><strong>${escapeHtml(residual.absolute_error)}</strong><span>Absolute error</span></div>
        </div>
        <ul class="record-list"><li class="record-row">
          <div class="record-primary">${escapeHtml(residual.metric_name)}<small>${escapeHtml(residual.metric_state)}</small></div>
          <div class="record-secondary">${escapeHtml(residual.unit)}<small>Unit equivalence ${escapeHtml(residual.unit_match_state)}</small></div>
          ${stateTag(residual.residual_state)}
        </li></ul>`
      : "";
    const validityGate = validity
      ? `<div class="collection-boundary">
          <div><span>Assessment decision</span><strong>${escapeHtml(validity.decision_state)}</strong></div>
          <div class="collection-boundary-states">
            ${stateTag(validity.eligibility_state)}
            ${stateTag(validity.target_fitter_state)}
            ${stateTag(validity.validity_update_state)}
          </div>
          <p>The descriptive residual was considered for a validity update and rejected by the bounded reference gate. Insufficient warrant is not evidence of model validity or invalidity.</p>
        </div>
        <ul class="record-list">${validity.blockers
          .map(
            (blocker) => `<li class="record-row">
              <div class="record-primary">${escapeHtml(titleCase(blocker))}</div>
              <div class="record-secondary">Update blocker retained</div>
              ${stateTag("BLOCKING")}
            </li>`,
          )
          .join("")}</ul>`
      : "";
    const specificationGate = fitterSpecification
      ? `<div class="collection-boundary">
          <div><span>Prospective model family</span><strong>${escapeHtml(titleCase(fitterSpecification.model_family))}</strong></div>
          <div class="collection-boundary-states">
            ${stateTag(fitterSpecification.registration_state)}
            ${stateTag(fitterSpecification.capability_state)}
            ${stateTag(fitterSpecification.execution_state)}
          </div>
          <p>This specification was registered after the historical validity assessment. It is future-only and cannot remove or rewrite that assessment's no-fitter blocker.</p>
        </div>
        <ul class="record-list">
          <li class="record-row">
            <div class="record-primary">${escapeHtml(titleCase(fitterSpecification.target_observation_type))}<small>${escapeHtml(fitterSpecification.target_structured_field_path.map(titleCase).join(" → "))} · ${escapeHtml(fitterSpecification.target_unit)}</small></div>
            <div class="record-secondary">Target contract<small>Point prediction and uncertainty outputs remain required but unimplemented</small></div>
            ${stateTag(fitterSpecification.prediction_state)}
          </li>
          ${fitterSpecification.feature_contracts
            .map(
              (feature) => `<li class="record-row">
                <div class="record-primary">${escapeHtml(titleCase(feature.name))}<small>${escapeHtml(titleCase(feature.observation_type))}</small></div>
                <div class="record-secondary">Pre-origin numeric feature<small>${escapeHtml(feature.structured_field_path.map(titleCase).join(" → "))} · ${escapeHtml(feature.unit)}</small></div>
                ${stateTag(feature.temporal_role)}
              </li>`,
            )
            .join("")}
          <li class="record-row">
            <div class="record-primary">Training prerequisites<small>${escapeHtml(fitterSpecification.objective)} · data ${escapeHtml(fitterSpecification.training_data_state)}</small></div>
            <div class="record-secondary">Temporal split and negative controls remain unbound<small>${escapeHtml(fitterSpecification.temporal_split_state)} · ${escapeHtml(fitterSpecification.negative_controls_state)}</small></div>
            ${stateTag(fitterSpecification.training_state)}
          </li>
          <li class="record-row">
            <div class="record-primary">Historical applicability<small>Prior assessment effect ${escapeHtml(fitterSpecification.prior_assessment_effect)}</small></div>
            <div class="record-secondary">Future forecasts only<small>No design selection, implementation, or validation corpus</small></div>
            ${stateTag(fitterSpecification.retroactive_application_state)}
          </li>
        </ul>`
      : "";
    const boundary = residual ?? selection;
    const updates = `<ul class="record-list">
      <li class="record-row"><div class="record-primary">Residual</div><div class="record-secondary">${residual ? "Descriptive arithmetic only" : "Selection is not scoring"}</div>${stateTag(boundary.residual_state)}</li>
      <li class="record-row"><div class="record-primary">Calibration</div><div class="record-secondary">Forecast skill remains unestablished</div>${stateTag(boundary.calibration_state)}</li>
      <li class="record-row"><div class="record-primary">Fitter validity</div><div class="record-secondary">No validity claim is justified</div>${stateTag(boundary.validity_update_state)}</li>
      <li class="record-row"><div class="record-primary">Learning</div><div class="record-secondary">No model or weight update</div>${stateTag(boundary.learning_state)}</li>
    </ul>`;
    return `<div class="overview-grid">
      ${sectionCard("Forecast evaluation design", design?.name ?? "none", designBody, true)}
      ${sectionCard("Predeclared readback aperture", selection.name, aperture, true)}
      ${sectionCard("Exactly-one selection", selection.selection_state, selectionResult, true)}
      ${residual ? sectionCard("Descriptive reference residual", residual.residual_scoring_state, residualResult, true) : ""}
      ${validity ? sectionCard("Validity update gate", validity.decision_state, validityGate, true) : ""}
      ${fitterSpecification ? sectionCard("Prospective fitter specification", fitterSpecification.registration_state, specificationGate, true) : ""}
      ${sectionCard("Validity and learning boundary", boundary.learning_state, updates, true)}
    </div>`;
  }
  if (!item) {
    return sectionCard(baseline ? "Frozen forecast baseline" : "Forecast evaluation design", design.name, designBody, true);
  }
  const eligibility = `<div class="collection-boundary">
    <div><span>Reference scenario</span><strong>${escapeHtml(item.scenario_name)}</strong></div>
    <div class="collection-boundary-states">
      ${stateTag(item.baseline_eligibility_state)}
      ${stateTag(item.residual_state)}
      ${stateTag(item.validity_update_state)}
    </div>
    <p>A later observation is bound to the earlier scenario run, but that run produced conditional branch evaluation—not a forecast. READIN therefore retains the readback and applies no residual, validity, weighting, or admissibility update.</p>
  </div>`;
  const observation = `<div class="aperture-grid">
    <div class="aperture-cell"><strong>${item.observation_count}</strong><span>Later observations</span></div>
    <div class="aperture-cell"><strong>${escapeHtml(item.scenario_horizon_days)}</strong><span>Scenario days</span></div>
    <div class="aperture-cell"><strong>${escapeHtml(item.reference_prediction_state)}</strong><span>Prediction state</span></div>
    <div class="aperture-cell"><strong>${item.network_access ? "YES" : "NO"}</strong><span>Network access</span></div>
  </div>
  <ul class="record-list"><li class="record-row">
    <div class="record-primary">${escapeHtml(item.observation_types.map(titleCase).join(" · "))}<small>${escapeHtml(item.latest_observed_at)}</small></div>
    <div class="record-secondary">Later than the declared scenario horizon<small>${escapeHtml(item.temporal_order_state)}</small></div>
    ${stateTag(item.forecast_baseline_state)}
  </li></ul>`;
  const updates = `<ul class="record-list">
    <li class="record-row"><div class="record-primary">Fitter validity</div><div class="record-secondary">No eligible residual exists</div>${stateTag(item.validity_update_state)}</li>
    <li class="record-row"><div class="record-primary">Fitter weighting</div><div class="record-secondary">No weight change is justified</div>${stateTag(item.weighting_update_state)}</li>
    <li class="record-row"><div class="record-primary">Future admissibility</div><div class="record-secondary">No admissibility rule is changed</div>${stateTag(item.future_admissibility_update_state)}</li>
  </ul>`;
  return `<div class="overview-grid">
    ${sectionCard("Forecast evaluation design", design?.name ?? "none", designBody, true)}
    ${sectionCard("Residual readback gate", item.baseline_eligibility_state, eligibility, true)}
    ${sectionCard("Bound later observation", shortId(item.id), observation, true)}
    ${sectionCard("Update state", item.learning_state, updates, true)}
  </div>`;
}

function renderTimeline(asset) {
  if (!asset.timeline.length) return emptyState();
  const rows = asset.timeline
    .map(
      (item) => `<li class="record-row">
        <div class="record-primary">${escapeHtml(item.event_type)}<small>${shortId(item.event_id)}</small></div>
        <div class="record-secondary">Effective ${escapeHtml(item.effective_at)}<small>Recorded ${escapeHtml(item.recorded_at)}</small></div>
        ${stateTag(item.hindsight ? "HINDSIGHT" : "LEDGER_RECORDED")}
      </li>`,
    )
    .join("");
  return sectionCard("Epistemic timeline", `${asset.timeline.length} retained events`, `<ul class="record-list">${rows}</ul>`, true);
}

function renderActiveView(asset) {
  const renderers = {
    case: renderCase,
    audit: renderAudit,
    setup: renderSetup,
    overview: renderOverview,
    claims: renderClaims,
    evidence: renderEvidence,
    relations: renderRelations,
    belief: renderBelief,
    scenarios: renderScenarios,
    collection: renderCollection,
    readback: renderReadback,
    timeline: renderTimeline,
  };
  byId("view-panel").innerHTML = renderers[state.activeTab](asset);
}

function syncActiveTabButtons() {
  document.querySelectorAll("[data-tab]").forEach((item) => {
    item.classList.toggle("is-active", item.dataset.tab === state.activeTab);
  });
}

function renderSnapshot() {
  renderCatalog();
  renderLimits();
  const asset = state.snapshot.selected_asset;
  if (!asset) {
    byId("asset-type").textContent = "Catalog";
    byId("asset-id-short").textContent = "empty";
    byId("asset-name").textContent = "No tracked assets";
    byId("asset-aliases").textContent = "Add records with the local CLI, then refresh this view.";
    byId("state-version").textContent = "NO_STATE";
    byId("metric-strip").innerHTML = "";
    byId("view-panel").innerHTML = emptyState();
    return;
  }
  renderHeader(asset);
  renderActiveView(asset);
}

async function loadSnapshot(assetId = null) {
  byId("workspace").setAttribute("aria-busy", "true");
  try {
    const query = assetId ? `?asset=${encodeURIComponent(assetId)}` : "";
    const response = await fetch(`/api/workbench${query}`, { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error ?? `Request failed: ${response.status}`);
    state.snapshot = payload;
    state.selectedAssetId = payload.selected_asset?.identity.id ?? null;
    if (!payload.case && payload.selected_asset?.governance?.source_setup && state.activeTab === "case") {
      state.activeTab = "setup";
      syncActiveTabButtons();
    }
    renderSnapshot();
  } catch (error) {
    byId("view-panel").innerHTML = `<div class="error-state">
      <span class="empty-glyph">!</span><h3>Ledger replay unavailable</h3>
      <p>${escapeHtml(error.message)}. The workbench remains read-only and has taken no external action.</p>
    </div>`;
  } finally {
    byId("workspace").removeAttribute("aria-busy");
  }
}

if (document.documentElement.dataset.launchMode === "served") {
  document.querySelectorAll("[data-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeTab = button.dataset.tab;
      syncActiveTabButtons();
      if (state.snapshot?.selected_asset) renderActiveView(state.snapshot.selected_asset);
    });
  });

  byId("asset-search").addEventListener("input", (event) => {
    state.search = event.target.value;
    renderCatalog();
  });
  byId("refresh-button").addEventListener("click", () => loadSnapshot(state.selectedAssetId));

  loadSnapshot();
}
