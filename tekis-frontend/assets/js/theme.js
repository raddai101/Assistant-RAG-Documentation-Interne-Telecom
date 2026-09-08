// TEKIS — Bascule thème clair / sombre
// Chargé dans <head> avant le rendu pour éviter le flash de thème (FOUC).
(function () {
  var STORAGE_KEY = 'tekis-theme';
  var root = document.documentElement;

  function getPreferredTheme() {
    var stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'light' || stored === 'dark') return stored;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function syncIcons(theme) {
    document.querySelectorAll('[data-theme-icon]').forEach(function (el) {
      el.textContent = theme === 'dark' ? 'light_mode' : 'dark_mode';
    });
  }

  function applyTheme(theme) {
    root.classList.toggle('dark', theme === 'dark');
    root.setAttribute('data-theme', theme);
    syncIcons(theme);
  }

  // Bascule appelée par les boutons : onclick="toggleTheme()"
  window.toggleTheme = function () {
    var next = root.classList.contains('dark') ? 'light' : 'dark';
    localStorage.setItem(STORAGE_KEY, next);
    applyTheme(next);
  };

  // Applique le thème dès que possible (avant peinture) pour éviter le flash
  applyTheme(getPreferredTheme());

  // Resynchronise les icônes une fois le DOM prêt (boutons pas encore présents plus tôt)
  document.addEventListener('DOMContentLoaded', function () {
    syncIcons(root.classList.contains('dark') ? 'dark' : 'light');
  });
})();
