/* Niezależni Studio — strony są generowane przez build.py, tu zostaje tylko odtwarzacz wideo. */
(function () {
  'use strict';

  document.querySelectorAll('[data-year]').forEach(function (node) {
    node.textContent = new Date().getFullYear();
  });

  // Lekki odtwarzacz: YouTube ładuje się dopiero po kliknięciu w miniaturę.
  document.querySelectorAll('button.video[data-video]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var frame = document.createElement('iframe');
      frame.src = 'https://www.youtube-nocookie.com/embed/' + btn.getAttribute('data-video') + '?autoplay=1&rel=0';
      frame.title = btn.getAttribute('aria-label') || 'Wideo';
      frame.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture';
      frame.allowFullscreen = true;
      frame.referrerPolicy = 'strict-origin-when-cross-origin';
      btn.replaceChildren(frame);
      btn.style.cursor = 'default';
      frame.focus();
    }, { once: true });
  });
})();
