/**
 * Fermeture locale de la carte promo (dashboard).
 */
(function () {
  const card = document.getElementById('promo-card');
  const key = 'cimentapp_hide_promo';
  if (!card) return;
  try {
    if (localStorage.getItem(key) === '1') {
      card.classList.add('hidden');
      return;
    }
    const btn = card.querySelector('[data-dismiss-promo]');
    if (btn) {
      btn.addEventListener('click', function () {
        card.classList.add('hidden');
        localStorage.setItem(key, '1');
      });
    }
  } catch (e) {
    /* ignore */
  }
})();

/**
 * CSRF token helper for fetch() POST.
 */
(function () {
  function getCookie(name) {
    const value = '; ' + (document.cookie || '');
    const parts = value.split('; ' + name + '=');
    if (parts.length === 2) return parts.pop().split(';').shift();
    return '';
  }
  window.CSRF_TOKEN = getCookie('csrftoken');
})();
