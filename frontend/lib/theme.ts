export type ThemePreference = "light" | "dark" | "system";

// Runs in <head> before paint. Keep independent of React so theme also survives
// slow hydration, storage restrictions, cross-tab changes and OS changes.
export const THEME_SCRIPT = `(() => {
  const root = document.documentElement;
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  const normalize = value => value === 'light' || value === 'dark' ? value : 'system';
  let preference = 'system';
  try { preference = normalize(localStorage.getItem('anicast-theme')); } catch {}
  function apply() {
    const theme = preference === 'system' ? (media.matches ? 'dark' : 'light') : preference;
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
  media.addEventListener('change', apply);
  apply();
})();`;
