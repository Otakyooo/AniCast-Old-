import type { CatalogItem } from "./api";

/**
 * One representative per franchise for "similar" shelves: sibling seasons of
 * the same story (Naruto + Naruto: Shippuden, both FMA series) otherwise
 * crowd out genuinely similar titles. Items without franchise data pass
 * through untouched, because nothing proves they are duplicates.
 */
export function dedupeByFranchise<T extends CatalogItem>(items: T[]): T[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    const franchiseSlug = item.franchise?.slug;
    if (!franchiseSlug) return true;
    if (seen.has(franchiseSlug)) return false;
    seen.add(franchiseSlug);
    return true;
  });
}
