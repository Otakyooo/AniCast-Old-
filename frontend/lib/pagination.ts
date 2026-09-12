/**
 * Windowed page numbers for list pagination.
 *
 * Shows the first and last page plus a small radius around the current one,
 * so a 40-page list never renders forty links. Gaps are left to the renderer
 * (an ellipsis between non-adjacent numbers). Matches the catalog behavior;
 * new paginated lists should reuse this instead of growing their own copy.
 */
export function paginationWindow(currentPage: number, pageCount: number, windowRadius = 2): number[] {
  const pages = new Set<number>([1, pageCount]);
  const from = Math.max(1, currentPage - windowRadius);
  const to = Math.min(pageCount, currentPage + windowRadius);
  for (let page = from; page <= to; page += 1) pages.add(page);
  return [...pages].sort((a, b) => a - b);
}
