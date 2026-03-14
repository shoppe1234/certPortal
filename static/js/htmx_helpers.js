/**
 * certPortal HTMX helpers
 * Global client-side utilities for HTMX-powered portal interactions.
 */

// ── HTMX global event handlers ──────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", function () {
  // Clock update in nav
  updateNavClock();
  setInterval(updateNavClock, 60_000);

  // Auto-dismiss flash messages after 5 seconds
  document.querySelectorAll(".flash").forEach(function (el) {
    setTimeout(function () {
      el.style.transition = "opacity 400ms ease";
      el.style.opacity = "0";
      setTimeout(function () { el.remove(); }, 400);
    }, 5000);
  });
});

// ── HTMX request lifecycle ───────────────────────────────────────────────────

document.addEventListener("htmx:beforeRequest", function (evt) {
  var btn = evt.detail.elt;
  if (btn && btn.tagName === "BUTTON") {
    // Skip wizard buttons — handled by meredith_wizard.js spinner
    if (btn.closest(".wizard-nav") || btn.closest(".generation-success")) return;
    btn.disabled = true;
    btn.dataset.originalText = btn.textContent;
    btn.textContent = "…";
  }
});

document.addEventListener("htmx:afterRequest", function (evt) {
  var btn = evt.detail.elt;
  if (btn && btn.tagName === "BUTTON" && btn.dataset.originalText) {
    btn.disabled = false;
    btn.textContent = btn.dataset.originalText;
    delete btn.dataset.originalText;
  }
});

document.addEventListener("htmx:responseError", function (evt) {
  // Skip wizard buttons — handled by meredith_wizard.js error toast
  var elt = evt.detail.elt;
  if (elt && (elt.closest(".wizard-nav") || elt.closest(".generation-success"))) return;
  var msg = "Request failed: " + evt.detail.xhr.status;
  try {
    var body = JSON.parse(evt.detail.xhr.responseText);
    if (body.detail) msg = body.detail;
  } catch (e) {}
  showFlash(msg, "error");
});

// ── Utilities ────────────────────────────────────────────────────────────────

function updateNavClock() {
  var el = document.getElementById("nav-clock");
  if (!el) return;
  var now = new Date();
  el.textContent = now.toISOString().replace("T", " ").substring(0, 19) + "Z";
}

function showFlash(message, level) {
  level = level || "info";
  var container = document.querySelector(".flash-container");
  if (!container) {
    container = document.createElement("div");
    container.className = "flash-container";
    document.body.insertBefore(container, document.querySelector(".main-content"));
  }
  var el = document.createElement("div");
  el.className = "flash flash-" + level;
  el.textContent = message;
  container.appendChild(el);
  setTimeout(function () {
    el.style.transition = "opacity 400ms ease";
    el.style.opacity = "0";
    setTimeout(function () { el.remove(); }, 400);
  }, 5000);
}

// Export for inline use
window.certPortal = { showFlash: showFlash };
