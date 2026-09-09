export type ThemePreference = "light" | "dark";

// Runs in <head> before paint. Keep independent of React so theme also survives
// slow hydration, storage restrictions and cross-tab changes. Legacy system
// preferences resolve to dark; the OS no longer changes the site's palette.
export const THEME_SCRIPT = `(() => {
  const root = document.documentElement;
  const normalize = value => value === 'light' ? 'light' : 'dark';
  let preference = 'dark';
  try { preference = normalize(localStorage.getItem('anicast-theme')); } catch {}
  function apply() {
    const theme = preference;
    root.dataset.theme = theme;
    root.dataset.themePreference = preference;
    root.style.colorScheme = theme;
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = theme === 'dark' ? '#171311' : '#FFFCF7';
    window.dispatchEvent(new Event('anicast-theme-applied'));
  }
  window.addEventListener('anicast-theme-change', event => {
    preference = normalize(event.detail);
    try { localStorage.setItem('anicast-theme', preference); } catch {}
    apply();
  });
  window.addEventListener('storage', event => {
    if (event.key === 'anicast-theme' || event.key === null) {
      preference = normalize(event.newValue);
      apply();
    }
  });
  apply();
})();`;
