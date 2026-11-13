import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { canonical,sha,utf8,hex,merkleRoot,deriveSeed,selectTimestamp } from "./core.mjs";
const example=JSON.parse(await readFile(new URL("./assets/example.json",import.meta.url),"utf8"));

test("independent browser algorithms reproduce Python export commitments",async()=>{
  assert.equal(hex(await sha(utf8(canonical(example.records)))),example.snapshot_hash);
  const root=await merkleRoot(example.records);
  assert.equal(root,example.merkle_root);
  assert.equal(await deriveSeed(example,root),example.master_seed);
  assert.equal(await selectTimestamp(example.epoch,example.randomness,example.sunday_start),example.selected_timestamp);
});
test("changing a public feature invalidates the snapshot and Merkle commitment",async()=>{
  const changed=structuredClone(example.records);changed[0].amount_in_usd="999999";
  assert.notEqual(await merkleRoot(changed),example.merkle_root);
});
test("educational artwork bytes match the exported image commitment",async()=>{
  const bytes=await readFile(new URL("./assets/artwork.png",import.meta.url));
  assert.equal(hex(await sha(bytes)),example.image_hash);
  assert.equal(example.classification,"synthetic_educational_sample");
  assert.equal(example.randomness_verified,false);
});
