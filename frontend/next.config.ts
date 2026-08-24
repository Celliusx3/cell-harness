import type { NextConfig } from "next";

/**
 * `/api` is proxied to the harness rather than called cross-origin.
 *
 * Same-origin means no CORS middleware on the backend and no preflight on the
 * event stream. It also keeps the browser's URL the only thing that changes
 * between dev and a future single-origin deployment.
 *
 * 4896 must match `--port` in the repo `Makefile`'s `BACKEND_RUN`. The port is
 * deliberately not in `config.json`: this file cannot read Python config, so a
 * setting would look authoritative while the proxy silently kept using the old
 * value. Both copies live next to the command that uses them instead.
 */
const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: "http://127.0.0.1:4896/api/:path*" }];
  },
};

export default nextConfig;
