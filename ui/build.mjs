// Builds the bundle into the Python package, so an installed core can serve it
// without Node. The Obsidian plugin bundles the same entry point.
import { build } from "esbuild";
import { copyFileSync, mkdirSync } from "node:fs";

const out = "../src/resource_librarian/ui";
mkdirSync(out, { recursive: true });
await build({
  entryPoints: ["src/main.ts"], bundle: true, format: "iife", globalName: "Librarian",
  target: "es2020", outfile: `${out}/app.js`, minify: false, legalComments: "none",
});
copyFileSync("src/style.css", `${out}/app.css`);
copyFileSync("src/index.html", `${out}/index.html`);
console.log("built", out);
