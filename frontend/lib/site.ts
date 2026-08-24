const rawSiteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "https://anicast.online";

/** Canonical public origin, without a trailing slash. */
export const SITE_URL = rawSiteUrl.replace(/\/+$/, "");

/** Public posters are stored as same-origin paths; metadata needs absolutes. */
export function absoluteUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  return `${SITE_URL}${path.startsWith("/") ? "" : "/"}${path}`;
}

/** Search snippets truncate around 160 chars; hard-cap keeps tags honest. */
export function metaDescription(text: string | null | undefined, fallback: string, max = 300): string {
  const normalized = text?.replace(/\s+/g, " ").trim();
  if (!normalized) return fallback;
  return normalized.length <= max ? normalized : `${normalized.slice(0, max - 1).trimEnd()}…`;
}
