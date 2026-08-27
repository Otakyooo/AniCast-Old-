import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
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
    ];
  },
  images: {
    // Shikimori originals are small web-sized files: the optimizer would
    // upscale and recompress them (q75), visibly degrading line art.
    unoptimized: true,
    remotePatterns: [
      { protocol: "https", hostname: "shikimori.one", pathname: "/system/**" },
      { protocol: "https", hostname: "shikimori.io", pathname: "/system/**" },
      { protocol: "https", hostname: "cdn.myanimelist.net", pathname: "/images/**" },
    ],
  },
  async rewrites() {
    const backend = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
