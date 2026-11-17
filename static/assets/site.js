(function () {
  'use strict';

  document.querySelectorAll('[data-year]').forEach(function (node) {
    node.textContent = new Date().getFullYear();
  });

  document.querySelectorAll('.filters').forEach(function (bar) {
    var grid = bar.nextElementSibling;
    var buttons = bar.querySelectorAll('[data-filter]');
    bar.hidden = false;
    buttons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        var type = btn.getAttribute('data-filter');
        buttons.forEach(function (b) { b.setAttribute('aria-pressed', String(b === btn)); });
        grid.querySelectorAll('.card').forEach(function (card) {
          card.hidden = !!type && card.getAttribute('data-type') !== type;
        });
      });
    });
  });

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
