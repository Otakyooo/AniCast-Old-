import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
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
