import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

const shellFiles = [
  "site/index.html",
  "site/styles.css",
  "site/manifest.webmanifest",
  "site/sw.js",
  "site/js/protocol.mjs",
  "site/js/bluetooth.mjs",
  "site/js/app.mjs",
  "assets/codepc-link-icon.svg",
];

test("all offline app-shell files exist in the repository", async () => {
  await Promise.all(shellFiles.map((path) => access(path)));
});

test("service worker caches the browser client modules and stylesheet", async () => {
  const worker = await readFile("site/sw.js", "utf8");
  for (const asset of ["./styles.css", "./js/protocol.mjs", "./js/bluetooth.mjs", "./js/app.mjs"]) {
    assert.match(worker, new RegExp(asset.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  }
});

test("the page loads the app as an ES module and links the manifest", async () => {
  const html = await readFile("site/index.html", "utf8");
  assert.match(html, /<script type="module" src="js\/app\.mjs"><\/script>/);
  assert.match(html, /<link rel="manifest" href="manifest\.webmanifest">/);
});
