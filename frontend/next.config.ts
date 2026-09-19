import type { NextConfig } from "next";

const BACKEND_PORT = process.env.BACKEND_PORT ?? "4896";

/** `/api` is proxied to the harness rather than called cross-origin. */
const nextConfig: NextConfig = {
  // Next's rewrite proxy gzips the event stream and holds the whole body until close.
  compress: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `http://127.0.0.1:${BACKEND_PORT}/api/:path*` }];
  },
};

export default nextConfig;
