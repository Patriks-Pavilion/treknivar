// Sidomeny, header som döljs vid scroll, citatbildspel och trailer i popup
(function () {
  var toggle = document.querySelector('.side-toggle');
  var menu = document.getElementById('side-menu');
  var overlay = document.querySelector('.side-overlay');
  var closeBtn = document.querySelector('.side-close');
  function setMenu(open) {
    menu.classList.toggle('open', open);
    overlay.classList.toggle('open', open);
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    menu.setAttribute('aria-hidden', open ? 'false' : 'true');
  }
  if (toggle && menu) {
    toggle.addEventListener('click', function () { setMenu(!menu.classList.contains('open')); });
    closeBtn.addEventListener('click', function () { setMenu(false); });
    overlay.addEventListener('click', function () { setMenu(false); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') setMenu(false); });
  }

  // Header göms när man scrollar nedåt och visas när man scrollar uppåt
  var header = document.querySelector('.site-header');
  var lastY = window.scrollY;
  window.addEventListener('scroll', function () {
    var y = window.scrollY;
    header.classList.toggle('hide', y > lastY && y > 200);
    lastY = y;
  }, { passive: true });

  // Bildspel (citat)
  document.querySelectorAll('[data-slider]').forEach(function (el) {
    var slides = Array.prototype.filter.call(el.children, function (c) { return c.tagName === 'BLOCKQUOTE' || c.tagName === 'FIGURE'; });
    var dots = el.querySelector('.dots');
    if (!slides.length) return;
    var i = 0, timer;
    function show(n) {
      slides[i].classList.remove('active');
      if (dots) dots.children[i].classList.remove('active');
      i = (n + slides.length) % slides.length;
      slides[i].classList.add('active');
      if (dots) dots.children[i].classList.add('active');
    }
    if (dots) slides.forEach(function (_, n) {
      var b = document.createElement('button');
      b.textContent = ('0' + (n + 1)).slice(-2);
      b.setAttribute('aria-label', 'Visa citat ' + (n + 1));
      b.addEventListener('click', function () { show(n); restart(); });
      dots.appendChild(b);
    });
    slides[0].classList.add('active');
    if (dots) dots.children[0].classList.add('active');
    function restart() { clearInterval(timer); timer = setInterval(function () { show(i + 1); }, 7000); }
    if (slides.length > 1) restart();
  });

  // Trailerknapp: öppna Vimeo/YouTube i en popup
  document.querySelectorAll('.video-button').forEach(function (a) {
    a.addEventListener('click', function (e) {
      var url = a.getAttribute('data-video') || '';
      var src = '';
      var m = url.match(/vimeo\.com\/(\d+)/);
      if (m) src = 'https://player.vimeo.com/video/' + m[1] + '?autoplay=1';
      m = url.match(/(?:youtu\.be\/|v=)([\w-]{6,})/);
      if (m) src = 'https://www.youtube-nocookie.com/embed/' + m[1] + '?autoplay=1';
      if (!src) return;
      e.preventDefault();
      var modal = document.createElement('div');
      modal.className = 'video-modal';
      modal.innerHTML = '<button aria-label="Stäng">×</button><div class="video"><iframe src="' + src + '" allow="autoplay; fullscreen; picture-in-picture" allowfullscreen title="Trailer"></iframe></div>';
      function close() { modal.remove(); document.removeEventListener('keydown', esc); }
      function esc(ev) { if (ev.key === 'Escape') close(); }
      modal.addEventListener('click', function (ev) { if (ev.target === modal || ev.target.tagName === 'BUTTON') close(); });
      document.addEventListener('keydown', esc);
      document.body.appendChild(modal);
    });
  });
})();
