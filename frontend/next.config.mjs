/** @type {import('next').NextConfig} */
const nextConfig = {
  // Bundle only what the server needs into .next/standalone, for a small Docker image
  output: "standalone",
};

export default nextConfig;
