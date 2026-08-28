# Design QA — AniCast home redesign, option 1

## Evidence

- Source visual truth: `/home/lama_admin/.codex/generated_images/01a04801-7caf-7231-995a-0ae2ee487af8/exec-36de501c-d477-41f3-9702-eca9226d5fe4.png`
- Browser-rendered desktop implementation: `/home/lama_admin/anicast/.artifacts/product-design/implementation-2026-08-28/home-desktop-final.png`
- Browser-rendered mobile implementation: `/home/lama_admin/anicast/.artifacts/product-design/implementation-2026-08-28/home-mobile-final.png`
- Viewport: desktop 1440 × 1024 CSS px; mobile 390 × 844 CSS px; deviceScaleFactor 1.
- Source pixels: 1487 × 1058. Desktop implementation pixels: 1440 × 1024. Mobile implementation pixels: 390 × 844.
- Density normalization: source and desktop implementation have the same effective aspect ratio; the source was visually fit to the 1440 × 1024 comparison frame without cropping. No device frame or browser chrome was included.
- State: desktop comparison uses a mocked returning-user API response with real catalog entities so the hero progress and seven-item Continue Watching rail match the source state. Mobile captures the supported guest state.

## Full-view comparison evidence

The source and final implementation were opened together after the final capture. Both use the same three-part composition: slim 64px navigation, cinematic edge-to-edge hero with left-aligned controls and right-weighted art, then a dense poster rail entering the first viewport. The hero-to-rail boundary, horizontal content rhythm, AniCast coral/navy balance, restrained borders, and artwork-first treatment align. Dynamic production data creates a longer Russian title than the mock; the implementation keeps it to two balanced lines on desktop and four readable lines on mobile without collision.

## Focused region comparison evidence

- **Header:** the full Russian navigation fits at 1440px, active state uses a two-pixel coral underline, search remains compact, and the user area stays visually light. Phosphor supplies one consistent icon family.
- **Hero:** generated 1920 × 1080 raster art is sharp, has a dark left focal zone for text, preserves the right-side character focus, and uses layered scrims rather than a rounded container. CTA, library action, metadata, genres, and progress retain the source hierarchy.
- **Rail:** seven 2:3 posters fill the available width, titles remain compact, and the shelf scrolls horizontally at narrower breakpoints.
- **Mobile:** hero is recomposed rather than merely stacked; both actions are reachable, bottom navigation remains fixed, the first content rail begins in the initial viewport, and measured horizontal overflow is false.

## Required fidelity surfaces

- **Fonts and typography:** Inter/system sans stack matches the modern grotesk direction; display weight, compact UI sizes, coral eyebrow tracking, and responsive wrapping preserve hierarchy. No clipped or mid-word desktop wrapping remains.
- **Spacing and layout rhythm:** desktop hero height, rail start, gutters, 8px-class radii, and 18px rail gaps are consistent with the selected mock. Mobile uses 16px gutters and 44px+ action targets.
- **Colors and visual tokens:** implementation uses the existing AniCast tokens (`#0B131C`, `#141E2A`, `#1B2330`, `#F3EDE2`, `#A8B1BD`, `#E04F3E`) and introduces no competing brand accent.
- **Image quality and asset fidelity:** hero is a dedicated WebP raster, not CSS/div art. Posters use real catalog assets with fixed 2:3 geometry and `object-fit: cover`. Brand asset is preserved.
- **Copy and content:** all new fixed copy is bilingual. Real title, genre, episode, progress, and poster data are used. Missing synopsis data remains absent instead of being fabricated.
- **Interaction and accessibility:** global search opens and renders results, the primary CTA navigates to the title route, mobile bottom navigation is visible, browser console and page errors are clean in the controlled test, focus-visible rules remain global, and reduced-motion behavior remains available.

## Findings

No actionable P0, P1, or P2 mismatches remain.

Accepted data-dependent deviations:

- The selected mock shows a concise title and synopsis; production may provide a long title or no synopsis. The responsive title constraint and deliberate omission keep the hierarchy intact without inventing editorial content.
- Guest and returning-user rails use different labels and data, while preserving the same geometry.

## Comparison history

1. **Iteration 1 — blocked:** title wrapped into four desktop lines, hero was too tall, navigation clipped the Community link, and an airing shelf with one result left most of the viewport empty.
   - Fixes: widened/reduced the display type, shortened the desktop hero, compacted navigation, and added a popularity fallback for sparse airing data.
   - Post-fix evidence: `home-desktop-v2.png`.
2. **Iteration 2 — blocked:** title wrapping and hero boundary improved, but the returning-user comparison exposed a five-card rail that ended too early.
   - Fixes: tuned final title width/scale and increased Continue Watching capacity to seven supporting entries.
   - Post-fix evidence: `home-desktop-returning-v4.png`.
3. **Iteration 3 — passed:** final returning-user desktop capture fills the rail, preserves the target composition, and the final mobile capture has no horizontal overflow. Search results, CTA navigation, bottom navigation, and clean console behavior were verified with controlled API responses.

## Follow-up polish

- P3: add editorial synopsis/backdrop fields to the catalog API so every featured title can achieve the richer text-and-art pairing shown in the concept without fallback copy.

final result: passed
