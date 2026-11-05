// Drive the distributed adapter's view lifecycle. The host widgets, Core
// transport and mount callback are test doubles. Real Obsidian has its own gate.
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {createRequire} from "node:module";
import vm from "node:vm";

const require = createRequire(import.meta.url);
let button, disposed = 0, cleared = 0;
class Surface {
  empty() { button = undefined; }
  addClass() {}
  createEl() {}
  createDiv() { return new Surface(); }
}
const host = {
  ItemView: class { contentEl = new Surface(); },
  Plugin: class {}, PluginSettingTab: class {},
  Setting: class {
    addButton(configure) {
      configure({
        setButtonText(label) {
          return {onClick(click) { button = {label, click}; }};
        },
      });
    }
  },
};
let protocol = "1";
const context = vm.createContext({
  module:{exports:{}}, require:id => id === "obsidian" ? host : require(id),
  fetch:async () => ({ok:true,json:async () => ({protocol_version:protocol})}),
  window:{setInterval:() => 1, clearInterval:() => { cleared++; }},
  fakeMount:() => ({dispose:() => { disposed++; }}),
});
const bundle = readFileSync(new URL("../obsidian/dist/main.js", import.meta.url),"utf8");
vm.runInContext(bundle,context);
const {View,Stale} = vm.runInContext("mount = fakeMount; ({View:LibrarianView, Stale:StaleCoreLease})",context);
const attempts = [];
const core = {url:"http://127.0.0.1",token:"fixture"};
let forgotten = 0;
const plugin = {
  ensureCore:async takeover => {
    attempts.push(takeover);
    if (attempts.length === 1) throw new Error("ordinary startup failure");
    if (attempts.length === 2) throw new Stale("stale lease");
    return core;
  },
  forgetCore:() => { forgotten++; }, activeMarkdownPath:() => "",
};
const view = new View({},plugin);
await view.onOpen();
assert.equal(button.label,"Try again");
await button.click();
assert.equal(button.label,"Recover and try again");
await button.click();
assert.equal(forgotten,1);
assert.equal(button.label,"Try again");
protocol = "2";
await button.click();
assert.deepEqual(attempts,[false,false,true,false]);
await view.onClose();
assert.equal(disposed,1);
assert.equal(cleared,1);
console.log("Bundled Obsidian view passed ordinary retry, explicit takeover, protocol recovery and disposal.");
