/**
 * Route-scoped stylesheet for Japanese titles.
 *
 * The variable Noto Sans JP stylesheet declares 124 `@font-face` rules (one per
 * unicode subset) and weighs ~99 KB. Only `title.module.css` uses that family,
 * and only for elements marked `[lang="ja"]`, so importing it in the root layout
 * put a large blocking stylesheet on every route to serve one selector on one
 * page. Scoping it here keeps the behaviour identical on title pages and removes
 * the cost everywhere else. The browser still downloads only the subsets the
 * rendered glyphs actually need.
 */
import "@fontsource-variable/noto-sans-jp";

export default function TitlesLayout({ children }: { children: React.ReactNode }) {
  return children;
}
