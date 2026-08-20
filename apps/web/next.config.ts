import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Permite E2E/Playwright vía 127.0.0.1 en dev (Next bloquea dev resources cross-origin).
  allowedDevOrigins: ["127.0.0.1"],
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${process.env.STATS_API_URL ?? "http://localhost:8000"}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
