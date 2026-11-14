import type { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Resolve private service discovery at runtime. No deployment secrets enter the browser bundle.
async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  if (path.some(part => !/^[a-zA-Z0-9_.-]+$/.test(part) || part === "..") ||
      (path.includes("admin") || path.includes("demo"))) {
    return Response.json({ detail: "Not found" }, { status: 404 });
  }
  const backend = process.env.BACKEND_URL || "http://127.0.0.1:8000";
  const origin = backend.includes("://") ? backend : `http://${backend}`;
  const url = new URL(`/api/${path.join("/")}${request.nextUrl.search}`, origin);
  const headers = new Headers();
  for (const name of ["content-type", "origin"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  try {
    let body: Uint8Array | undefined;
    if (request.method !== "GET" && request.method !== "HEAD") {
      const reader = request.body?.getReader();
      const chunks: Uint8Array[] = []; let size = 0;
      if (reader) {
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          size += value.byteLength;
          if (size > 262144) { await reader.cancel(); return new Response(null, { status: 413 }); }
          chunks.push(value);
        }
      }
      body = new Uint8Array(size); let offset = 0;
      for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.length; }
    }
    const upstream = await fetch(url, { method: request.method, headers, body: body as BodyInit | undefined,
      signal: AbortSignal.timeout(30000), cache: "no-store", redirect: "manual" });
    const responseHeaders = new Headers({ "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" });
    for (const name of ["content-type", "retry-after", "content-security-policy", "content-disposition"]) {
      const value = upstream.headers.get(name); if (value) responseHeaders.set(name, value);
    }
    if (upstream.status >= 300 && upstream.status < 400) {
      const location = upstream.headers.get("location");
      if (!location?.startsWith("https://")) return Response.json({ detail: "Invalid upstream redirect" }, { status: 502 });
      responseHeaders.set("location", location);
    }
    return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
  } catch {
    return Response.json({ detail: "Service temporarily unavailable" }, { status: 503 });
  }
}
export { proxy as GET, proxy as POST, proxy as HEAD };
