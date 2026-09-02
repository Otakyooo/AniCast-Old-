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

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", PUBLIC_MEDIA_PATH],
        disallow: [
          "/api/",
          "/staff",
        ],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
