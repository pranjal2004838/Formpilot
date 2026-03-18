const DEFAULT_SETTINGS = {
  apiBase: "http://127.0.0.1:8010",
  documentType: "passport",
  country: "IN",
  appType: "passport"
};

const statusEl = document.getElementById("status");
const resultListEl = document.getElementById("resultList");
const runBtn = document.getElementById("runBtn");
const saveBtn = document.getElementById("saveBtn");

const apiBaseEl = document.getElementById("apiBase");
const fileEl = document.getElementById("identityFile");
const documentTypeEl = document.getElementById("documentType");
const countryEl = document.getElementById("country");
const appTypeEl = document.getElementById("appType");

document.addEventListener("DOMContentLoaded", init);
runBtn.addEventListener("click", runAutofill);
saveBtn.addEventListener("click", saveSettings);

async function init() {
  const values = await storageGet(DEFAULT_SETTINGS);
  apiBaseEl.value = values.apiBase || DEFAULT_SETTINGS.apiBase;
  documentTypeEl.value = values.documentType || DEFAULT_SETTINGS.documentType;
  countryEl.value = values.country || DEFAULT_SETTINGS.country;
  appTypeEl.value = values.appType || DEFAULT_SETTINGS.appType;
  setStatus("Ready.");
}

async function saveSettings() {
  await storageSet(getCurrentSettings());
  setStatus("Settings saved.", "ok");
}

async function runAutofill() {
  clearResults();

  try {
    const file = fileEl.files && fileEl.files[0];
    if (!file) {
      throw new Error("Upload an identity document first.");
    }

    await storageSet(getCurrentSettings());
    setBusy(true);

    const targetTab = await resolveTargetTab();
    if (!targetTab || !targetTab.id) {
      throw new Error("Could not identify the current tab.");
    }

    if (!/^https?:/i.test(targetTab.url || "")) {
      throw new Error("Open a normal http/https form page before running autofill.");
    }

    setStatus("Scanning fields on the active page…");
    await ensureContentScript(targetTab.id);
    const discovery = await sendMessageToTab(targetTab.id, { type: "DISCOVER_FIELDS" });

    if (!discovery || !discovery.ok) {
      throw new Error(discovery && discovery.error ? discovery.error : "Could not scan form fields.");
    }

    const formFields = discovery.fields || [];
    if (!formFields.length) {
      throw new Error("No fillable form fields found on this page.");
    }

    setStatus(`Found ${formFields.length} form fields. Sending document to FormPilot…`);

    const payload = {
      document_image: await toBase64(file),
      document_type: documentTypeEl.value,
      country: countryEl.value,
      app_type: appTypeEl.value,
      form_title: "FormPilot Extension Autofill",
      form_fields: formFields,
      notify_slack: false,
      upload_sharepoint: false,
      hitl_enabled: false
    };

    const apiBase = normalizeApiBase(apiBaseEl.value);
    const startData = await postJson(`${apiBase}/api/workflows/start`, payload);
    const workflowId = startData.workflow_id;
    if (!workflowId) {
      throw new Error("Workflow did not return a workflow_id.");
    }

    const terminalStatus = await waitForWorkflow(apiBase, workflowId);

    if (terminalStatus.status === "failed" || terminalStatus.status === "rejected") {
      throw new Error(terminalStatus.message || "Workflow failed before autofill.");
    }

    if (terminalStatus.status === "awaiting_user_interaction") {
      throw new Error(
        "Workflow requires user interaction (CAPTCHA/OTP/password). Complete that in web app mode."
      );
    }

    const result = await getJson(`${apiBase}/api/workflows/${workflowId}/result`);
    const mappings = Array.isArray(result.mappings) ? result.mappings : [];

    if (!mappings.length) {
      throw new Error("No mapped values returned by FormPilot.");
    }

    setStatus(`Applying ${mappings.length} mapped values to page…`);
    const applyResult = await sendMessageToTab(targetTab.id, {
      type: "APPLY_MAPPINGS",
      mappings
    });

    if (!applyResult || !applyResult.ok) {
      throw new Error(applyResult && applyResult.error ? applyResult.error : "Autofill failed.");
    }

    setStatus(
      `Done. Filled ${applyResult.filled} field(s), skipped ${applyResult.skipped}.`,
      "ok"
    );

    const resultLines = [];
    resultLines.push(`Detected fields: ${formFields.length}`);
    resultLines.push(`Mappings returned: ${mappings.length}`);
    resultLines.push(`Filled fields: ${applyResult.filled}`);
    resultLines.push(`Skipped fields: ${applyResult.skipped}`);

    const sampleApplied = (applyResult.applied || []).slice(0, 5);
    sampleApplied.forEach((item) => {
      resultLines.push(`${item.field}: ${item.value}`);
    });

    renderResults(resultLines);
  } catch (error) {
    setStatus(error.message || "Unexpected extension error.", "err");
  } finally {
    setBusy(false);
  }
}

function getCurrentSettings() {
  return {
    apiBase: normalizeApiBase(apiBaseEl.value),
    documentType: documentTypeEl.value,
    country: countryEl.value,
    appType: appTypeEl.value
  };
}

function normalizeApiBase(value) {
  const raw = String(value || "").trim();
  const fallback = DEFAULT_SETTINGS.apiBase;
  if (!raw) return fallback;
  return raw.replace(/\/$/, "");
}

async function resolveTargetTab() {
  const params = new URLSearchParams(window.location.search);
  const tabIdParam = params.get("tabId");

  if (tabIdParam && /^\d+$/.test(tabIdParam)) {
    const tabId = Number(tabIdParam);
    return getTabById(tabId);
  }

  const tabs = await queryTabs({ active: true, currentWindow: true });
  return tabs && tabs.length ? tabs[0] : null;
}

async function ensureContentScript(tabId) {
  try {
    const ping = await sendMessageToTab(tabId, { type: "PING" });
    if (ping && ping.ok) return;
  } catch (_ignored) {
    // Try injecting content script when tab has not loaded it yet.
  }

  await executeScript(tabId, ["content.js"]);

  const ping = await sendMessageToTab(tabId, { type: "PING" });
  if (!ping || !ping.ok) {
    throw new Error("Could not initialize content script on this page.");
  }
}

async function waitForWorkflow(apiBase, workflowId) {
  const maxAttempts = 75;
  const delayMs = 1200;

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    const status = await getJson(`${apiBase}/api/workflows/${workflowId}/status`);
    const msg = status.message || `Step ${status.step || 0}`;
    setStatus(`Workflow ${status.status}: ${msg}`);

    if (["completed", "failed", "rejected", "awaiting_user_interaction"].includes(status.status)) {
      return status;
    }

    await sleep(delayMs);
  }

  throw new Error("Workflow timed out. Try again or check API health.");
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body)
  });

  let data = {};
  try {
    data = await response.json();
  } catch (_ignored) {
    data = {};
  }

  if (!response.ok) {
    const detail = typeof data.detail === "string"
      ? data.detail
      : data.detail && data.detail.message
        ? data.detail.message
        : JSON.stringify(data.detail || data || {});
    throw new Error(detail || `Request failed (${response.status}).`);
  }

  return data;
}

async function getJson(url) {
  const response = await fetch(url);

  let data = {};
  try {
    data = await response.json();
  } catch (_ignored) {
    data = {};
  }

  if (!response.ok) {
    throw new Error(data.detail || `Request failed (${response.status}).`);
  }

  return data;
}

function toBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || "");
      const comma = result.indexOf(",");
      if (comma < 0) {
        reject(new Error("Could not read file data."));
        return;
      }
      resolve(result.slice(comma + 1));
    };
    reader.onerror = () => reject(new Error("Could not load document file."));
    reader.readAsDataURL(file);
  });
}

function setBusy(busy) {
  runBtn.disabled = busy;
  saveBtn.disabled = busy;
  fileEl.disabled = busy;
  apiBaseEl.disabled = busy;
  documentTypeEl.disabled = busy;
  countryEl.disabled = busy;
  appTypeEl.disabled = busy;

  if (busy) {
    runBtn.textContent = "Running…";
  } else {
    runBtn.textContent = "Analyze and Autofill";
  }
}

function setStatus(text, cls) {
  statusEl.textContent = text;
  statusEl.className = "status";
  if (cls) {
    statusEl.classList.add(cls);
  }
}

function clearResults() {
  resultListEl.innerHTML = "";
}

function renderResults(lines) {
  clearResults();
  lines.forEach((line) => {
    const li = document.createElement("li");
    li.textContent = line;
    resultListEl.appendChild(li);
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function storageGet(defaults) {
  return new Promise((resolve) => chrome.storage.sync.get(defaults, resolve));
}

function storageSet(values) {
  return new Promise((resolve) => chrome.storage.sync.set(values, resolve));
}

function queryTabs(queryInfo) {
  return new Promise((resolve) => chrome.tabs.query(queryInfo, resolve));
}

function getTabById(tabId) {
  return new Promise((resolve, reject) => {
    chrome.tabs.get(tabId, (tab) => {
      const err = chrome.runtime.lastError;
      if (err) {
        reject(new Error(err.message));
        return;
      }
      resolve(tab);
    });
  });
}

function executeScript(tabId, files) {
  return new Promise((resolve, reject) => {
    chrome.scripting.executeScript(
      {
        target: { tabId },
        files
      },
      () => {
        const err = chrome.runtime.lastError;
        if (err) {
          reject(new Error(err.message));
          return;
        }
        resolve();
      }
    );
  });
}

function sendMessageToTab(tabId, payload) {
  return new Promise((resolve, reject) => {
    chrome.tabs.sendMessage(tabId, payload, (response) => {
      const err = chrome.runtime.lastError;
      if (err) {
        reject(new Error(err.message));
        return;
      }
      resolve(response);
    });
  });
}
