import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

const shellFiles = [
  "site/index.html",
  "site/rfcomm.html",
  "site/styles.css",
  "site/manifest.webmanifest",
  "site/sw.js",
  "site/js/protocol.mjs",
  "site/js/bluetooth.mjs",
  "site/js/app.mjs",
  "site/js/rfcomm.mjs",
  "site/js/rfcomm-app.mjs",
  "assets/codepc-link-icon.svg",
];

test("all offline app-shell files exist in the repository", async () => {
  await Promise.all(shellFiles.map((path) => access(path)));
});

test("service worker caches the BLE and RFCOMM browser client modules", async () => {
  const worker = await readFile("site/sw.js", "utf8");
  for (const asset of [
    "./styles.css",
    "./js/protocol.mjs",
    "./js/bluetooth.mjs",
    "./js/app.mjs",
    "./rfcomm.html",
    "./js/rfcomm.mjs",
    "./js/rfcomm-app.mjs",
  ]) {
    assert.match(worker, new RegExp(asset.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  }
  assert.match(worker, /CACHE_NAME = "codepc-link-v0\.1-shell-3"/);
});

test("the BLE page loads its app module and links the RFCOMM prototype", async () => {
  const html = await readFile("site/index.html", "utf8");
  assert.match(html, /<script type="module" src="js\/app\.mjs"><\/script>/);
  assert.match(html, /<link rel="manifest" href="manifest\.webmanifest">/);
  assert.match(html, /href="rfcomm\.html"/);
});

test("the RFCOMM page loads the Web Serial app module", async () => {
  const html = await readFile("site/rfcomm.html", "utf8");
  assert.match(html, /<script type="module" src="js\/rfcomm-app\.mjs"><\/script>/);
  assert.match(html, /RFCOMM \+ Web Serial feasibility prototype/);
});
