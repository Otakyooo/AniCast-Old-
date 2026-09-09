---
name: anicast-ui
description: Implement or review Anicast Next.js pages, React components, forms, themes and UI flows using the existing brand and accessibility contracts. Use for frontend behavior and visual QA, not backend-only or infrastructure-only work.
---

# Anicast UI

Read [brand tokens/assets](../../../docs/BRAND_UI_TECH_SPEC.md) and
[interface rules](../../../docs/FRONTEND_DESIGN_RULES.md). Inspect the closest route,
shared component, CSS module and `frontend/lib` consumer before choosing a pattern.
Preserve App Router, Server Components by default, CSS Modules, Phosphor Icons
and existing i18n unless the user requests a different architecture.

`frontend/app/theme.css` owns semantic colors; `globals.css` owns the shared frame.
Themes light/dark use `lib/theme.ts` and ThemeSwitcher; default/legacy system
preferences resolve to dark. Read installed Next.js API guidance from
`frontend/node_modules/next/dist/docs/` before changing framework contracts.
Small text on the
warm-white surface uses berry, not amber. Dark media surfaces scope their light
text explicitly. Keep the same mascot/spelling across themes; use the SVG asset
table in the brand document, self-hosted Manrope and Noto Sans JP for Japanese.

Use the existing PageShell and data boundaries. Preserve input after failed
mutations and show success only after backend confirmation. Check applicable
loading/empty/unavailable/retry states and rapid repeated actions. New localized
copy belongs in the established i18n system; PDF mockup values are not fixtures.

HTML uses a fresh proxy nonce, including theme bootstrap and JSON-LD. Do not
introduce an inline script without the request nonce or shared caching of HTML.
Numeric React style attributes remain separately permitted; this does not permit
inline script handlers. Follow the actual CSP source in `frontend/lib/csp.ts`.

For affected flows verify keyboard/focus, mobile/desktop, long translated text,
theme persistence, independence from OS changes and unavailable storage. Use the
frontend [checks](../../../docs/operations/DEPLOYMENT.md#validation). State which
browser, viewport or screen-reader checks were actually performed. Review findings
must describe impact on the user's task; do not turn UI QA into unrelated cleanup.
