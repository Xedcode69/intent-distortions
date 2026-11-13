import type { NextConfig } from "next";
const config: NextConfig = {
  distDir: process.env.ECHOES_NEXT_DIST_DIR || ".next",
  output: "standalone",
  poweredByHeader:false,
  async headers(){return [{source:"/:path*",headers:[
    {key:"X-Content-Type-Options",value:"nosniff"},
    {key:"X-Frame-Options",value:"DENY"},
    {key:"Referrer-Policy",value:"strict-origin-when-cross-origin"},
    {key:"Permissions-Policy",value:"camera=(), microphone=(), geolocation=()"},
    ...(process.env.APP_PROFILE==="production"?[{key:"Strict-Transport-Security",value:"max-age=31536000"}]:[]),
  ]}];},
};
export default config;
