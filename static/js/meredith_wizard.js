/**
 * certPortal — Shared Wizard Controller
 * Step navigation, HTMX integration, form validation, auto-save indicator.
 * Used by both Lifecycle Wizard and Layer 2 Wizard.
 *
 * Export: window.certPortal.wizard
 */

(function () {
  "use strict";

  /* ── State ───────────────────────────────────────────────────── */
  var _config = {
    stepCount: 5,
    currentStep: 0,
    sessionId: null,
    saveUrl: null,        // e.g. "/lifecycle-wizard/{id}/save-step"
    contentTarget: "#wizard-content",
  };

  /* ── Public API ──────────────────────────────────────────────── */

  /**
   * initWizard(opts)
   * Call once after DOMContentLoaded on a wizard page.
   * @param {object} opts — { stepCount, currentStep, sessionId, saveUrl }
   */
  function initWizard(opts) {
    _config.stepCount   = opts.stepCount   || _config.stepCount;
    _config.currentStep = opts.currentStep || 0;
    _config.sessionId   = opts.sessionId   || null;
    _config.saveUrl     = opts.saveUrl     || null;
    _config.contentTarget = opts.contentTarget || _config.contentTarget;

    bindKeyboardNav();
    bindSessionNameInput();
    observeAutoSave();
    updateStepIndicator(_config.currentStep);
  }

  /* ── Step indicator update ───────────────────────────────────── */

  function updateStepIndicator(activeStep) {
    var steps = document.querySelectorAll(".wizard-step");
    steps.forEach(function (el) {
      var num = parseInt(el.dataset.step, 10);
      if (isNaN(num)) return;
      var circle = el.querySelector(".wizard-step-circle");
      var label  = el.querySelector(".wizard-step-label");

      el.classList.remove("wizard-step--active", "wizard-step--complete", "wizard-step--pending");

      if (num < activeStep) {
        el.classList.add("wizard-step--complete");
        if (circle) circle.innerHTML = "&#10003;";  // checkmark
      } else if (num === activeStep) {
        el.classList.add("wizard-step--active");
        if (circle) circle.textContent = String(num + 1);
      } else {
        el.classList.add("wizard-step--pending");
        if (circle) circle.textContent = String(num + 1);
      }
    });

    // Update connector lines
    var connectors = document.querySelectorAll(".wizard-step-connector");
    connectors.forEach(function (c, i) {
      if (i < activeStep) {
        c.classList.add("wizard-step-connector--complete");
      } else {
        c.classList.remove("wizard-step-connector--complete");
      }
    });
  }

  /* ── Form validation ─────────────────────────────────────────── */

  /**
   * validateCurrentStep()
   * Checks all required fields in #step-form. Returns true if valid.
   */
  function validateCurrentStep() {
    var form = document.getElementById("step-form");
    if (!form) return true;

    var valid = true;

    // Clear previous errors
    form.querySelectorAll(".field-error").forEach(function (el) {
      el.classList.remove("field-error");
    });
    form.querySelectorAll(".field-error-msg").forEach(function (el) {
      el.remove();
    });

    // Check required inputs
    form.querySelectorAll("input[required], select[required], textarea[required]").forEach(function (inp) {
      if (!inp.value || !inp.value.trim()) {
        inp.classList.add("field-error");
        var msg = document.createElement("div");
        msg.className = "field-error-msg";
        msg.textContent = "This field is required.";
        inp.parentNode.appendChild(msg);
        valid = false;
      }
    });

    // Check radio groups — at least one checked if group has data-required
    form.querySelectorAll("[data-required-group]").forEach(function (container) {
      var groupName = container.dataset.requiredGroup;
      var checked = form.querySelector('input[name="' + groupName + '"]:checked');
      if (!checked) {
        container.classList.add("field-error");
        valid = false;
      }
    });

    // Check checkbox groups — at least one checked
    var txGrid = form.querySelector(".tx-checkbox-grid");
    if (txGrid) {
      var anyChecked = txGrid.querySelector('input[type="checkbox"]:checked');
      if (!anyChecked) {
        showFlash("Please select at least one transaction.", "error");
        valid = false;
      }
    }

    // Check radio selection for mode
    var modeCards = form.querySelector(".mode-cards");
    if (modeCards) {
      var modeChecked = modeCards.querySelector('input[type="radio"]:checked');
      if (!modeChecked) {
        showFlash("Please select a mode.", "error");
        valid = false;
      }
    }

    return valid;
  }

  /* ── Navigation helpers ──────────────────────────────────────── */

  /**
   * navigateNext()
   * Validate current step, then trigger the HTMX next-step button.
   */
  function navigateNext() {
    if (!validateCurrentStep()) return;
    var nextBtn = document.querySelector(
      '.wizard-nav .btn-primary[hx-post*="save-step"]'
    );
    if (nextBtn) {
      // Trigger any pre-submit collectors (segment overrides, business rules)
      if (typeof window.collectSegmentOverrides === "function") {
        window.collectSegmentOverrides();
      }
      if (typeof window.collectBusinessRules === "function") {
        window.collectBusinessRules();
      }
      htmx.trigger(nextBtn, "click");
    }
  }

  /**
   * navigateBack()
   * Trigger the HTMX back button.
   */
  function navigateBack() {
    var backBtn = document.querySelector(
      '.wizard-nav .btn[hx-post*="save-step"][hx-vals*="go_back"]'
    );
    if (!backBtn) {
      // Fallback: look for any back button
      backBtn = document.querySelector('.wizard-nav a.btn[href]');
    }
    if (backBtn) {
      if (backBtn.tagName === "A") {
        window.location.href = backBtn.href;
      } else {
        htmx.trigger(backBtn, "click");
      }
    }
  }

  /* ── Keyboard navigation ─────────────────────────────────────── */

  function bindKeyboardNav() {
    document.addEventListener("keydown", function (e) {
      // Do not intercept when typing in inputs
      var tag = (e.target.tagName || "").toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select") {
        // Enter in an input triggers next only if not in a modal
        if (e.key === "Enter" && !e.target.closest(".state-modal-overlay")) {
          e.preventDefault();
          navigateNext();
        }
        return;
      }

      if (e.key === "Enter") {
        e.preventDefault();
        navigateNext();
      }

      // Escape closes modals
      if (e.key === "Escape") {
        var modal = document.querySelector(".state-modal-overlay.visible, .state-modal-overlay[style*='flex']");
        if (modal) {
          if (typeof window.closeStateModal === "function") {
            window.closeStateModal();
          } else {
            modal.style.display = "none";
            modal.classList.remove("visible");
          }
        }
      }
    });
  }

  /* ── Session name input ──────────────────────────────────────── */

  function bindSessionNameInput() {
    var nameInput = document.querySelector('.wizard-session-bar .wizard-session-name');
    // Session name display is read-only in the bar — handled on landing page input
  }

  /* ── Auto-save indicator ─────────────────────────────────────── */

  function observeAutoSave() {
    // Listen for HTMX save-step requests to show "Saving..." / "Saved"
    document.addEventListener("htmx:beforeRequest", function (evt) {
      var elt = evt.detail.elt;
      if (!elt) return;
      var url = evt.detail.requestConfig && evt.detail.requestConfig.path;
      if (url && url.indexOf("save-step") !== -1) {
        showAutoSave("saving");
      }
    });

    document.addEventListener("htmx:afterRequest", function (evt) {
      var url = evt.detail.requestConfig && evt.detail.requestConfig.path;
      if (url && url.indexOf("save-step") !== -1) {
        if (evt.detail.successful) {
          showAutoSave("saved");
        } else {
          showAutoSave("error");
        }
      }
    });

    // After HTMX swaps new step content, re-read step number from DOM
    document.addEventListener("htmx:afterSwap", function (evt) {
      var panel = document.querySelector(".wizard-step-panel");
      if (panel && panel.id) {
        var match = panel.id.match(/step-(\d+)/);
        if (match) {
          _config.currentStep = parseInt(match[1], 10);
          updateStepIndicator(_config.currentStep);
        }
      }
    });
  }

  function showAutoSave(state) {
    var el = document.querySelector(".wizard-autosave");
    if (!el) {
      el = document.createElement("span");
      el.className = "wizard-autosave";
      var bar = document.querySelector(".wizard-session-bar");
      if (bar) {
        bar.appendChild(el);
      } else {
        return;
      }
    }

    el.classList.remove("wizard-autosave--saving", "wizard-autosave--saved");

    if (state === "saving") {
      el.textContent = "Saving\u2026";
      el.classList.add("wizard-autosave--saving");
    } else if (state === "saved") {
      el.textContent = "Saved";
      el.classList.add("wizard-autosave--saved");
      setTimeout(function () {
        el.style.opacity = "0";
        setTimeout(function () {
          el.textContent = "";
          el.style.opacity = "1";
        }, 300);
      }, 2000);
    } else {
      el.textContent = "Save failed";
      el.style.color = "var(--color-error)";
    }
  }

  /* ── Flash helper (reuse from htmx_helpers if available) ────── */

  function showFlash(message, level) {
    if (window.certPortal && window.certPortal.showFlash) {
      window.certPortal.showFlash(message, level);
    } else {
      alert(message);
    }
  }

  /* ── Export ──────────────────────────────────────────────────── */

  window.certPortal = window.certPortal || {};
  window.certPortal.wizard = {
    init: initWizard,
    validate: validateCurrentStep,
    navigateNext: navigateNext,
    navigateBack: navigateBack,
    updateStepIndicator: updateStepIndicator,
  };
})();
