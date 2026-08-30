---
name: anicast-ui
description: Design, implement, or review AniCast frontend UI and user flows in Next.js/React/CSS Modules while preserving its brand tokens, accessibility, data honesty, and existing architecture. Use for changes under frontend/app or frontend/components and for UI design QA; do not use for backend-only or infrastructure-only work.
---

# AniCast UI

Before making a visual, interaction, navigation, form, or UI-copy decision, read:

- `docs/FRONTEND_DESIGN_RULES.md` for product-specific design and QA rules;
- `docs/BRAND_UI_TECH_SPEC.md` for the canonical assets and color tokens.

Inspect the closest existing route, shared component, CSS module, data boundary,
and localized copy before choosing a pattern. Preserve CSS Modules, App Router,
Phosphor Icons, and the existing i18n system. Do not add Tailwind, shadcn/ui, a
new icon family, a new palette, or another UI dependency unless the user asks for
that architectural change.

## Implementation

- Identify the user's primary task and the affected data/interaction states.
- Reuse the project shell, semantic tokens, shared components, and established API
  behavior.
- Handle applicable loading, empty, unavailable, pending, success, error, and retry
  states. Never show success before backend confirmation.
- Keep native semantics, keyboard behavior, visible focus, responsive reading order,
  and localized copy intact.
- Limit cleanup to code required for a coherent change; report adjacent design debt
  separately.

## Review

Review observable behavior, not only JSX and CSS. Classify findings as:

- blocking: prevents the primary flow, loses data, lies about outcome, or makes the
  flow inaccessible;
- significant: breaks hierarchy, responsiveness, recovery, consistency, or a
  documented design rule;
- polish: improvement with no material effect on task completion.

Run the relevant frontend checks from `docs/FRONTEND_DESIGN_RULES.md`. If a browser,
viewport, keyboard, or screen-reader check was not performed, state that limitation.
