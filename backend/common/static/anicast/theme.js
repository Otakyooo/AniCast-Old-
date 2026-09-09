/* Explicit light/dark preference shared with the public site. Runs before paint. */
(() => {
  'use strict';
  const root = document.documentElement;
  const normalize = value => value === 'light' ? 'light' : 'dark';
  let theme = 'dark';
  try { theme = normalize(localStorage.getItem('anicast-theme')); } catch {}
  function apply() {
    root.dataset.theme = theme;
    root.style.colorScheme = theme;
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = theme === 'light' ? '#FFFCF7' : '#171311';
    document.querySelectorAll('[data-anicast-theme]').forEach(select => { select.value = theme; });
  }
  apply();
  document.addEventListener('DOMContentLoaded', () => {
    apply();
    document.querySelectorAll('[data-anicast-theme]').forEach(select => {
      select.addEventListener('change', () => {
        theme = normalize(select.value);
        try { localStorage.setItem('anicast-theme', theme); } catch {}
        apply();
      });
    });
  });
  window.addEventListener('storage', event => {
    if (event.key === 'anicast-theme' || event.key === null) {
      theme = normalize(event.newValue);
      apply();
    }
  });
})();
