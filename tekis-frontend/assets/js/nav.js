// TEKIS — Navigation partagée : surbrillance du lien actif + menu mobile
(function () {
  document.addEventListener('DOMContentLoaded', function () {
    var current = location.pathname.split('/').pop() || 'index.html';
    document.querySelectorAll('[data-nav-link]').forEach(function (link) {
      if (link.getAttribute('href') === current) link.classList.add('active');
    });

    var menuBtn = document.querySelector('[data-menu-toggle]');
    var sidebar = document.querySelector('.tk-sidebar');
    if (menuBtn && sidebar) {
      menuBtn.addEventListener('click', function () {
        sidebar.classList.toggle('open');
      });
      document.addEventListener('click', function (e) {
        if (sidebar.classList.contains('open') && !sidebar.contains(e.target) && !menuBtn.contains(e.target)) {
          sidebar.classList.remove('open');
        }
      });
    }
  });
})();
