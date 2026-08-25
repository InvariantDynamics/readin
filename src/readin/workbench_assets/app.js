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
const titleCase = (value) =>
  String(value ?? "").toLowerCase().replaceAll("_", " ").replaceAll(".", " ");

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
  const design = asset.forecasting.latest_evaluation_design;
  const baseline = asset.forecasting.latest_baseline;
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
        <p>${baseline ? "A user-declared constant baseline was frozen before forecast origin. It used no training observations and remains uncalibrated and empirically unvalidated; residual scoring is still disabled." : `${escapeHtml(design.metric_name)} was recorded before the forecast origin using a ledger-recorded training cutoff. Post-cutoff input is excluded. The target and metric remain user-declared and unvalidated; no forecast-capable fitter is registered.`}</p>
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
    const updates = `<ul class="record-list">
      <li class="record-row"><div class="record-primary">Residual</div><div class="record-secondary">Selection is not scoring</div>${stateTag(selection.residual_state)}</li>
      <li class="record-row"><div class="record-primary">Calibration</div><div class="record-secondary">Forecast skill remains unestablished</div>${stateTag(selection.calibration_state)}</li>
      <li class="record-row"><div class="record-primary">Fitter validity</div><div class="record-secondary">No validity claim is justified</div>${stateTag(selection.validity_update_state)}</li>
      <li class="record-row"><div class="record-primary">Learning</div><div class="record-secondary">No model or weight update</div>${stateTag(selection.learning_state)}</li>
    </ul>`;
    return `<div class="overview-grid">
      ${sectionCard("Forecast evaluation design", design?.name ?? "none", designBody, true)}
      ${sectionCard("Predeclared readback aperture", selection.name, aperture, true)}
      ${sectionCard("Exactly-one selection", selection.selection_state, selectionResult, true)}
      ${sectionCard("Scoring boundary", selection.residual_scoring_state, updates, true)}
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
