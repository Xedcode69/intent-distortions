import { cpSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
const root=new URL("../",import.meta.url);
mkdirSync(new URL(".next/standalone/.next/static/",root),{recursive:true});
cpSync(new URL(".next/static/",root),new URL(".next/standalone/.next/static/",root),{recursive:true});
process.env.HOSTNAME=process.env.ECHOES_HOST||"127.0.0.1";
await import(new URL(".next/standalone/server.js",root).href);
