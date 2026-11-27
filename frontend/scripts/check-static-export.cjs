const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const exportDir = process.argv[2] || path.join(__dirname, "..", "out");
const pages = ["index.html", "404.html", "landing.html", "dashboard.html"];
const requiredUtilities = [".flex", ".grid", ".hidden", ".sr-only"];

for (const page of pages) {
  const html = fs.readFileSync(path.join(exportDir, page), "utf8");
  const links = html.matchAll(/<(?:link|script)\b[^>]*?\b(?:href|src)="(\/_next\/[^"?#]+)(?:[?#][^"]*)?"/g);
  const assets = new Set(Array.from(links, ([, url]) => url));
  assert.ok(assets.size > 0, `${page} does not reference any Next.js assets`);

  const styles = [];
  for (const url of assets) {
    const assetPath = path.join(exportDir, url);
    assert.ok(fs.existsSync(assetPath) && fs.statSync(assetPath).size > 0, `${page} references a missing or empty asset: ${url}`);
    if (url.endsWith(".css")) styles.push(fs.readFileSync(assetPath, "utf8"));
  }

  for (const utility of requiredUtilities) {
    assert.ok(styles.some((css) => css.includes(`${utility}{`)), `${page} is missing Tailwind's ${utility} rule`);
  }
}

console.log("Static export: linked assets and Tailwind layout utilities are present.");
