/**
 * certPortal — Segment Configuration Controller
 * Expand/collapse accordions, qualifier dropdowns, requirement toggles,
 * preset reset, JSON collection, and live YAML preview.
 *
 * Export: window.certPortal.segmentConfig
 */

(function () {
  "use strict";

  /* ── State ───────────────────────────────────────────────────── */
  var _presetSnapshot = {};  // Original preset values per segment/element

  /* ── Public API ──────────────────────────────────────────────── */

  /**
   * init()
   * Call after DOM is ready on the Layer 2 wizard segment step.
   * Snapshots preset values for reset functionality.
   */
  function init() {
    snapshotPresetValues();
    bindAccordions();
    bindRequirementToggles();
    bindResetButtons();
    updateYamlPreview();
  }

  /* ── Accordion expand/collapse ───────────────────────────────── */

  function bindAccordions() {
    // Use event delegation on stable parent for HTMX compatibility
    document.addEventListener("click", function (e) {
      var header = e.target.closest(".seg-accordion-header");
      if (!header) return;

      // Do not toggle if click was on a button or input inside header
      if (e.target.closest("button, input, select")) return;

      var body = header.nextElementSibling;
      if (!body || !body.classList.contains("seg-accordion-body")) return;

      var isHidden = body.classList.contains("hidden");
      body.classList.toggle("hidden");

      // Update arrow via aria-expanded attribute (CSS handles rotation)
      header.setAttribute("aria-expanded", isHidden ? "true" : "false");

      // Fallback: update arrow text if CSS transform not applied
      var arrow = header.querySelector(".seg-arrow");
      if (arrow) {
        arrow.textContent = isHidden ? "\u25BC" : "\u25B6";
      }
    });
  }

  /**
   * expandAll() / collapseAll()
   * Bulk toggle for all segment accordions.
   */
  function expandAll() {
    document.querySelectorAll(".seg-accordion-body.hidden").forEach(function (body) {
      body.classList.remove("hidden");
      var header = body.previousElementSibling;
      if (header) {
        header.setAttribute("aria-expanded", "true");
        var arrow = header.querySelector(".seg-arrow");
        if (arrow) arrow.textContent = "\u25BC";
      }
    });
  }

  function collapseAll() {
    document.querySelectorAll(".seg-accordion-body:not(.hidden)").forEach(function (body) {
      body.classList.add("hidden");
      var header = body.previousElementSibling;
      if (header) {
        header.setAttribute("aria-expanded", "false");
        var arrow = header.querySelector(".seg-arrow");
        if (arrow) arrow.textContent = "\u25B6";
      }
    });
  }

  /* ── Requirement toggles ─────────────────────────────────────── */

  function bindRequirementToggles() {
    document.addEventListener("change", function (e) {
      if (!e.target.classList.contains("elem-required")) return;
      // When toggled, schedule a YAML preview refresh
      debouncePreview();
    });

    document.addEventListener("change", function (e) {
      if (!e.target.classList.contains("elem-qualifier")) return;
      debouncePreview();
    });

    document.addEventListener("input", function (e) {
      if (!e.target.classList.contains("elem-qualifier") && !e.target.classList.contains("elem-note")) return;
      debouncePreview();
    });
  }

  /* ── Preset snapshot & reset ─────────────────────────────────── */

  function snapshotPresetValues() {
    _presetSnapshot = {};
    document.querySelectorAll(".seg-element-row").forEach(function (row) {
      var seg = row.dataset.segment;
      var elem = row.dataset.element;
      if (!seg || !elem) return;

      var key = seg + ":" + elem;
      var qualInput = row.querySelector(".elem-qualifier");
      var reqInput  = row.querySelector(".elem-required");
      var noteInput = row.querySelector(".elem-note");

      _presetSnapshot[key] = {
        qualifier: qualInput ? qualInput.value : "",
        required:  reqInput  ? reqInput.checked : true,
        note:      noteInput ? noteInput.value  : "",
      };
    });
  }

  function bindResetButtons() {
    document.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-reset-segment]");
      if (!btn) return;
      var segId = btn.dataset.resetSegment;
      resetSegment(segId);
    });
  }

  /**
   * resetSegment(segId)
   * Restore all element values in a segment to their preset snapshot.
   */
  function resetSegment(segId) {
    document.querySelectorAll('.seg-element-row[data-segment="' + segId + '"]').forEach(function (row) {
      var elem = row.dataset.element;
      var key = segId + ":" + elem;
      var snap = _presetSnapshot[key];
      if (!snap) return;

      var qualInput = row.querySelector(".elem-qualifier");
      var reqInput  = row.querySelector(".elem-required");
      var noteInput = row.querySelector(".elem-note");

      if (qualInput) qualInput.value = snap.qualifier;
      if (reqInput)  reqInput.checked = snap.required;
      if (noteInput) noteInput.value  = snap.note;
    });
    updateYamlPreview();
  }

  /* ── Collect all segment overrides into JSON ─────────────────── */

  /**
   * collectOverrides()
   * Gathers all segment element values into a JSON object and stores
   * it in the hidden #segment-overrides-json input.
   * Returns the overrides object.
   */
  function collectOverrides() {
    var overrides = {};

    document.querySelectorAll(".seg-element-row").forEach(function (row) {
      var segId  = row.dataset.segment;
      var elemId = row.dataset.element;
      if (!segId || !elemId) return;

      var qualInput = row.querySelector(".elem-qualifier");
      var noteInput = row.querySelector(".elem-note");
      var reqInput  = row.querySelector(".elem-required");

      if (!overrides[segId]) overrides[segId] = { elements: {} };
      var elemData = {};
      if (qualInput && qualInput.value)  elemData.qualifier = qualInput.value;
      if (noteInput && noteInput.value)  elemData.note      = noteInput.value;
      if (reqInput)                       elemData.required  = reqInput.checked;

      if (Object.keys(elemData).length > 0) {
        overrides[segId].elements[elemId] = elemData;
      }
    });

    var hiddenField = document.getElementById("segment-overrides-json");
    if (hiddenField) {
      hiddenField.value = JSON.stringify(overrides);
    }

    return overrides;
  }

  // Expose globally so the inline onclick in the template can call it
  window.collectSegmentOverrides = collectOverrides;

  /* ── Live YAML Preview ───────────────────────────────────────── */

  var _previewTimer = null;

  function debouncePreview() {
    clearTimeout(_previewTimer);
    _previewTimer = setTimeout(updateYamlPreview, 400);
  }

  /**
   * updateYamlPreview()
   * Build a simplified YAML string from current segment config and
   * render it in the .yaml-live-preview pane (if present on page).
   */
  function updateYamlPreview() {
    var pane = document.querySelector(".yaml-live-preview");
    if (!pane) return;

    var overrides = collectOverrides();
    var lines = ["# Layer 2 — Segment Overrides", "segments:"];

    var segIds = Object.keys(overrides);
    if (segIds.length === 0) {
      lines.push("  # (no overrides configured)");
    }

    segIds.forEach(function (seg) {
      lines.push("  " + seg + ":");
      var elements = overrides[seg].elements || {};
      var elemIds = Object.keys(elements);
      if (elemIds.length === 0) return;

      lines.push("    elements:");
      elemIds.forEach(function (el) {
        var d = elements[el];
        lines.push("      " + el + ":");
        if (d.required !== undefined) lines.push("        required: " + d.required);
        if (d.qualifier)              lines.push("        qualifier: \"" + d.qualifier + "\"");
        if (d.note)                   lines.push("        note: \"" + d.note + "\"");
      });
    });

    pane.textContent = lines.join("\n");
  }

  /* ── HTMX pre-request hook: auto-collect before save-step ───── */
  document.addEventListener("htmx:beforeRequest", function (e) {
    var elt = e.detail.elt;
    if (!elt) return;
    var collectType = elt.dataset.collect;
    if (collectType === "segments") {
      collectOverrides();
    } else if (collectType === "rules") {
      collectBusinessRules();
    }
  });

  /**
   * collectBusinessRules()
   * Gathers business rule toggles into a JSON array and stores
   * in the hidden #business-rules-json input.
   */
  function collectBusinessRules() {
    var rules = [];
    document.querySelectorAll(".rule-toggle-row").forEach(function (row) {
      var ruleId = row.dataset.ruleId;
      var enabledToggle = row.querySelector(".rule-enabled");
      if (!ruleId) return;
      var rule = { id: ruleId, enabled: enabledToggle ? enabledToggle.checked : false };
      var paramInputs = row.querySelectorAll(".rule-param");
      paramInputs.forEach(function (inp) {
        rule[inp.name] = inp.value;
      });
      rules.push(rule);
    });
    var hiddenField = document.getElementById("business-rules-json");
    if (hiddenField) {
      hiddenField.value = JSON.stringify(rules);
    }
    return rules;
  }

  // Expose globally for backward compat
  window.collectBusinessRules = collectBusinessRules;

  /* ── Export ──────────────────────────────────────────────────── */

  window.certPortal = window.certPortal || {};
  window.certPortal.segmentConfig = {
    init: init,
    expandAll: expandAll,
    collapseAll: collapseAll,
    collectOverrides: collectOverrides,
    resetSegment: resetSegment,
    updateYamlPreview: updateYamlPreview,
  };
})();
