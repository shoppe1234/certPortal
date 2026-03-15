// Theme toggle — persists in localStorage, respects OS preference
(function() {
  var root = document.documentElement;
  var portalName = root.dataset.portal;

  // PAM defaults to dark; others default to light
  var defaultTheme = (portalName === 'pam') ? 'dark' : 'light';

  // Check stored preference, then OS, then portal default
  var stored = localStorage.getItem('certportal-theme');
  var osDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  var theme = stored || (osDark ? 'dark' : defaultTheme);

  root.setAttribute('data-theme', theme);
  updateIcon(theme);

  function updateIcon(t) {
    var icon = document.getElementById('theme-icon');
    if (icon) icon.textContent = t === 'dark' ? '\u263E' : '\u2600';
  }

  window.toggleTheme = function() {
    var current = root.getAttribute('data-theme');
    var next = current === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    localStorage.setItem('certportal-theme', next);
    updateIcon(next);
  };
})();
