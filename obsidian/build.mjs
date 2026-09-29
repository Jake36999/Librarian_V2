// Builds the plugin into dist/: main.js, manifest.json and styles.css, the three
// files an Obsidian plugin folder holds. The interface is the same bundle the
// website serves (../ui/src).
import { build } from "esbuild";
import { builtinModules } from "node:module";
import { copyFileSync, mkdirSync } from "node:fs";

mkdirSync("dist", { recursive: true });
await build({
  entryPoints: ["src/main.ts"], bundle: true, format: "cjs", platform: "node", target: "es2020",
  external: ["obsidian", "electron", ...builtinModules, ...builtinModules.map((m) => `node:${m}`)],
  outfile: "dist/main.js", legalComments: "none",
});
copyFileSync("manifest.json", "dist/manifest.json");
copyFileSync("../ui/src/style.css", "dist/styles.css");
console.log("built dist/");
