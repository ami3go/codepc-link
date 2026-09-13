import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

const html = await readFile(new URL("../site/index.html", import.meta.url), "utf8");
const manifest = JSON.parse(
  await readFile(new URL("../site/manifest.webmanifest", import.meta.url), "utf8"),
);
const serviceWorker = await readFile(new URL("../site/sw.js", import.meta.url), "utf8");

test("web app shell contains the core PWA links", () => {
  assert.match(html, /manifest\.webmanifest/);
  assert.match(html, /js\/app\.mjs/);
  assert.match(html, /rfcomm\.html/);
  assert.equal(manifest.name, "CodePC Link");
});

test("service worker caches versioned BLE and RFCOMM shells", () => {
  assert.match(serviceWorker, /CACHE_NAME = "codepc-link-v0\.1-shell-3"/);
  assert.match(serviceWorker, /\.\/js\/bluetooth\.mjs/);
  assert.match(serviceWorker, /\.\/rfcomm\.html/);
  assert.match(serviceWorker, /\.\/js\/rfcomm\.mjs/);
  assert.match(serviceWorker, /SKIP_WAITING/);
});
