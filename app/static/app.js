const sampleSets = {
  "thai-id": [
    {
      name: "Synthetic Thai ID",
      detail: "Clearly marked, non-valid KYC fixture",
      url: "/samples/thai_id/synthetic_thai_id.png",
    },
  ],
  "medical-receipt": [
    {
      name: "Synthetic medical receipt",
      detail: "Clearly marked, fictional claim fixture",
      url: "/samples/thai_medical_receipt/synthetic_medical_receipt.png",
    },
  ],
};

const endpoints = {
  "thai-id": "/api/v1/validate/thai-id",
  "medical-receipt": "/api/v1/validate/medical-receipt",
};

const qualityDispositionLabels = {
  CONTINUE: "QUALITY PASSED",
  HUMAN_REVIEW: "REVIEW REQUIRED",
  REQUEST_RESUBMISSION: "RESUBMISSION REQUIRED",
};

const state = { documentType: "thai-id", file: null, previewUrl: null };

const tabs = [...document.querySelectorAll(".doc-tab")];
const dropZone = document.querySelector("#drop-zone");
const fileInput = document.querySelector("#file-input");
const emptyUpload = document.querySelector("#empty-upload");
const previewWrap = document.querySelector("#preview-wrap");
const previewImage = document.querySelector("#preview-image");
const fileName = document.querySelector("#file-name");
const fileSize = document.querySelector("#file-size");
const removeFile = document.querySelector("#remove-file");
const validateButton = document.querySelector("#validate-button");
const sampleList = document.querySelector("#sample-list");
const resultSection = document.querySelector("#result-section");

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function clearPreview() {
  if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
  state.file = null;
  state.previewUrl = null;
  fileInput.value = "";
  previewImage.hidden = false;
  previewImage.removeAttribute("src");
  previewWrap.hidden = true;
  emptyUpload.hidden = false;
  validateButton.disabled = true;
  document.querySelectorAll(".sample-card").forEach((card) => card.classList.remove("selected"));
}

function selectFile(file, sampleUrl = null) {
  if (!file || !["image/jpeg", "image/png", "application/pdf"].includes(file.type)) {
    showRequestError("Choose a JPG, JPEG, PNG, or single-page PDF.");
    return;
  }
  if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
  state.file = file;
  state.previewUrl = URL.createObjectURL(file);
  const isPdf = file.type === "application/pdf";
  previewImage.hidden = isPdf;
  if (isPdf) {
    previewImage.removeAttribute("src");
  } else {
    previewImage.src = state.previewUrl;
  }
  fileName.textContent = file.name;
  fileSize.textContent = formatBytes(file.size);
  emptyUpload.hidden = true;
  previewWrap.hidden = false;
  validateButton.disabled = false;
  document.querySelectorAll(".sample-card").forEach((card) => {
    card.classList.toggle("selected", card.dataset.url === sampleUrl);
  });
}

function renderSamples() {
  sampleList.replaceChildren();
  sampleSets[state.documentType].forEach((sample) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "sample-card";
    button.dataset.url = sample.url;
    button.setAttribute("aria-label", `Use sample: ${sample.name}`);

    const image = document.createElement("img");
    image.src = sample.url;
    image.alt = "";
    const copy = document.createElement("span");
    copy.className = "sample-copy";
    const name = document.createElement("strong");
    name.textContent = sample.name;
    const detail = document.createElement("small");
    detail.textContent = sample.detail;
    copy.append(name, detail);
    const arrow = document.createElement("span");
    arrow.className = "sample-arrow";
    arrow.textContent = "→";
    button.append(image, copy, arrow);

    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        const response = await fetch(sample.url);
        if (!response.ok) throw new Error("Sample image could not be loaded.");
        const blob = await response.blob();
        const filename = sample.url.split("/").pop();
        selectFile(new File([blob], filename, { type: blob.type }), sample.url);
      } catch (error) {
        showRequestError(error.message);
      } finally {
        button.disabled = false;
      }
    });
    sampleList.append(button);
  });
}

function switchDocumentType(type) {
  state.documentType = type;
  tabs.forEach((tab) => {
    const active = tab.dataset.type === type;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  clearPreview();
  resultSection.hidden = true;
  renderSamples();
}

function valueLabel(value) {
  if (value === null || value === undefined || value === "") return "Not detected";
  if (typeof value === "boolean") return value ? "Present" : "Missing";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function collectFields(data, prefix = "") {
  const fields = [];
  Object.entries(data || {}).forEach(([key, raw]) => {
    const label = prefix ? `${prefix} · ${key}` : key;
    if (Array.isArray(raw)) {
      raw.forEach((item, index) => fields.push(...collectFields(item, `${key} ${index + 1}`)));
    } else if (raw && typeof raw === "object" && Object.hasOwn(raw, "value")) {
      fields.push({ label, value: raw.value, confidence: raw.confidence });
    } else if (raw && typeof raw === "object") {
      fields.push(...collectFields(raw, label));
    } else {
      fields.push({ label, value: raw });
    }
  });
  return fields;
}

function humanize(label) {
  return label.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function renderWorkflow(workflow) {
  const action = workflow?.action || "UNAVAILABLE";
  document.querySelector("#workflow-action").textContent = humanize(action);
  document.querySelector("#workflow-explanation").textContent =
    workflow?.explanation || "No workflow evidence was returned for this request.";

  const citations = document.querySelector("#policy-citations");
  citations.replaceChildren();
  (workflow?.policy_citations || []).forEach((citation) => {
    const item = document.createElement("article");
    const policy = document.createElement("strong");
    policy.textContent = citation.policy_id;
    const title = document.createElement("span");
    title.textContent = citation.title;
    const section = document.createElement("small");
    section.textContent = citation.section;
    item.append(policy, title, section);
    citations.append(item);
  });
  if (!citations.children.length) {
    const empty = document.createElement("p");
    empty.className = "evidence-empty";
    empty.textContent = "No supporting policy citation was available.";
    citations.append(empty);
  }

  const audit = document.querySelector("#audit-trail");
  audit.replaceChildren();
  (workflow?.audit_trail || []).forEach((event) => {
    const item = document.createElement("li");
    const tool = document.createElement("strong");
    tool.textContent = humanize(event.tool);
    const outcome = document.createElement("span");
    outcome.textContent = event.outcome;
    outcome.className = event.outcome === "SUCCEEDED" ? "succeeded" : "failed";
    const summary = document.createElement("small");
    summary.textContent = event.summary;
    item.append(tool, outcome, summary);
    audit.append(item);
  });
  if (!audit.children.length) {
    const empty = document.createElement("li");
    empty.className = "evidence-empty";
    empty.textContent = "No tool events were recorded.";
    audit.append(empty);
  }
}

function renderQuality(quality) {
  const disposition = quality?.disposition || "UNAVAILABLE";
  document.querySelector("#quality-disposition").textContent =
    qualityDispositionLabels[disposition] || humanize(disposition);
  document.querySelector("#quality-explanation").textContent =
    quality?.explanation || "No quality evidence was returned for this request.";

  const signals = document.querySelector("#quality-signals");
  signals.replaceChildren();
  if (!quality?.image) {
    const empty = document.createElement("li");
    empty.textContent = "Quality signals are unavailable.";
    signals.append(empty);
    return;
  }

  const summaries = [
    `Processed image: ${quality.image.width} × ${quality.image.height}px`,
    `Focus advisory score: ${Math.round(quality.image.focus_score)}`,
  ];
  if (quality.extraction) {
    summaries.push(
      `Extracted fields present: ${Math.round(quality.extraction.field_completeness * 100)}%`,
      `Critical evidence present: ${Math.round(quality.extraction.critical_completeness * 100)}%`,
      `Mean extraction confidence: ${Math.round(quality.extraction.mean_confidence * 100)}%`,
    );
  }
  (quality.image.advisory_codes || []).forEach((code) =>
    summaries.push(`Advisory: ${humanize(code)}`),
  );
  summaries.forEach((summary) => {
    const item = document.createElement("li");
    item.textContent = summary;
    signals.append(item);
  });
}

function renderResult(payload) {
  const card = resultSection.querySelector(".result-card");
  const isApproved = payload.status === "APPROVED";
  const isReview = payload.status === "FLAGGED_FOR_REVIEW";
  const isResubmission = payload.workflow?.action === "REQUEST_RESUBMISSION";
  card.classList.toggle("rejected", !isApproved && !isReview);
  card.classList.toggle("review", isReview);

  document.querySelector("#result-symbol").textContent = isApproved ? "✓" : isReview ? "!" : "×";
  document.querySelector("#result-title").textContent = isApproved
    ? "Document is valid"
    : isReview
      ? "Manual review required"
      : isResubmission
        ? "Replacement document required"
        : "Document is not valid";
  document.querySelector("#result-reasoning").textContent = payload.reasoning || "Validation completed.";
  document.querySelector("#risk-score").textContent = `${Math.round((payload.risk_score || 0) * 100)}%`;

  const flagsList = document.querySelector("#flags-list");
  flagsList.replaceChildren();
  const flags = payload.validation_flags || [];
  if (!flags.length) {
    const pass = document.createElement("div");
    pass.className = "flag pass";
    pass.textContent = "All deterministic validation checks passed.";
    flagsList.append(pass);
  } else {
    flags.forEach((message) => {
      const flag = document.createElement("div");
      flag.className = "flag";
      flag.textContent = message;
      flagsList.append(flag);
    });
  }

  const fieldGrid = document.querySelector("#extracted-fields");
  fieldGrid.replaceChildren();
  const fields = collectFields(payload.extracted_data);
  if (!fields.length) {
    const empty = document.createElement("div");
    empty.className = "field";
    const value = document.createElement("strong");
    value.textContent = "No fields were extracted.";
    empty.append(value);
    fieldGrid.append(empty);
  } else {
    fields.forEach((item) => {
      const field = document.createElement("div");
      field.className = "field";
      const label = document.createElement("small");
      label.textContent = humanize(item.label);
      const value = document.createElement("strong");
      value.textContent = valueLabel(item.value);
      if (typeof item.confidence === "number") {
        const confidence = document.createElement("span");
        confidence.className = "confidence";
        confidence.textContent = `${Math.round(item.confidence * 100)}%`;
        value.append(confidence);
      }
      field.append(label, value);
      fieldGrid.append(field);
    });
  }

  renderQuality(payload.quality);
  renderWorkflow(payload.workflow);

  resultSection.hidden = false;
  resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

function showRequestError(message) {
  renderResult({
    status: "REJECTED",
    risk_score: 1,
    reasoning: message,
    validation_flags: ["The validation request could not be completed."],
    extracted_data: {},
  });
}

async function validateDocument() {
  if (!state.file) return;
  validateButton.disabled = true;
  validateButton.classList.add("loading");
  validateButton.querySelector(".button-label").textContent = "Checking document";
  const body = new FormData();
  body.append("file", state.file);

  try {
    const response = await fetch(endpoints[state.documentType], { method: "POST", body });
    const payload = await response.json();
    if (!response.ok) {
      const detail = typeof payload.detail === "string" ? payload.detail : "Validation failed.";
      throw new Error(detail);
    }
    renderResult(payload);
  } catch (error) {
    showRequestError(error.message || "The server could not process this document.");
  } finally {
    validateButton.disabled = false;
    validateButton.classList.remove("loading");
    validateButton.querySelector(".button-label").textContent = "Run document check";
  }
}

tabs.forEach((tab) => tab.addEventListener("click", () => switchDocumentType(tab.dataset.type)));
dropZone.addEventListener("click", () => fileInput.click());
dropZone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    fileInput.click();
  }
});
fileInput.addEventListener("change", () => selectFile(fileInput.files[0]));
removeFile.addEventListener("click", (event) => {
  event.stopPropagation();
  clearPreview();
});
["dragenter", "dragover"].forEach((eventName) => dropZone.addEventListener(eventName, (event) => {
  event.preventDefault();
  dropZone.classList.add("dragging");
}));
["dragleave", "drop"].forEach((eventName) => dropZone.addEventListener(eventName, (event) => {
  event.preventDefault();
  dropZone.classList.remove("dragging");
}));
dropZone.addEventListener("drop", (event) => selectFile(event.dataTransfer.files[0]));
validateButton.addEventListener("click", validateDocument);

fetch("/api/v1/config")
  .then((response) => response.json())
  .then((config) => {
    const pill = document.querySelector("#mode-pill");
    pill.classList.toggle("demo", config.demo_mode);
    pill.lastChild.textContent = config.demo_mode ? " Demo mode" : " Live model";
  })
  .catch(() => {
    document.querySelector("#mode-pill").lastChild.textContent = " Mode unavailable";
  });

renderSamples();
