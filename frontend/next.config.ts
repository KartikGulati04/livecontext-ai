import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  typescript: {
    // Ignore type errors during build so pre-generated WASM type definitions don't block
    ignoreBuildErrors: true,
  },
};

export default nextConfig;
