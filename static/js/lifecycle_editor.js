/**
 * certPortal — Lifecycle State/Transition Editor Controller
 * Add/edit/remove states, manage transitions, maintain hidden JSON,
 * auto-generate ASCII transition diagram, validate state graph.
 *
 * Export: window.certPortal.lifecycleEditor
 */

(function () {
  "use strict";

  /* ── State ───────────────────────────────────────────────────── */
  var _states = {};
  var _editingStateName = null;

  /* ── Public API ──────────────────────────────────────────────── */

  /**
   * init()
   * Call after DOM is ready on the lifecycle wizard states step.
   * Parses existing states from the hidden input.
   */
  function init() {
    var input = document.getElementById("states-json-input");
    if (input) {
      try {
        _states = JSON.parse(input.value || "{}");
      } catch (e) {
        _states = {};
      }
    }
    refreshDiagram();
  }

  /* ── Modal: Add State ────────────────────────────────────────── */

  function showAddStateModal() {
    _editingStateName = null;
    var modal = document.getElementById("state-modal");
    if (!modal) return;

    document.getElementById("state-modal-title").textContent = "Add State";
    document.getElementById("modal-state-name").value = "";
    document.getElementById("modal-state-name").disabled = false;
    document.getElementById("modal-trigger-doc").value = "";
    document.getElementById("modal-trigger-dir").value = "inbound";
    document.getElementById("modal-description").value = "";
    document.getElementById("modal-is-terminal").checked = false;
    document.getElementById("modal-transitions").innerHTML = "";

    openModal(modal);
  }

  /* ── Modal: Edit State ───────────────────────────────────────── */

  function editState(name) {
    _editingStateName = name;
    var st = _states[name] || {};
    var modal = document.getElementById("state-modal");
    if (!modal) return;

    document.getElementById("state-modal-title").textContent = "Edit State: " + name;
    document.getElementById("modal-state-name").value = name;
    document.getElementById("modal-state-name").disabled = true;
    document.getElementById("modal-trigger-doc").value = (st.trigger || {}).document || "";
    document.getElementById("modal-trigger-dir").value = (st.trigger || {}).direction || "inbound";
    document.getElementById("modal-description").value = st.description || "";
    document.getElementById("modal-is-terminal").checked = !!st.is_terminal;

    var transContainer = document.getElementById("modal-transitions");
    transContainer.innerHTML = "";
    (st.valid_transitions || []).forEach(function (tr) {
      addTransitionRow(tr.to, tr.via);
    });

    openModal(modal);
  }

  /* ── Modal: Close ────────────────────────────────────────────── */

  function closeStateModal() {
    var modal = document.getElementById("state-modal");
    if (!modal) return;
    modal.classList.remove("visible");
    // Allow transition to finish before hiding
    setTimeout(function () {
      modal.style.display = "none";
    }, 200);
  }

  function openModal(modal) {
    modal.style.display = "flex";
    // Force reflow then add visible class for CSS transition
    void modal.offsetWidth;
    modal.classList.add("visible");
    // Focus the name input
    var nameInput = document.getElementById("modal-state-name");
    if (nameInput && !nameInput.disabled) {
      nameInput.focus();
    }
  }

  /* ── Modal: Add transition row ───────────────────────────────── */

  function addTransitionRow(toVal, viaVal) {
    var container = document.getElementById("modal-transitions");
    if (!container) return;
    var row = document.createElement("div");
    row.className = "transition-row";
    row.innerHTML =
      '<input type="text" class="form-input transition-to" placeholder="to state" value="' +
      escHtml(toVal || "") + '">' +
      '<input type="text" class="form-input transition-via" placeholder="via document" value="' +
      escHtml(viaVal || "") + '">' +
      '<button type="button" class="btn btn-sm text-error" title="Remove transition">x</button>';
    // Remove button handler
    row.querySelector("button").addEventListener("click", function () {
      row.remove();
    });
    container.appendChild(row);
  }

  /* ── Save state from modal ───────────────────────────────────── */

  function saveStateFromModal() {
    var name = (document.getElementById("modal-state-name").value || "").trim();
    if (!name) {
      alert("State name is required.");
      return;
    }
    // Sanitize: only allow word chars, hyphens, underscores
    if (!/^[\w-]+$/.test(name)) {
      alert("State name must contain only letters, numbers, underscores, or hyphens.");
      return;
    }

    var trigDoc    = (document.getElementById("modal-trigger-doc").value || "").trim();
    var trigDir    = document.getElementById("modal-trigger-dir").value;
    var desc       = (document.getElementById("modal-description").value || "").trim();
    var isTerminal = document.getElementById("modal-is-terminal").checked;

    var transitions = [];
    document.querySelectorAll("#modal-transitions .transition-row").forEach(function (row) {
      var to  = (row.querySelector(".transition-to").value || "").trim();
      var via = (row.querySelector(".transition-via").value || "").trim();
      if (to) transitions.push({ to: to, via: via });
    });

    var stDef = {};
    if (trigDoc) stDef.trigger = { document: trigDoc, direction: trigDir };
    if (desc) stDef.description = desc;
    if (isTerminal) stDef.is_terminal = true;
    if (transitions.length > 0 && !isTerminal) stDef.valid_transitions = transitions;

    // If renaming (editing + name changed), remove old entry
    if (_editingStateName && _editingStateName !== name) {
      delete _states[_editingStateName];
    }
    _states[name] = stDef;

    closeStateModal();
    refreshStateList();
    refreshDiagram();
  }

  /* ── Remove state ────────────────────────────────────────────── */

  function removeState(name) {
    if (!confirm('Remove state "' + name + '"?')) return;
    delete _states[name];
    // Remove transitions that target this state
    Object.keys(_states).forEach(function (k) {
      var s = _states[k];
      if (s.valid_transitions) {
        s.valid_transitions = s.valid_transitions.filter(function (t) {
          return t.to !== name;
        });
      }
    });
    refreshStateList();
    refreshDiagram();
  }

  /* ── Refresh DOM state list ──────────────────────────────────── */

  function refreshStateList() {
    syncHiddenInput();
    var list = document.getElementById("state-list");
    if (!list) return;

    var keys = Object.keys(_states);
    if (keys.length === 0) {
      list.innerHTML =
        '<div class="empty-state" id="no-states-msg">' +
        '<p class="text-muted">No states defined yet. Click "Add State" to begin.</p></div>';
      return;
    }

    var html = "";
    keys.forEach(function (sn) {
      var sd = _states[sn];
      html += '<div class="state-card" data-state-name="' + escHtml(sn) + '">';
      html += '<div class="state-card-header"><div class="state-card-name"><strong>' + escHtml(sn) + "</strong>";
      if (sd.is_terminal) html += ' <span class="gate-pill gate-certified">terminal</span>';
      html += '</div><div class="state-card-actions">';
      html += '<button type="button" class="btn btn-sm" data-edit-state="' + escHtml(sn) + '">Edit</button>';
      html += '<button type="button" class="btn btn-sm text-error" data-remove-state="' + escHtml(sn) + '">Remove</button>';
      html += "</div></div>";
      html += '<div class="state-card-body">';
      if (sd.trigger) {
        html +=
          '<div class="state-detail"><span class="state-detail-label">Trigger:</span><span>' +
          escHtml((sd.trigger.document || "") + " " + (sd.trigger.direction || "")) +
          "</span></div>";
      }
      if (sd.description) {
        html +=
          '<div class="state-detail"><span class="state-detail-label">Description:</span><span class="text-muted">' +
          escHtml(sd.description) + "</span></div>";
      }
      if (sd.valid_transitions && sd.valid_transitions.length) {
        html += '<div class="state-detail"><span class="state-detail-label">Transitions:</span><div class="state-transitions">';
        sd.valid_transitions.forEach(function (tr) {
          html +=
            '<span class="transition-pill">' + escHtml(tr.to || "?") +
            ' <span class="text-muted">via ' + escHtml(tr.via || "?") + "</span></span>";
        });
        html += "</div></div>";
      }
      html += "</div></div>";
    });
    list.innerHTML = html;
  }

  /* ── Event delegation for edit/remove/modal buttons ───────────── */

  document.addEventListener("click", function (e) {
    var editBtn = e.target.closest("[data-edit-state]");
    if (editBtn) {
      editState(editBtn.dataset.editState);
      return;
    }
    var removeBtn = e.target.closest("[data-remove-state]");
    if (removeBtn) {
      removeState(removeBtn.dataset.removeState);
      return;
    }
    // "Add State" button (by ID)
    if (e.target.closest("#add-state-btn")) {
      showAddStateModal();
      return;
    }
    // Close modal buttons
    var closeBtn = e.target.closest("[data-close-modal]");
    if (closeBtn) {
      closeStateModal();
      return;
    }
    // Save state button
    var saveBtn = e.target.closest("[data-save-state]");
    if (saveBtn) {
      saveStateFromModal();
      return;
    }
    // Add transition button
    var addTransBtn = e.target.closest("[data-add-transition]");
    if (addTransBtn) {
      addTransitionRow("", "");
      return;
    }
  });

  /* ── Sync hidden JSON input ──────────────────────────────────── */

  function syncHiddenInput() {
    var input = document.getElementById("states-json-input");
    if (input) {
      input.value = JSON.stringify(_states);
    }
  }

  /* ── ASCII Transition Diagram ────────────────────────────────── */

  /**
   * generateDiagram()
   * Produce a simple ASCII text diagram of states and transitions.
   * Returns the diagram as a string.
   */
  function generateDiagram() {
    var keys = Object.keys(_states);
    if (keys.length === 0) return "(no states defined)";

    var lines = [];

    keys.forEach(function (sn) {
      var sd = _states[sn];
      var label = sn;
      if (sd.is_terminal) label += " [terminal]";
      if (sd.trigger) {
        label += "  (" + (sd.trigger.document || "?") + " " + (sd.trigger.direction || "") + ")";
      }
      lines.push(label);

      if (sd.valid_transitions && sd.valid_transitions.length) {
        sd.valid_transitions.forEach(function (tr, i) {
          var prefix = (i === sd.valid_transitions.length - 1) ? "  \u2514\u2500\u2500 " : "  \u251C\u2500\u2500 ";
          lines.push(prefix + "\u2192 " + (tr.to || "?") + "  via " + (tr.via || "?"));
        });
      }
      lines.push("");  // blank line between states
    });

    return lines.join("\n").replace(/\n+$/, "");
  }

  function refreshDiagram() {
    var container = document.querySelector(".transition-diagram");
    if (!container) {
      // Create diagram container if not in DOM
      var editor = document.getElementById("state-editor");
      if (!editor) return;
      var wrapper = document.createElement("div");
      wrapper.innerHTML =
        '<div class="transition-diagram-title">Transition Diagram</div>' +
        '<pre class="transition-diagram"></pre>';
      editor.appendChild(wrapper);
      container = wrapper.querySelector(".transition-diagram");
    }
    container.textContent = generateDiagram();
  }

  /* ── Validation ──────────────────────────────────────────────── */

  /**
   * validate()
   * Check that:
   * - At least one state exists
   * - At least one terminal state exists
   * - No orphan states (states referenced in transitions that do not exist)
   * Returns { valid: bool, errors: string[] }
   */
  function validate() {
    var errors = [];
    var keys = Object.keys(_states);

    if (keys.length === 0) {
      errors.push("At least one state is required.");
      return { valid: false, errors: errors };
    }

    // Check for terminal state
    var hasTerminal = false;
    keys.forEach(function (k) {
      if (_states[k].is_terminal) hasTerminal = true;
    });
    if (!hasTerminal) {
      errors.push("At least one terminal state is required (a state with no outgoing transitions).");
    }

    // Check for orphan references (transition targets that do not exist as states)
    var allStateNames = new Set(keys);
    keys.forEach(function (k) {
      var transitions = _states[k].valid_transitions || [];
      transitions.forEach(function (tr) {
        if (tr.to && !allStateNames.has(tr.to)) {
          errors.push('State "' + k + '" has transition to "' + tr.to + '" which does not exist.');
        }
      });
    });

    return { valid: errors.length === 0, errors: errors };
  }

  /* ── Utilities ───────────────────────────────────────────────── */

  function escHtml(str) {
    var div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  /* ── Expose functions globally for backward compat with inline onclick ─ */
  window.showAddStateModal = showAddStateModal;
  window.editState = editState;
  window.closeStateModal = closeStateModal;
  window.addTransitionRow = addTransitionRow;
  window.saveStateFromModal = saveStateFromModal;
  window.removeState = removeState;

  /* ── Export ──────────────────────────────────────────────────── */

  window.certPortal = window.certPortal || {};
  window.certPortal.lifecycleEditor = {
    init: init,
    showAddStateModal: showAddStateModal,
    editState: editState,
    removeState: removeState,
    closeStateModal: closeStateModal,
    addTransitionRow: addTransitionRow,
    saveStateFromModal: saveStateFromModal,
    validate: validate,
    generateDiagram: generateDiagram,
    getStates: function () { return _states; },
  };
})();
