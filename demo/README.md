# Intent Distortions educational demo

A standalone explanation of the project. Serve this directory over localhost or HTTPS:

```powershell
uv run --locked python scripts/serve_demo.py
```

Open http://127.0.0.1:3001. No production server, database, API key, wallet or network RPC is required. Browser Web Crypto works on localhost and HTTPS.

The walkthrough includes synthetic swap-shaped records, a sample checkpoint calculation, canonical snapshot/Merkle/seed checks, toggleable artwork layers, illustrative auction credits and tamper detection. The sample beacon and block 42 are synthetic; the browser does not perform BLS verification or assert historical blockchain evidence.

`assets/example.json` includes the complete redacted synthetic sample. Its commitments are generated with the same Python algorithms and independently recomputed by `core.mjs`. `node --test demo/core.test.mjs` verifies cross-language agreement and image bytes. Rebuild with `uv run --locked python scripts/build_explainer.py`; package for static hosting with `node scripts/package-demo.mjs`.

The production application is deployed independently using the root `render.yaml`; its credentials never enter this directory or static site.
