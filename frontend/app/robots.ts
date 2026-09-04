import type { MetadataRoute } from "next";
import { SITE_URL } from "../lib/site";

/**
 * Public media lives under the API prefix.
 *
 * Posters and portraits are served from `/api/v1/media/posters/...` and those
 * exact absolute URLs are published as `og:image` and as JSON-LD `image`. A
 * blanket `Disallow: /api/` therefore told crawlers to ignore every image the
 * site advertises. Per RFC 9309 the longest matching rule wins, so this `Allow`
 * re-opens the media path while the rest of the API stays closed.
 */
const PUBLIC_MEDIA_PATH = "/api/v1/media/";

/**
 * Backlink and keyword crawlers, kept out of the image path only.
 *
 * These are not search engines: nobody reaches AniCast through them, and they do
 * not render pages, so poster bytes are pure cost. Measured over a 56-minute
 * window at the edge, MJ12bot alone was 242 of 691 requests (35%) and this group
 * together was 46%, and every media byte crosses the AmneziaWG tunnel from
 * MainServer. They keep full access to HTML, links and metadata, so the site
 * still shows up in Ahrefs/Semrush reports the owner may rely on; only the
 * artwork is withheld. Search engines are unaffected.
 */
const LINK_ANALYSIS_CRAWLERS = ["MJ12bot", "SemrushBot", "AhrefsBot", "Amazonbot"];

/**
 * Recovery links carry a single-use token in the query string.
 *
 * `X-Robots-Tag: noindex` (next.config.ts) only takes effect after the URL is
 * fetched, and fetching is the harm here: a crawler that follows a reset link
 * from a referrer or a leaked paste spends it before the person opens their
 * mail. Disallow stops the request instead of the indexing.
 */
const TOKEN_PATHS = ["/reset-password", "/verify-email"];

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", PUBLIC_MEDIA_PATH],
        disallow: [
          "/api/",
          "/staff",
          ...TOKEN_PATHS,
        ],
      },
      ...LINK_ANALYSIS_CRAWLERS.map((userAgent) => ({
        userAgent,
        allow: "/",
        disallow: ["/api/", "/staff", ...TOKEN_PATHS],
      })),
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
