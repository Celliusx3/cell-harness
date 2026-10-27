import type { NextConfig } from "next";

const BACKEND_PORT = process.env.BACKEND_PORT ?? "4896";

/** `/api` is proxied to the harness rather than called cross-origin. */
const nextConfig: NextConfig = {
  output: "standalone",
  // Next roots the trace at a lockfile higher up when it finds one, which nests server.js below the standalone folder.
  outputFileTracingRoot: __dirname,
  // Next's rewrite proxy gzips the event stream and holds the whole body until close.
  compress: false,
  experimental: {
    // Next's rewrite proxy cuts a request body off at 10MB; the harness's `files.max_bytes` is the limit.
    middlewareClientMaxBodySize: "1gb",
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `http://127.0.0.1:${BACKEND_PORT}/api/:path*` }];
  },
};

export default nextConfig;
