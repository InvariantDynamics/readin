const state = {
  snapshot: null,
  selectedAssetId: null,
  activeTab: "overview",
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
const titleCase = (value) => String(value ?? "").toLowerCase().replaceAll("_", " ");

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
  if (text.includes("SUPPORT") || text.includes("MATCHED") || text === "FIT") return "is-good";
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

function emptyState() {
  return byId("empty-state-template").content.firstElementChild.outerHTML;
}

function renderCatalog() {
  const catalog = state.snapshot?.catalog ?? [];
  const filtered = catalog.filter((item) => {
    const haystack = `${item.canonical_name} ${item.entity_type} ${item.id}`.toLowerCase();
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
              <span>${escapeHtml(item.entity_type)}</span>
              <span>${item.counts.observations} obs · ${item.counts.claims} claims</span>
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

  const metrics = [
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
  const manifests = asset.evidence.manifests.length
    ? `<ul class="record-list">${asset.evidence.manifests
        .map(
          (item) => `<li class="record-row">
            <div class="record-primary">${escapeHtml(item.source_label)}<small>${shortId(item.id)}</small></div>
            <div class="record-secondary">${escapeHtml(item.source_uri)}<small>sha256:${escapeHtml(item.sha256.slice(0, 16))}… · ${item.transformation_count} transform(s)</small></div>
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
    overview: renderOverview,
    claims: renderClaims,
    evidence: renderEvidence,
    relations: renderRelations,
    belief: renderBelief,
    scenarios: renderScenarios,
    timeline: renderTimeline,
  };
  byId("view-panel").innerHTML = renderers[state.activeTab](asset);
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

document.querySelectorAll("[data-tab]").forEach((button) => {
  button.addEventListener("click", () => {
    state.activeTab = button.dataset.tab;
    document.querySelectorAll("[data-tab]").forEach((item) => {
      item.classList.toggle("is-active", item === button);
    });
    if (state.snapshot?.selected_asset) renderActiveView(state.snapshot.selected_asset);
  });
});

byId("asset-search").addEventListener("input", (event) => {
  state.search = event.target.value;
  renderCatalog();
});
byId("refresh-button").addEventListener("click", () => loadSnapshot(state.selectedAssetId));

loadSnapshot();
