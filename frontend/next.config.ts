import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "shikimori.one", pathname: "/system/**" },
      { protocol: "https", hostname: "shikimori.io", pathname: "/system/**" },
    ],
  },
  async rewrites() {
    const backend = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
