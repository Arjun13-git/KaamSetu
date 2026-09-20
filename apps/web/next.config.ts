import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    // An intake photo is sent through a Server Action (up to 3.5 MB, before base64).
    serverActions: { bodySizeLimit: "5mb" },
  },
};

export default nextConfig;
