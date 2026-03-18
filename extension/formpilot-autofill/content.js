const IGNORED_INPUT_TYPES = new Set([
  "hidden",
  "submit",
  "button",
  "reset",
  "image",
  "file"
]);

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  try {
    if (!message || !message.type) {
      sendResponse({ ok: false, error: "Invalid extension message." });
      return true;
    }

    if (message.type === "PING") {
      sendResponse({ ok: true });
      return true;
    }

    if (message.type === "DISCOVER_FIELDS") {
      const result = discoverFormFields();
      sendResponse(result);
      return true;
    }

    if (message.type === "APPLY_MAPPINGS") {
      const result = applyMappings(message.mappings || []);
      sendResponse(result);
      return true;
    }

    sendResponse({ ok: false, error: `Unknown message type: ${message.type}` });
  } catch (error) {
    sendResponse({ ok: false, error: error.message || "Content script failed." });
  }

  return true;
});

function discoverFormFields() {
  const elements = getFillableElements();
  const dedupe = new Set();
  const fields = [];

  elements.forEach((el) => {
    const descriptor = buildFieldDescriptor(el);

    const dedupeKey = [
      descriptor.name,
      descriptor.id,
      descriptor.label,
      descriptor.placeholder,
      descriptor.type
    ].join("|").toLowerCase();

    if (!dedupeKey.replace(/\|/g, "").trim()) {
      return;
    }

    if (dedupe.has(dedupeKey)) {
      return;
    }

    dedupe.add(dedupeKey);
    fields.push(descriptor);
  });

  return {
    ok: true,
    fieldCount: fields.length,
    fields
  };
}

function applyMappings(mappings) {
  const applied = [];
  const skipped = [];

  mappings.forEach((mapping) => {
    const fieldName = String(
      mapping.formField || mapping.formFieldName || mapping.target || ""
    ).trim();
    const value = mapping.value;

    if (!fieldName || value === null || value === undefined || String(value).trim() === "") {
      skipped.push({
        field: fieldName || "(unknown)",
        reason: "Missing field name or value"
      });
      return;
    }

    const element = findElementForField(fieldName);
    if (!element) {
      skipped.push({
        field: fieldName,
        reason: "No matching element in page"
      });
      return;
    }

    if (element.disabled || element.readOnly) {
      skipped.push({
        field: fieldName,
        reason: "Field is disabled or readonly"
      });
      return;
    }

    const success = setElementValue(element, String(value));
    if (!success) {
      skipped.push({
        field: fieldName,
        reason: "Value format not accepted"
      });
      return;
    }

    highlightElement(element);

    applied.push({
      field: fieldName,
      value: String(value)
    });
  });

  return {
    ok: true,
    filled: applied.length,
    skipped: skipped.length,
    applied,
    skipped
  };
}

function getFillableElements() {
  return Array.from(document.querySelectorAll("input, textarea, select")).filter((el) => {
    if (!el || !el.tagName) return false;
    if (el.disabled) return false;

    const tag = el.tagName.toLowerCase();
    if (tag === "input") {
      const type = (el.type || "text").toLowerCase();
      if (IGNORED_INPUT_TYPES.has(type)) return false;
      if (type === "radio" && !el.name) return false;
    }

    return isVisible(el);
  });
}

function isVisible(el) {
  const style = window.getComputedStyle(el);
  if (!style) return true;
  if (style.display === "none" || style.visibility === "hidden") return false;
  return true;
}

function buildFieldDescriptor(el) {
  const tag = el.tagName.toLowerCase();
  const type = tag === "input" ? (el.type || "text").toLowerCase() : tag;

  const descriptor = {
    name: (el.getAttribute("name") || "").trim(),
    id: (el.getAttribute("id") || "").trim(),
    label: resolveLabel(el),
    placeholder: (el.getAttribute("placeholder") || "").trim(),
    ariaLabel: (el.getAttribute("aria-label") || "").trim(),
    type,
    options: []
  };

  if (tag === "select") {
    descriptor.options = Array.from(el.options).slice(0, 50).map((option) => ({
      value: String(option.value || ""),
      label: String(option.textContent || "").trim()
    }));
  }

  return descriptor;
}

function resolveLabel(el) {
  if (el.labels && el.labels.length > 0) {
    return cleanText(el.labels[0].textContent);
  }

  const id = el.getAttribute("id");
  if (id) {
    const byFor = document.querySelector(`label[for="${escapeCss(id)}"]`);
    if (byFor) {
      return cleanText(byFor.textContent);
    }
  }

  const wrapped = el.closest("label");
  if (wrapped) {
    return cleanText(wrapped.textContent);
  }

  const aria = el.getAttribute("aria-label");
  if (aria) return cleanText(aria);

  const placeholder = el.getAttribute("placeholder");
  if (placeholder) return cleanText(placeholder);

  return "";
}

function findElementForField(fieldName) {
  const value = String(fieldName || "").trim();
  if (!value) return null;

  // Exact by name and id first.
  let el = document.querySelector(`[name="${escapeCss(value)}"]`);
  if (el) return el;

  el = document.getElementById(value);
  if (el) return el;

  el = document.querySelector(`[id="${escapeCss(value)}"]`);
  if (el) return el;

  // Case-insensitive exact fallback.
  const lower = value.toLowerCase();
  const fillable = getFillableElements();

  el = fillable.find((candidate) => {
    const cName = String(candidate.getAttribute("name") || "").toLowerCase();
    const cId = String(candidate.getAttribute("id") || "").toLowerCase();
    return cName === lower || cId === lower;
  });
  if (el) return el;

  // Match by label/placeholder/aria text.
  const targetNorm = normalize(value);

  el = fillable.find((candidate) => {
    const label = normalize(resolveLabel(candidate));
    const placeholder = normalize(candidate.getAttribute("placeholder") || "");
    const aria = normalize(candidate.getAttribute("aria-label") || "");
    return label === targetNorm || placeholder === targetNorm || aria === targetNorm;
  });
  if (el) return el;

  // Partial contains match as last resort.
  el = fillable.find((candidate) => {
    const joined = [
      candidate.getAttribute("name") || "",
      candidate.getAttribute("id") || "",
      resolveLabel(candidate),
      candidate.getAttribute("placeholder") || "",
      candidate.getAttribute("aria-label") || ""
    ].map(normalize).join(" ");

    return joined.includes(targetNorm);
  });

  return el || null;
}

function setElementValue(element, rawValue) {
  const tag = element.tagName.toLowerCase();

  if (tag === "select") {
    return setSelectValue(element, rawValue);
  }

  if (tag === "textarea") {
    element.focus();
    element.value = rawValue;
    dispatchInputEvents(element);
    return true;
  }

  const type = (element.type || "text").toLowerCase();

  if (type === "checkbox") {
    element.checked = parseTruthy(rawValue);
    dispatchInputEvents(element);
    return true;
  }

  if (type === "radio") {
    return setRadioValue(element, rawValue);
  }

  if (type === "date") {
    const isoDate = normalizeDateForInput(rawValue);
    if (!isoDate) {
      return false;
    }
    element.focus();
    element.value = isoDate;
    dispatchInputEvents(element);
    return true;
  }

  element.focus();
  element.value = rawValue;
  dispatchInputEvents(element);
  return true;
}

function setSelectValue(selectEl, rawValue) {
  const targetNorm = normalize(rawValue);
  const options = Array.from(selectEl.options || []);

  const exact = options.find((opt) => {
    const valueNorm = normalize(opt.value || "");
    const textNorm = normalize(opt.textContent || "");
    return valueNorm === targetNorm || textNorm === targetNorm;
  });

  const partial = exact || options.find((opt) => {
    const valueNorm = normalize(opt.value || "");
    const textNorm = normalize(opt.textContent || "");
    return valueNorm.includes(targetNorm) || textNorm.includes(targetNorm);
  });

  if (!partial) {
    return false;
  }

  selectEl.value = partial.value;
  dispatchInputEvents(selectEl);
  return true;
}

function setRadioValue(radioEl, rawValue) {
  const name = radioEl.name;
  if (!name) {
    return false;
  }

  const targetNorm = normalize(rawValue);
  const radios = Array.from(document.querySelectorAll(`input[type="radio"][name="${escapeCss(name)}"]`));

  let selected = radios.find((radio) => {
    const valueNorm = normalize(radio.value || "");
    const labelNorm = normalize(resolveLabel(radio));
    return valueNorm === targetNorm || labelNorm === targetNorm;
  });

  if (!selected) {
    selected = radios.find((radio) => {
      const valueNorm = normalize(radio.value || "");
      const labelNorm = normalize(resolveLabel(radio));
      return valueNorm.includes(targetNorm) || labelNorm.includes(targetNorm);
    });
  }

  if (!selected) {
    return false;
  }

  selected.checked = true;
  dispatchInputEvents(selected);
  return true;
}

function normalizeDateForInput(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";

  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
    return raw;
  }

  const ddmmyyyy = raw.match(/^(\d{2})[\/\-](\d{2})[\/\-](\d{4})$/);
  if (ddmmyyyy) {
    return `${ddmmyyyy[3]}-${ddmmyyyy[2]}-${ddmmyyyy[1]}`;
  }

  return "";
}

function parseTruthy(value) {
  const normalized = normalize(value);
  return ["yes", "true", "1", "on", "checked"].includes(normalized);
}

function dispatchInputEvents(el) {
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
  el.dispatchEvent(new Event("blur", { bubbles: true }));
}

function highlightElement(el) {
  const originalOutline = el.style.outline;
  const originalTransition = el.style.transition;

  el.style.transition = "outline 120ms ease";
  el.style.outline = "2px solid #22d3ee";

  window.setTimeout(() => {
    el.style.outline = originalOutline;
    el.style.transition = originalTransition;
  }, 700);
}

function normalize(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function cleanText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function escapeCss(value) {
  if (window.CSS && typeof window.CSS.escape === "function") {
    return window.CSS.escape(value);
  }

  return String(value).replace(/([ !"#$%&'()*+,./:;<=>?@[\\\]^`{|}~])/g, "\\$1");
}
