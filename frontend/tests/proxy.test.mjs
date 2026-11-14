import test from "node:test";
import assert from "node:assert/strict";
import { GET,POST } from "../app/api/[...path]/route.ts";

const originalFetch=globalThis.fetch;
const request=(path,init)=>Object.assign(new Request(`https://studio.example/api/${path}`,init),{nextUrl:new URL(`https://studio.example/api/${path}`)});
const params=path=>({params:Promise.resolve({path:path.split("/")})});

test("production proxy forwards only HTTPS artifact redirects without following them",async()=>{
  process.env.APP_PROFILE="production";process.env.BACKEND_URL="private-api:8000";
  try {
    globalThis.fetch=async(url,options)=>{
      assert.equal(url.host,"private-api:8000");assert.equal(options.redirect,"manual");
      assert.equal(options.headers.get("host"),null);
      assert.equal(options.headers.get("authorization"),null);
      return new Response(null,{status:307,headers:{location:"https://art.example/sha256/abc"}});
    };
    const response=await GET(request("v1/content/abc",{headers:{Authorization:"Bearer must-not-forward"}}),params("v1/content/abc"));
    assert.equal(response.status,307);assert.equal(response.headers.get("location"),"https://art.example/sha256/abc");
    globalThis.fetch=async()=>new Response(null,{status:307,headers:{location:"http://private.invalid"}});
    assert.equal((await GET(request("v1/content/abc"),params("v1/content/abc"))).status,502);
  } finally {globalThis.fetch=originalFetch;}
});

test("production proxy rejects admin/demo and oversized bodies before reaching upstream",async()=>{
  process.env.APP_PROFILE="production";
  try {
    globalThis.fetch=async()=>{throw new Error("Upstream must not be reached");};
    for(const path of ["v1/admin/jobs","v1/demo/status"]){
      assert.equal((await GET(request(path),params(path))).status,404);
    }
    assert.equal((await POST(request("v1/receipts",{method:"POST",body:"a".repeat(262145)}),params("v1/receipts"))).status,413);
  } finally {globalThis.fetch=originalFetch;}
});

test("upstream failures return a bounded generic error without leaking provider details",async()=>{
  process.env.APP_PROFILE="production";
  try {
    globalThis.fetch=async()=>{throw new Error("provider-secret-must-not-appear");};
    const response=await GET(request("v1/health"),params("v1/health"));
    assert.equal(response.status,503);assert.equal((await response.text()).includes("provider-secret"),false);
  } finally {globalThis.fetch=originalFetch;}
});
