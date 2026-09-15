import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Bound build-time page workers on the small maintenance builder.
  experimental: { cpus: 1 },
  poweredByHeader: false,
  // Django owns API slash semantics. Next's global slash removal runs before
  // rewrites and loops with Django's APPEND_SLASH when using this proxy.
  // Page canonicalization remains in proxy.ts (its matcher excludes /api/).
  skipTrailingSlashRedirect: true,
  async headers() {
    const noIndex = [{ key: "X-Robots-Tag", value: "noindex, follow" }];
    return [
      { source: "/account", headers: noIndex },
      { source: "/library", headers: noIndex },
      { source: "/history", headers: noIndex },
      { source: "/notes", headers: noIndex },
      { source: "/settings", headers: noIndex },
      { source: "/recommendations", headers: noIndex },
      { source: "/collections", headers: noIndex },
      { source: "/collections/manage/:path*", headers: noIndex },
      { source: "/login", headers: noIndex },
      { source: "/register", headers: noIndex },
      // Recovery pages carry a single-use token in the query string. Beyond
      // having nothing to index, a crawler that followed such a URL would spend
      // the link before the person ever opened it.
      { source: "/forgot-password", headers: noIndex },
      { source: "/reset-password", headers: noIndex },
      { source: "/verify-email", headers: noIndex },
    ];
  },
  images: {
    // Generate a DPR-aware srcset instead of asking the browser to resample
    // one large JPEG into fractional grid dimensions.
    qualities: [92],
    // WebP only, deliberately. Measured on the production VPS (1 vCPU) with a
    // real 6.2 MB poster at quality 92: WebP is 88.6 KB in 1.9 s, AVIF is
    // 122.1 KB in 6.8 s. At this quality setting AVIF is both larger and 3.5x
    // slower to encode, and Next negotiates AVIF first, so listing it would make
    // every cold miss worse for a bigger file. Revisit only with a measurement
    // at a lower AVIF-specific quality on hardware that can afford the encode.
    formats: ["image/webp"],
    // Optimized variants live in .next/cache/images, keyed by source URL and
    // parameters. Poster filenames are content-addressed (a SHA-256 prefix), so
    // a URL never changes meaning and a long TTL cannot serve stale art. The
    // 60-second default re-encoded the same posters all day, and a cold miss
    // costs up to 4 s through the tunnel.
    minimumCacheTTL: 60 * 60 * 24 * 30,
    remotePatterns: [
      { protocol: "https", hostname: "anicast.online", pathname: "/api/v1/media/**" },
    ],
  },
  async rewrites() {
    // One backend address: INTERNAL_API_BASE_URL is the SSR base including
    // /api/v1, API_INTERNAL_URL is the bare host fallback for rewrites.
    // These destinations are serialized into .next/routes-manifest.json at
    // build time, so API_INTERNAL_URL must be a build argument (see
    // frontend/Dockerfile and .github/workflows/publish.yml) -- setting it
    // only in the container environment has no effect. The 127.0.0.1
    // default is for local development only.
    const ssrBase = process.env.INTERNAL_API_BASE_URL?.replace(/\/+$/, "");
    const backend = process.env.API_INTERNAL_URL
      ?? (ssrBase ? ssrBase.replace(/\/api\/v1$/, "") : "http://127.0.0.1:8000");
    return [
      { source: "/api/v1/media/posters/:filename", destination: `${backend}/api/v1/media/posters/:filename` },
      // Strict matching needs both variants: "/api/:path*/" matches only
      // paths with a trailing slash, "/api/:path*" only paths without one.
      // The catch-all captures the segments without a leading or trailing
      // slash, so the literal "/api/" prefix and the trailing "/" written in
      // the destination each add exactly one slash (asserted in
      // lib/rewrite-destination.test.ts against Next's own matcher).
      { source: "/api/:path*/", destination: `${backend}/api/:path*/` },
      { source: "/api/:path*", destination: `${backend}/api/:path*/` },
    ];
  },
};

export default nextConfig;
