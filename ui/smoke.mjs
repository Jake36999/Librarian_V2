// The interface's smoke check in a real browser, against the demo core
// (tests/ui_demo_core.py). Needs `playwright-core` and a Chromium:
//   node smoke.mjs <url> [chromium-path]
// Every step asserts; any page error fails the run.
import { chromium } from "playwright-core";
import { mkdtempSync, writeFileSync } from "fs";
import { tmpdir } from "os";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const FAKE_MCP = join(dirname(fileURLToPath(import.meta.url)), "..", "tests", "fixtures", "fake_mcp_server.py");
const PYTHON = process.env.LIBRARIAN_SMOKE_PYTHON || (process.platform === "win32" ? "python" : "python3");

const [url, exe = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"] = process.argv.slice(2);
const browser = await chromium.launch({ executablePath: exe });
const page = await browser.newPage({ viewport: { width: 1200, height: 820 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
// A 409 is an expected answer here (no model yet; an overwrite needs confirming),
// which the browser also logs as a failed resource load.
page.on("console", (m) => {
  if (m.type() === "error" && !/status of 409/.test(m.text())) errors.push(m.text());
});
const step = (name) => console.log("✓", name);
const expect = async (cond, what) => { if (!(await cond)) throw new Error(`expected: ${what}`); };

await page.goto(url);
await page.waitForSelector("header nav");

// MF-005: one send at a time, success clears only what was sent, Enter never
// stops a reply, and Stop waits for the Core. The accepted send is faked, so
// the page is reloaded afterwards to return to the Core's real state.
let chatPosts = 0, cancelPosts = 0;
page.on("request", (r) => {
  if (r.method() !== "POST") return;
  if (r.url().endsWith("/api/chat")) chatPosts++;
  if (r.url().endsWith("/api/chat/cancel")) cancelPosts++;
});
{
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  await page.route("**/api/chat", async (route) => {
    await gate;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ started: true }) });
  });
  await page.route("**/api/chat/cancel", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "{}" }));
  // The faked send starts no real turn, so the Core's state is shown as busy
  // too; otherwise the next state refresh would correctly report idle.
  await page.route("**/api/state", async (route) => {
    try {
      const real = await route.fetch();
      await route.fulfill({ response: real, json: { ...(await real.json()), busy: true } });
    } catch { /* the page reloaded while this was in flight */ }
  });
  await page.fill("#lib-msg", "first question");
  await page.press("#lib-msg", "Enter");
  await page.press("#lib-msg", "Enter");                  // still pending: sends nothing
  await page.fill("#lib-msg", "a newer draft");
  release();
  await page.waitForSelector("button.lib-send[aria-label='Stop reply']");
  await expect(chatPosts === 1, "one chat request while one is pending");
  await expect(page.inputValue("#lib-msg").then((v) => v === "a newer draft"),
    "success clears only what was sent, not text typed meanwhile");
  await page.press("#lib-msg", "Enter");
  await page.waitForTimeout(300);
  await expect(cancelPosts === 0, "Enter while a reply runs never stops it");
  await expect(page.inputValue("#lib-msg").then((v) => v === "a newer draft"), "and leaves the draft alone");
  await page.click("button.lib-send");
  await page.waitForSelector("button.lib-send[aria-label='Stopping reply'][disabled]");
  await expect(cancelPosts === 1, "Stop sends one cancel and then waits for the Core");
  await page.unroute("**/api/chat");
  await page.unroute("**/api/chat/cancel");
  await page.unroute("**/api/state");
  await page.reload();
  await page.waitForSelector("header nav");
  chatPosts = 0;
  step("composer: one send at a time; Enter never stops; Stop waits for the outcome");
}

// Obsidian owns a generic `.popover` class and makes it a horizontal flex
// container. The shared UI must namespace its own panels so host CSS cannot
// turn the model picker's vertical sections into squeezed columns.
await page.addStyleTag({ content: ".popover, .grid { display: flex !important; flex-direction: row !important; } .card { display: inline-flex !important; height: 32px !important; white-space: nowrap !important; }" });

// No model yet: sending says so, plainly.
await page.fill("#lib-msg", "hello");
await page.keyboard.press("Enter");
await page.waitForSelector(".lib-notice >> text=Choose a chat model first");
await expect(page.inputValue("#lib-msg").then((v) => v === "hello"), "a refused send keeps the draft (MF-005)");
await expect(chatPosts === 1, "a refused send is one request");
await page.fill("#lib-msg", "");
step("sending without a model says what to do, and keeps the draft");

// Model tile: click order sets tiers; clicking again explains; right-click clears.
await page.click(".lib-toolbar .lib-tb:nth-child(4)");
await page.waitForSelector("#lib-models .lib-model-card");
await expect(page.evaluate(() => {
  const panel = document.querySelector("#lib-models");
  if (!panel || panel.classList.contains("popover") || getComputedStyle(panel).display !== "block") return false;
  const visible = [...panel.children].filter((el) => getComputedStyle(el).display !== "none");
  const tops = visible.map((el) => el.getBoundingClientRect().top);
  const box = panel.getBoundingClientRect();
  const card = panel.querySelector(".lib-model-card");
  const cardBox = card?.getBoundingClientRect();
  return tops.every((top, i) => i === 0 || top >= tops[i - 1])
    && box.left >= 0 && box.right <= window.innerWidth
    && !!card && getComputedStyle(card).display === "block"
    && !!cardBox && cardBox.height >= card.scrollHeight;
}), "host popover CSS cannot turn the model picker into horizontal columns");
// The cards re-render once the choice is saved; a click before the save has
// answered lands on the old card and simply chooses it again. Wait for it.
await Promise.all([
  page.waitForResponse((r) => r.url().endsWith("/api/tiers") && r.request().method() === "POST"),
  page.click("#lib-models section:has-text('Local server') .lib-model-card")]);
// R10: no lead has completed the M0 suite yet, so leading asks for a recorded override.
await page.waitForSelector("#lib-models >> text=has not completed the lead qualification suite");
await Promise.all([
  page.waitForResponse((r) => r.url().endsWith("/api/tiers") && r.status() === 200),
  page.click("#lib-models button:has-text('Use it as lead anyway')")]);
await page.waitForSelector("#lib-models .lib-slot:first-child >> text=scripted-demo");
await page.waitForSelector("#lib-models section:has-text('Local server') .lib-model-card.lib-sel");
await page.waitForSelector("#lib-models .lib-model-card.lib-sel .lib-readiness-chip >> text=lead: experimental");
await page.click("#lib-models section:has-text('Local server') .lib-model-card");
await page.waitForSelector("#lib-models .lib-toast >> text=is tier 1");
await page.click("#lib-models section:has-text('Local server') .lib-model-card", { button: "right" });
await page.waitForSelector("#lib-models .lib-toast >> text=Selection cleared");
await page.waitForSelector("#lib-models section:has-text('Local server') .lib-model-card:not(.lib-sel)");
await page.click("#lib-models section:has-text('Local server') .lib-model-card");
await page.waitForSelector("#lib-models section:has-text('Local server') .lib-model-card.lib-sel");
await page.keyboard.press("Escape");
await page.waitForSelector(".lib-toolbar >> text=scripted-demo");
step("tiers by click order, right-click clears");

// A turn: tool rail, reply with a note link, plan beside it.
await page.fill("#lib-msg", "explore host monitoring");
await page.keyboard.press("Enter");
await page.waitForSelector(".lib-msg >> text=exposes the operating system");
await page.waitForSelector(".lib-working", { state: "detached" });      // the turn is done, not just its text
await expect(page.isVisible(".lib-tool >> text=opened a thread"), "the rail shows the session opening");
await expect(page.isVisible(".lib-pane .lib-plan >> text=Frame"), "the plan shows the phases beside the chat");
step("a turn streams into the rail and the plan");

// Ask mode: a write waits on a card; switching to Auto releases it.
await page.fill("#lib-msg", "make the project");
await page.keyboard.press("Enter");
await page.waitForSelector(".lib-perm:not(.lib-done)");
await page.click(".lib-toolbar .lib-tb:nth-child(3)");
await page.check("input[name=librarian-mode][value=auto]");
await page.waitForSelector(".lib-perm.lib-done >> text=released by the switch to auto");
await page.waitForSelector(".lib-msg >> text=written");
await page.keyboard.press("Escape");
await page.waitForSelector(".lib-toolbar >> text=Auto");
step("a mode switch releases the waiting write");

// A note link opens the note beside the chat, rendered; ⋮ browses the vault.
await page.click(".lib-msg .lib-wl:has-text('osquery')");
await page.waitForSelector(".lib-pane .lib-doc >> text=Exposes the operating system");
await expect(page.isVisible(".lib-pane .lib-doc table.lib-props >> text=repository"), "frontmatter shows as properties");
// Text to speech: mode A under a reply, mode B beside ⋮ while a document is open.
await expect(page.isVisible(".lib-msg-wrap:not(.lib-user) .lib-msg-actions button[aria-label='Read aloud']"), "a reply can be read aloud");
await expect(page.isVisible(".lib-pane .lib-pane-actions button[aria-label='Read this document']"), "the open document can be read aloud");
await expect(page.isVisible(".lib-pane .lib-pane-crumbs >> text=osquery.md"), "the path shows as breadcrumbs");
await page.click(".lib-pane button[aria-label='Documents menu']");
await page.click(".lib-pane-menu .lib-menuitem.lib-up");
await page.click(".lib-pane-menu .lib-menuitem.lib-up");
await page.click(".lib-pane-menu .lib-menuitem.lib-dir:has-text('Projects/')");
await page.click(".lib-pane-menu .lib-menuitem.lib-file:has-text('Host Watch')");
await page.waitForSelector(".lib-pane .lib-doc-title >> text=Host Watch");
step("a [[link]] opens the note beside the chat; ⋮ browses folders and returns to the plan");

// The Desk: opening a note on this pursuit's thread touches it onto the
// desk automatically; pinning keeps one there for good.
await page.click(".lib-pane button[aria-label='Documents menu']");
await page.waitForSelector(".lib-pane-menu >> text=Desk — Host Watch");
await page.waitForSelector(".lib-pane-menu .lib-desk-row:has-text('osquery')");   // the async desk fetch
await expect(page.isVisible(".lib-pane-menu .lib-desk-row:has-text('Host Watch')"), "the pursuit's own note is on its desk too");
await expect(page.isVisible('.lib-pane-menu .lib-menuitem.lib-pin >> text=Pin "Host Watch"'), "the open note can be pinned from here");
await page.click('.lib-pane-menu button[aria-label="Pin osquery"]');
await page.waitForSelector('.lib-pane-menu button[aria-label="Unpin osquery"]');
step("opening a note on a pursuit's thread touches its desk; pinning keeps it there for good");

// The agenda: "This week" scans every note's own checkboxes, seeded (in the
// demo core) on notes that already exist, with no dependence on this walk.
await page.click(".lib-pane-menu .lib-menuitem:has-text('This week')");
await page.waitForSelector(".lib-pane .lib-agenda >> text=osquery");
await expect(page.isVisible(".lib-pane .lib-agenda >> text=check for a new stable release"), "a dated task shows under its bucket");
await expect(page.isVisible(".lib-pane .lib-agenda h4:has-text('No date')"), "an undated task gets its own bucket");
await expect(page.isVisible(".lib-pane .lib-agenda >> text=review the changelog"), "the undated task itself is shown");
step("This week scans every note's checkboxes and buckets them by due date");

await page.click(".lib-pane button[aria-label='Documents menu']");
await page.click(".lib-pane-menu .lib-menuitem:has-text('Plan')");
await page.waitForSelector(".lib-pane .lib-plan >> text=Frame");
await expect(page.evaluate(() => {
  const composer = document.querySelector(".lib-composer").getBoundingClientRect();
  return composer.bottom > window.innerHeight - 4;
}), "the composer sits at the bottom of the window");
step("⋮ returns to the plan; the composer stays docked at the bottom");

// ⋮ → Rename or move: the note moves, the chat's link to it follows; then back.
await page.click(".lib-msg .lib-wl:has-text('osquery')");
await page.waitForSelector('.lib-pane .lib-doc-title >> text="osquery"');
await page.click(".lib-pane button[aria-label='Documents menu']");
await page.click(".lib-pane-menu .lib-menuitem:has-text('Rename or move')");
await page.fill("#lib-mv-name", "osquery host");
await page.click(".lib-pane-menu .lib-move-form button:has-text('Move')");
await page.waitForSelector('.lib-pane .lib-doc-title >> text="osquery host"');
await expect(page.isVisible(".lib-pane .lib-pane-crumbs >> text=osquery host.md"), "the breadcrumbs show the new name");
await expect(page.isVisible(".lib-pane .lib-doc .lib-moved"), "the pane says what moved");
await expect(page.isVisible(".lib-msg .lib-wl:has-text('osquery host')"), "the chat's link followed the rename");
await page.click(".lib-pane button[aria-label='Documents menu']");
await page.click(".lib-pane-menu .lib-menuitem:has-text('Rename or move')");
await page.fill("#lib-mv-name", "osquery");
await page.click(".lib-pane-menu .lib-move-form button:has-text('Move')");
await page.waitForSelector('.lib-pane .lib-doc-title >> text="osquery"');
await page.click(".lib-pane button[aria-label='Documents menu']");
await page.click(".lib-pane-menu .lib-menuitem:has-text('Plan')");
step("⋮ renames a note in place, and links to it follow");

// The composer's paperclip: attach a file (it lands in Inbox/, a plain path
// comes back into the message) or link an existing note (a [[wikilink]]).
await page.click("button[aria-label='Attach']");
await page.waitForSelector("#lib-attach >> text=Attach a file from this computer");
const attachFile = join(mkdtempSync(join(tmpdir(), "librarian-smoke-")), "notes.pdf");
writeFileSync(attachFile, "smoke test attachment");
await page.setInputFiles("input[type=file]", attachFile);
await page.waitForFunction(() => document.querySelector("#lib-msg").value.includes("Inbox/notes.pdf"));
await page.fill("#lib-msg", "");
await page.keyboard.press("Escape");            // setInputFiles skips the menu item that would close it
await page.click("button[aria-label='Attach']");
await page.click("#lib-attach .lib-menuitem:has-text('Projects/')");
await page.click("#lib-attach .lib-menuitem:has-text('Host Watch')");
await page.waitForFunction(() => document.querySelector("#lib-msg").value.includes("[[Host Watch]]"));
await page.fill("#lib-msg", "");
step("the paperclip attaches a file into Inbox/, and links an existing note, both inserted into the message");

// Settings: save a key, then overwriting asks first; the key never shows.
// OpenAI, not the default DeepInfra tab: the demo core profiles a DeepInfra
// model with its own key, so DeepInfra already has one saved here.
await page.click(".lib-tb.lib-icon");
await page.selectOption("#lib-provider", "openai");
await page.fill("#lib-key", "sk-demo-SECRET-9999");
await page.click("dialog.lib-settings button:has-text('Save key')");
await page.waitForSelector("dialog.lib-settings #lib-key[placeholder*='9999']");
await page.fill("#lib-key", "sk-demo-OTHER-1111");
await page.click("dialog.lib-settings button:has-text('Overwrite key')");
await page.waitForSelector("dialog.lib-settings .lib-confirm >> text=Replace the saved OpenAI key?");
await page.click("dialog.lib-settings .lib-confirm button:has-text('Cancel')");
await expect(page.evaluate(() => !document.body.innerHTML.includes("SECRET")), "the key is not in the page");
await page.click("dialog.lib-settings button:has-text('Check usage')");
await page.waitForSelector("dialog.lib-settings .lib-usage a:has-text('View on the provider')");
await expect(page.isVisible("dialog.lib-settings .lib-usage >> text=has no usage endpoint"),
  "no usage endpoint says so plainly, alongside the dashboard link");
await page.click("dialog.lib-settings [role=tab]:has-text('Working context')");
await page.fill("#lib-sys", "A thesis on host monitoring");
await page.click("dialog.lib-settings .lib-seg button:has-text('Short')");
await page.click("dialog.lib-settings .lib-seg button:has-text('Coach')");
await page.click("dialog.lib-settings button:has-text('Save')");
await page.waitForSelector("dialog.lib-settings >> text=Saved.");
await page.click("dialog.lib-settings [role=tab]:has-text('Working context')");
await expect(page.isVisible("dialog.lib-settings .lib-seg button[aria-pressed=true]:has-text('Coach')"),
  "the stance choice is saved and shown pressed on reopening the page");
await page.click("dialog.lib-settings [role=tab]:has-text('Library')");
await page.waitForSelector("dialog.lib-settings .lib-srv");
step("settings: key saved and confirmed, usage falls back to a dashboard link, context and library shown");

// A key row in the capability list opens a box under the list to set that key in place.
await page.click("dialog.lib-settings .lib-srv button.lib-link:has-text('key: Brave Search')");
await page.fill("dialog.lib-settings .lib-key-entry input[type=password]", "brave-test-key-0123");
await page.click("dialog.lib-settings .lib-key-entry button:has-text('Save key')");
await page.waitForSelector("dialog.lib-settings .lib-key-entry >> text=Saved. Web search now uses Brave");
await page.waitForSelector("dialog.lib-settings .lib-srv:has-text('key: Brave Search') >> text=saved in this computer's key store");
step("settings: a key row opens a box to set that key in place");

// Lens packs (roadmap §4 C3): a standard pack is listed, not accepted; Accept
// installs its lenses, and the pack then shows as accepted.
await page.waitForSelector("dialog.lib-settings .lib-lens-packs .lib-srv:has-text('tool-choice')");
await page.click("dialog.lib-settings .lib-lens-packs .lib-srv:has-text('tool-choice') button:has-text('Accept')");
await page.waitForSelector("dialog.lib-settings .lib-lens-packs >> text=tool-choice: 10 lens(es) installed");
await expect(page.isVisible("dialog.lib-settings .lib-lens-packs .lib-srv:has-text('tool-choice') >> text=· accepted ·"),
  "the pack shows as accepted");
await expect(page.isVisible("dialog.lib-settings .lib-lens-packs .lib-srv:has-text('tool-choice') button:has-text('Accept')")
  .then((v) => !v), "and offers no Accept once accepted");
step("lens packs: a standard pack is accepted from Settings → Library, and its lenses installed");

// MCP servers: the curated skill is listed (not installed); browsing the
// registry (a fixed fake page, not the real network) finds a result and
// fills the hand-add form from it without connecting anything; a hand-added
// server (the test fixture, a real stdio subprocess) connects and lists its
// tools; per-tool permission and the enable toggle both reach the API.
await page.click("dialog.lib-settings [role=tab]:has-text('MCP servers')");
await page.waitForSelector("dialog.lib-settings .lib-srv >> text=Semantic Scholar");
await page.click("dialog.lib-settings button:has-text('Search')");
await page.waitForSelector("dialog.lib-settings .lib-browse-results .lib-srv >> text=Weather MCP");
await page.click("dialog.lib-settings .lib-browse-results button:has-text('Fill in below')");
await expect(page.inputValue("dialog.lib-settings input[placeholder='server name']")
  .then((v) => v === "weather-mcp"), "Fill in below carries the registry result's own name in");
await expect(page.inputValue("dialog.lib-settings input[placeholder='command, e.g. npx']")
  .then((v) => v === "npx"), "and its resolved command");
step("MCP servers: browsing the registry finds a result and pre-fills the hand-add form, unconnected");

await page.fill("dialog.lib-settings input[placeholder='server name']", "fake");
await page.fill("dialog.lib-settings input[placeholder='command, e.g. npx']", PYTHON);
await page.fill("dialog.lib-settings input[placeholder='args, space-separated']", FAKE_MCP);
await page.click("dialog.lib-settings button:has-text('Add and accept')");
await page.waitForSelector("dialog.lib-settings .lib-srv-block:has-text('2 tools')");
await page.click("dialog.lib-settings .lib-tool-perms .lib-row2:has-text('fake__echo') button:has-text('Deny')");
await page.waitForSelector("dialog.lib-settings .lib-tool-perms .lib-row2:has-text('fake__echo') button[aria-pressed=true]:has-text('Deny')");
await page.click("dialog.lib-settings .lib-srv-block button:has-text('Disable')");
await page.waitForSelector("dialog.lib-settings .lib-srv-block button:has-text('Enable')");
step("MCP servers: curated skill listed, a hand-added server connects and lists tools, per-tool permission and disable both work");

// Service models (R17, slot 4): chosen with the same model tile, kept with the library.
await page.click("dialog.lib-settings [role=tab]:has-text('Connections')");
await page.waitForSelector("dialog.lib-settings .lib-slot-ocr >> text=Qwen/Qwen3.5-397B-A17B");
await expect(page.isVisible("dialog.lib-settings .lib-slot-ocr >> text=(default)"), "the assigned default is marked");
await expect(page.isVisible("dialog.lib-settings .lib-slot-tts >> text=hexgrad/Kokoro-82M"), "slot 5 (text to speech) holds its default");
await expect(page.isVisible("dialog.lib-settings .lib-slot-tts >> text=cap"), "slot 5 says its spend against its cap");
await expect(page.isVisible("dialog.lib-settings .lib-slot-embeddings >> text=none chosen"), "slot 6 starts empty: nothing is embedded unasked");
await expect(page.isVisible("dialog.lib-settings .lib-slot-embeddings button:has-text('Use a local model')"), "a local embedding model is one click");
await page.click("dialog.lib-settings .lib-slot-ocr button:has-text('Choose…')");
await page.waitForSelector("#lib-models >> text=Choose the OCR model");
await expect(page.locator("#lib-models .lib-readiness-chip").count().then(n => n === 0),
  "service cards never borrow chat-role qualification");
await page.click("#lib-models button:has-text('Show all')");
await page.click("#lib-models .lib-model-card:has-text('openai/gpt-oss-20b')");
await page.waitForSelector("dialog.lib-settings .lib-slot-ocr >> text=openai/gpt-oss-20b");
step("service slot 4: OCR chosen through the model tile and kept with the library");
await page.click("dialog.lib-settings .lib-slot-ocr", { button: "right" });
await page.waitForSelector("dialog.lib-settings .lib-slot-ocr >> text=none chosen");
step("right-click empties a service slot");

// An exact custom host can be selected without adding it to preset provider
// tiles. This is an assignment only; the smoke test makes no provider request.
await page.fill("dialog.lib-settings input[aria-label='New host id']", "smoke-vision");
await page.fill("dialog.lib-settings input[aria-label='New host display name']", "Smoke Vision");
await page.fill("dialog.lib-settings input[aria-label='New host base URL']", "http://127.0.0.1:11998/v1");
await page.click("dialog.lib-settings button:has-text('Add host')");
await page.waitForSelector("dialog.lib-settings .lib-host-card:has-text('Smoke Vision')");
await page.fill("dialog.lib-settings input[aria-label='Model on Smoke Vision']", "custom-vision");
await page.selectOption("dialog.lib-settings select[aria-label='Service slot on Smoke Vision']", "ocr");
await page.click("dialog.lib-settings .lib-host-card:has-text('Smoke Vision') button:has-text('Use for service')");
await page.waitForSelector("dialog.lib-settings .lib-slot-ocr >> text=custom-vision");
await expect(page.isVisible("dialog.lib-settings .lib-slot-ocr >> text=smoke-vision"), "the exact custom host is visible");
await page.click("dialog.lib-settings .lib-slot-ocr", { button: "right" });
await page.waitForSelector("dialog.lib-settings .lib-slot-ocr >> text=none chosen");
step("custom service assignment stays explicit and uses the existing Connections controls");

// Research Pipeline §6.1: project access is a person's switch, off by default.
await page.click("dialog.lib-settings [role=tab]:has-text('Projects')");
await page.waitForSelector("dialog.lib-settings >> text=Enable project access");
await expect(page.isChecked("#lib-projects-on").then((on) => !on), "project access starts off");
await expect(page.isVisible("dialog.lib-settings >> text=No project folders yet."), "no folder is allowed until a person adds one");
step("settings: project access is off by default and folders are a person's to add");

// Editing is a second, per-folder permission: off when a folder is added.
const projectDir = mkdtempSync(join(tmpdir(), "librarian-project-"));
await page.fill("#lib-project-path", projectDir);
await page.click("dialog.lib-settings button:has-text('Add')");
await page.waitForSelector("dialog.lib-settings .lib-project-root");
const editsBox = "dialog.lib-settings .lib-project-root .lib-project-writes input";
await expect(page.isChecked(editsBox).then((on) => !on), "edits start off for a new folder");
await page.click(editsBox);
await page.waitForSelector("dialog.lib-settings >> text=Edits allowed: each one is still asked.");
await expect(page.isChecked(editsBox), "edits allowed for this folder only");
await page.click("dialog.lib-settings button:has-text('Remove this project')");
await page.waitForSelector("dialog.lib-settings >> text=No project folders yet.");
step("settings: edits are a separate per-folder permission, off until a person ticks it");

await page.click("dialog.lib-settings button:has-text('Close')");

// The effort slider: one control, saved with the app, its meaning in the tooltip.
await page.$eval(".lib-toolbar .lib-effort input", (el) => {
  el.value = "8";
  el.dispatchEvent(new Event("input"));
  el.dispatchEvent(new Event("change"));
});
await page.waitForFunction(() => (document.querySelector(".lib-toolbar .lib-effort")?.getAttribute("title") ?? "").startsWith("Effort up to 8 of 10"));
await expect(page.textContent(".lib-toolbar .lib-effort .lib-effort-value").then((t) => t === "8"), "the slider shows its level");
step("effort slider: saved, and its tooltip says what it allows");

// Search and staging.
await page.click(".lib-app nav button:has-text('Search')");
await page.fill(".lib-search input[type=search]", "operating system");
await page.keyboard.press("Enter");
// SM-1: everything, grouped by the intent that answered; result-derived facets; tiles that
// say how much of each source was read; a click opens the note beside it.
await page.waitForSelector(".lib-search .lib-tile >> text=osquery");
// ui/packaged-smoke.mjs waits on this selector; keep the two in step (MF-007).
await expect(page.$(".lib-view.lib-search .lib-results").then(Boolean), "the packaged smoke's search-results selector exists");
await expect(page.isVisible(".lib-search .lib-group h3 >> text=Sources"), "everything is grouped by intent");
await expect(page.isVisible(".lib-search >> text=Ran: orient, pattern, made"), "which intents ran is said");
await expect(page.isVisible(".lib-search .lib-tile .lib-depth >> text=read:"), "a tile shows its read depth");
if (await page.locator(".lib-search .lib-facets .lib-chip").count()) {
  await page.locator(".lib-search .lib-facets .lib-chip").first().click();
  await page.waitForSelector(".lib-search button:has-text('Clear filters (1)')");
  await page.click(".lib-search button:has-text('Clear filters')");
  await page.waitForSelector(".lib-search .lib-tile >> text=osquery");
}
await page.click(".lib-search .lib-tile .lib-wl:has-text('osquery')");
await page.waitForSelector(".lib-pane .lib-doc >> text=Exposes the operating system");
step("search: everything grouped by intent, facets narrow and clear, a tile opens its note");
await page.selectOption(".lib-search select[aria-label='Search in']", "staging");
await page.fill(".lib-search input[type=search]", "rowstream");
await page.keyboard.press("Enter");
await page.waitForSelector(".lib-search .lib-tile >> text=acme - rowstream");
await page.selectOption(".lib-search select[aria-label='Search in']", "library");
step("search: the work too - a staged source found by name");
await page.route("**/api/tool/batch_status", (route) => route.fulfill({
  status: 200, contentType: "application/json", body: JSON.stringify({
    waiting: 0, status: "failed", run: "fixture-batch", detail: "review the changed source",
    items: [{ id: "fixture", status: "processing" }],
  }),
}));
await page.click(".lib-app nav button:has-text('Staging')");
await page.waitForSelector(".lib-batch-banner >> text=Batch processing stopped");
await page.waitForSelector(".lib-batch-banner button:has-text('Resume it')");
await page.unroute("**/api/tool/batch_status");
await page.click(".lib-app nav button:has-text('Chat')");
step("a failed batch stays visible with explicit resume, not a silent success");
await page.click(".lib-app nav button:has-text('Staging')");
await page.click(".lib-staging .lib-item");
await page.waitForSelector(".lib-staging .lib-evidence");
await expect(page.isVisible(".lib-staging >> text=Only the opening of this source has been read"), "the unread state is said");
await page.click(".lib-staging button:has-text('Deep read')");
await page.waitForSelector(".lib-staging >> text=/Read \\d+ of \\d+ parts/");
await expect(page.isVisible(".lib-staging >> text=/Deep read: \\d+ of \\d+ parts read/"), "progress is kept on the item");
step("deep read reads the source and reports progress");

// The lens review view: every grounded claim shown inline - the quote, the
// probe questions, the failure caught, when it applies - not just a link.
// The list item is matched by its own text, not a bare ".item": switching
// kind repaints the list asynchronously, and a bare selector can still hit
// the previous kind's item for one frame.
await page.click(".lib-staging .lib-seg button:has-text('Lenses')");
await page.waitForSelector(".lib-staging .lib-item:has-text('Change-stream first')");
await page.click(".lib-staging .lib-item:has-text('Change-stream first')");
await page.waitForSelector(".lib-staging .lib-detail >> text=Change-stream first");
await expect(page.isVisible(".lib-staging .lib-detail blockquote.lib-lens-quote >> text=write-ahead log"), "the grounding quote is shown");
await expect(page.isVisible(".lib-staging .lib-detail >> text=Ask this of a similar artifact"), "probe questions are shown");
await expect(page.isVisible(".lib-staging .lib-detail blockquote.lib-lens-quote.lib-small"), "a probe's own grounding quote is shown inline");
await expect(page.isVisible(".lib-staging .lib-detail >> text=describing the current state instead of how it got there"), "the failure it catches is shown");
await expect(page.isVisible(".lib-staging .lib-detail >> text=Applies when:"), "when it applies is shown");
await expect(page.isVisible(".lib-staging .lib-detail >> text=Not when:"), "when it does not apply is shown");
await expect(page.isVisible(".lib-staging .lib-detail >> text=Also fits"), "the transfer test's situations are shown");
step("deep read stages a lens, and its review shows every grounded claim inline");

// Edit at acceptance (C3): a person rewords the stance's name before accepting;
// the edited lens is what the store holds (checked when it is adopted below).
await page.click(".lib-staging .lib-detail summary:has-text('Edit before accepting')");
await page.fill("#lens-edit-name", "Change-stream first, as I put it");
await page.click(".lib-staging .lib-detail button:has-text('Accept')");
await page.waitForSelector(".lib-staging .lib-detail >> text=accepted into the lens store");
step("a lens is edited before it is accepted");
await page.click(".lib-staging .lib-seg button:has-text('Sources')");
await page.waitForSelector(".lib-staging .lib-item:has-text('acme - rowstream')");
await page.click(".lib-staging .lib-item:has-text('acme - rowstream')");
await page.waitForSelector(".lib-staging .lib-evidence");

await page.fill("#lib-bl", "A change-data-capture tool that streams row changes from Postgres.");
await page.fill("#lib-solves", "Getting row changes out of Postgres as a stream.");
await page.click(".lib-staging button:has-text('Accept')");
await page.waitForSelector(".lib-staging >> text=Accepted");
step("search finds; staging accepts with the person's Bottom Line");

// The two approvals (Research Pipeline §4.2): approving only queues a source; a person
// begins the batch from the banner; the ingested source comes back to be accepted.
await page.click(".lib-staging .lib-item:has-text('Lovelace')");
await page.waitForSelector(".lib-staging .lib-evidence");
await page.click(".lib-staging button:has-text('Approve for ingestion')");
await page.waitForSelector(".lib-staging >> text=Approved for ingestion: it waits for the batch");
await page.waitForSelector(".lib-staging .lib-batch-banner >> text=1 source approved and awaiting ingestion.");
await page.click(".lib-staging .lib-batch-banner button:has-text('Click here to begin')");
await page.waitForFunction(() => {
  const text = document.querySelector(".lib-staging .lib-batch-banner")?.textContent ?? "";
  return !text.includes("Processing") && !text.includes("awaiting ingestion");
}, null, { timeout: 30000 });
// The demo's clerk does not answer the full read, so the batch ends with that stage
// unfinished: the source is "partial", never "enriched", and its note says so.
await page.selectOption(".lib-staging select[aria-label='Which sources']", "partial");
await page.click(".lib-staging .lib-item:has-text('Lovelace')");
await page.waitForSelector(".lib-staging .lib-detail >> text=/Ingested in batch-.* with gaps: coverage partial/");
await expect(page.isVisible(".lib-staging .lib-detail >> text=/Not examined: .*waiting for the clerk model/"), "what was not examined is shown");
await page.fill("#lib-bl", "A paper on streaming rows out of a write-ahead log.");
await page.fill("#lib-solves", "Reading database changes as a stream.");
await page.click(".lib-staging button:has-text('Accept with partial coverage')");
await page.waitForSelector(".lib-staging >> text=/Accepted into the library and catalogued \\(coverage: partial/");
await page.selectOption(".lib-staging select[aria-label='Which sources']", "staged");
step("approving queues a source; the banner begins the batch; a partly ingested source is accepted with its coverage stated");

// The concept-candidate flow: a term seen across two sources (seeded in the
// demo core) is scanned, staged, and shows its quoted usages and sources -
// then a person's own Definition, never drafted for them, turns it into a
// Concept note.
await page.click(".lib-staging .lib-seg button:has-text('Concepts')");
await page.click(".lib-staging button:has-text('Scan for concepts')");
await page.waitForSelector(".lib-staging .lib-items >> text=staged");
await page.waitForSelector(".lib-staging .lib-item:has-text('host instrumentation')");
await page.click(".lib-staging .lib-item:has-text('host instrumentation')");
await page.waitForSelector(".lib-staging .lib-detail >> text=Seen across 2 sources");
await expect(page.isVisible(".lib-staging .lib-detail blockquote.lib-lens-quote.lib-small"), "a usage's own quoted sentence is shown");
await expect(page.isVisible(".lib-staging .lib-detail >> text=osquery"), "the sources it was seen in are shown");
await expect(page.isVisible(".lib-staging .lib-detail >> text=duckdb"), "the sources it was seen in are shown");
await page.click(".lib-staging .lib-detail button:has-text('Accept')");
await page.waitForSelector(".lib-staging .lib-detail >> text=A Definition, in your own words, is needed to accept a concept.");
await page.fill("#lib-def", "How much of a host's live state you can see and query.");
await page.click(".lib-staging .lib-detail button:has-text('Accept')");
await page.waitForSelector(".lib-staging >> text=accepted as a Concept note");
step("a term seen across sources is scanned, staged, and accepted with a person's own Definition");
await page.click(".lib-staging .lib-seg button:has-text('Sources')");

// Sessions: the thread is listed and can be picked back up - under the library's own
// name (its folder is "Demo Vault"; the library is called "Test Vault").
await page.click(".lib-app nav button:has-text('Chat')");
await expect(page.isVisible(".lib-switch:has-text('Test Vault')"), "the toolbar names the open library");
await page.click("header .lib-ghost:has-text('Sessions')");
await page.waitForSelector("#lib-sessions h4 >> text=Threads in Test Vault");
await page.waitForSelector("#lib-sessions .lib-menuitem >> text=Host Watch");
await page.click("#lib-sessions .lib-menuitem:has-text('Host Watch')");
await page.waitForSelector(".lib-tool >> text=continuing the thread");
step("sessions list and attach");

// Adoption (C3): the ⋮ menu lists this thread's lenses - the edited one under
// its new name, and the accepted pack's - and a person adopts one into the thread.
await page.click(".lib-pane button[aria-label='Documents menu']");
await page.waitForSelector(".lib-pane-menu >> text=Lenses — this thread");
await page.waitForSelector(".lib-pane-menu .lib-lens-name:has-text('Change-stream first, as I put it')");
await expect(page.isVisible(".lib-pane-menu .lib-lens-name:has-text('The Least-Privilege-First Lens')"),
  "the accepted pack's lenses are offered too");
await page.click('.lib-pane-menu button[aria-label="Adopt Change-stream first, as I put it"]');
await page.waitForSelector('.lib-pane-menu button[aria-label="Drop Change-stream first, as I put it"]');
await page.keyboard.press("Escape");
step("a lens is adopted into the thread from the ⋮ menu, under the name it was accepted with");

// Model profiling: an unprofiled model can be profiled (staged like any other
// source); a model already profiled with tool_calling: false can't lead a
// session, but can still be tier 2 or 3.
await page.click(".lib-toolbar .lib-tb:nth-child(4)");
await page.waitForSelector("#lib-models section:has-text('DeepInfra') .lib-model-card");
await expect(page.isVisible("#lib-models .lib-model-card:has-text('acme/no-tools-model') >> text=no tool calling"),
  "a profiled model shows its real specs, not 'unprofiled'");
await Promise.all([
  page.waitForResponse((r) => r.url().endsWith("/api/tiers") && r.status() === 200),
  page.click("#lib-models button:has-text('Clear selection')")]);
await page.waitForSelector("#lib-models .lib-slot:first-child >> text=not chosen");
await page.click("#lib-models .lib-model-card:has-text('acme/no-tools-model')");
await page.waitForSelector("#lib-models .lib-toast >> text=can't lead a session");
await expect(page.locator("#lib-models .lib-slot").first().innerText().then((t) => t.includes("not chosen")),
  "the gated model was not made tier 1");
await page.click("#lib-models section:has-text('DeepInfra') button.lib-profile-link");
await page.waitForSelector("#lib-models .lib-toast >> text=staged for review");
await page.click("#lib-models .lib-model-card:has-text('openai/gpt-oss-20b')");         // unprofiled: still fine as tier 1
await page.click("#lib-models button:has-text('Use it as lead anyway')");       // R10: not M0-qualified
await page.waitForSelector("#lib-models .lib-slot:first-child >> text=openai/gpt-oss-20b");
await page.click("#lib-models .lib-model-card:has-text('acme/no-tools-model')");        // now tier 2, no gate on tier 2/3
await page.waitForSelector("#lib-models .lib-slot:nth-child(2) >> text=acme/no-tools-model");
await page.keyboard.press("Escape");
step("an unprofiled model can be profiled; a profiled non-tool-calling model can't lead, but can be tier 2");

await page.click(".lib-app nav button:has-text('Staging')");
await page.click(".lib-staging .lib-item:has-text('gpt-oss-20b')");
await page.waitForSelector(".lib-staging .lib-evidence");
await page.fill("#lib-bl", "OpenAI's own open-weight 21B-parameter model.");
await page.fill("#lib-solves", "A cheap default for high-volume sub-agent work.");
await page.click(".lib-staging button:has-text('Accept')");
await page.waitForSelector(".lib-staging >> text=Accepted");
await page.click(".lib-app nav button:has-text('Chat')");
await page.click(".lib-toolbar .lib-tb:nth-child(4)");
await page.waitForSelector("#lib-models section:has-text('DeepInfra') .lib-model-card:has-text('openai/gpt-oss-20b') >> text=Tier 3");
await expect(page.isVisible("#lib-models .lib-model-card:has-text('openai/gpt-oss-20b') >> text=131k ctx"),
  "the accepted model now shows its measured specs in the tile");
await page.keyboard.press("Escape");
step("accepting the staged model finishes profiling it; the tile shows the real specs");

// Test Directive A2 (a): a staged revision of an accepted note says so, and Accept merges it.
await page.click(".lib-app nav button:has-text('Staging')");
await page.click(".lib-staging .lib-seg button:has-text('Sources')");
await page.selectOption(".lib-staging select[aria-label='Which sources']", "staged");
await page.waitForSelector(".lib-staging .lib-item:has-text('osquery (whole text read)')");
await page.click(".lib-staging .lib-item:has-text('osquery (whole text read)')");
await page.waitForSelector(".lib-staging .lib-detail >> text=A revision of an accepted note");
await page.fill("#lib-bl", "My in-progress review wording");
await expect(page.evaluate(async () => {
  const token = document.querySelector("meta[name=librarian-token]")?.getAttribute("content") ?? "";
  const r = await fetch("/api/tool/staging_flag", { method: "POST", headers: { "Content-Type": "application/json",
    "X-Librarian-Token": token }, body: JSON.stringify({ arguments: { item_id: "rev-osquery",
      sensitive: true, reason: "A concurrent review marked this item sensitive." } }) });
  const out = await r.json();
  return r.ok && !out.error && !out.refused;
}), "a separate person action changes the staged item after review");
await page.click(".lib-staging .lib-detail button:has-text('Accept')");
await page.waitForSelector(".lib-staging .lib-detail >> text=changed after it was read");
await expect(page.inputValue("#lib-bl").then((v) => v === "My in-progress review wording"),
  "a stale review keeps the person's form edits and does not retry acceptance");
await page.click(".lib-staging .lib-detail button:has-text('Reload item (discards form edits)')");
await page.waitForSelector(".lib-staging .lib-detail >> text=A revision of an accepted note");
await page.click(".lib-staging .lib-detail button:has-text('Accept')");
await page.waitForSelector(".lib-staging >> text=/Merged Claims into Sources\\/repository\\/osquery.md/");
await expect(page.evaluate(async () => {
  const token = document.querySelector("meta[name=librarian-token]")?.getAttribute("content") ?? "";
  const r = await fetch("/api/file?path=Sources/repository/osquery.md", { headers: { "X-Librarian-Token": token } });
  return r.ok && (await r.json()).text.includes("a fleet can query");
}), "the revision's Claims are in the note");
step("a staged revision: stale review refuses without losing form edits; explicit reload and Accept merge it");

// (c) a document-level lens: drawn from the whole text; a probe answered elsewhere in it.
await page.click(".lib-staging .lib-seg button:has-text('Lenses')");
await page.waitForSelector(".lib-staging .lib-item:has-text('Read the whole system by its changes')");
await page.click(".lib-staging .lib-item:has-text('Read the whole system by its changes')");
await page.waitForSelector(".lib-staging .lib-detail >> text=Drawn from the whole text");
await expect(page.isVisible(".lib-staging .lib-detail >> text=differential queries report what changed (part 3)"), "the claims it rests on are listed");
await expect(page.isVisible(".lib-staging .lib-detail >> text=Answered elsewhere in the text"), "a probe answered elsewhere says so");
step("a document-level lens: drawn from the whole text, a probe answered elsewhere in it");

// (b) a staged offering is read in full before it is promoted, and promoted from there.
await page.click(".lib-staging .lib-seg button:has-text('Offerings')");
await page.waitForSelector(".lib-staging .lib-item:has-text('Host Watch Starter') >> text=asked: promote?");
await page.click(".lib-staging .lib-item:has-text('Host Watch Starter')");
await page.waitForSelector(".lib-staging .lib-offering-body >> text=osquery turns host instrumentation into queryable SQL tables.");
await expect(page.isVisible(".lib-staging .lib-detail >> text=The session has asked you to promote this"), "the pending question is named");
await page.click(".lib-staging .lib-detail button:has-text('Promote into the library')");
await page.waitForSelector(".lib-staging .lib-detail >> text=/promoted to Offerings\\/Insights\\/Host Watch Starter.md/");
await expect(page.isVisible(".lib-staging >> text=No offering waits to be promoted."), "the list is empty after promoting");
step("a staged offering: read in full in Staging -> Offerings, then promoted from there");

// (d) the review-due action opens a parked learn session for the review that fell due.
await page.click(".lib-app nav button:has-text('Chat')");
await page.click(".lib-toolbar .lib-tb:has-text('Modes')");
await page.click("#lib-modes .lib-menuitem:has-text('review-due')");
await page.waitForFunction(async () => {
  const token = document.querySelector("meta[name=librarian-token]")?.getAttribute("content") ?? "";
  const r = await fetch("/api/tool/list_sessions", { method: "POST", headers: { "Content-Type": "application/json",
    "X-Librarian-Token": token }, body: JSON.stringify({ arguments: {} }) });
  if (!r.ok) return false;
  const out = await r.json();
  return (out.sessions ?? []).some((s) => s.purpose === "learn" && s.status === "parked");
}, null, { timeout: 20000 });
step("the review-due action opens a parked learn session");

// Taxonomy controls keep the existing review workflow, but never report a
// refused refresh as success or accept a changed proposal without re-review.
await page.keyboard.press("Escape");
await page.route("**/api/tool/model_catalog_status", (route) => route.fulfill({ status: 200,
  contentType: "application/json", body: JSON.stringify({ catalogues: [{ provider: "fixture-provider",
    models: 2, held: 1, needs_attention: ["Incomplete fixture model"] }] }) }));
await page.route("**/api/tool/model_catalog_adopt", (route) => route.fulfill({ status: 200,
  contentType: "application/json", body: JSON.stringify({ provider: "fixture-provider", written: 0,
    already_held: 1, failed: [{ name: "Conflicted fixture model", error: "Earlier writes remain; review before retrying" }] }) }));
await page.click(".lib-tb.lib-icon");
await page.click("dialog.lib-settings [role=tab]:has-text('Library')");
await page.waitForSelector("dialog.lib-settings .lib-model-catalogs >> text=Review incomplete/unfindable Source notes");
await page.click("dialog.lib-settings .lib-model-catalogs button:has-text('Adopt the rest')");
await page.waitForSelector("dialog.lib-settings .lib-model-catalogs >> text=Earlier writes remain; review before retrying");
await page.unroute("**/api/tool/model_catalog_status");
await page.unroute("**/api/tool/model_catalog_adopt");
step("catalogue adoption surfaces incomplete Source notes and retained partial-write failures");
await page.waitForSelector("dialog.lib-settings input[aria-label='Topic name']");
await page.route("**/api/tool/views_refresh", (route) => route.fulfill({ status: 200,
  contentType: "application/json", body: JSON.stringify({ error: "refused", refused: "DOCUMENT_ACTIVE",
    detail: "Active index edit (smoke)." }) }));
await page.click("dialog.lib-settings button:has-text('Rewrite indexes')");
await page.waitForSelector("dialog.lib-settings >> text=Active index edit (smoke).");
await expect(page.isVisible("dialog.lib-settings >> text=Indexes rewritten.").then((v) => !v),
  "structured refusal must not be presented as rewritten indexes");
await page.unroute("**/api/tool/views_refresh");
await page.click("dialog.lib-settings button:has-text('Rewrite indexes')");
await page.waitForSelector("dialog.lib-settings >> text=Indexes rewritten.");
await page.fill("dialog.lib-settings input[aria-label='Topic name']", "Smoke Topics Reviewed");
await expect(page.evaluate(async () => {
  const token = document.querySelector("meta[name=librarian-token]")?.getAttribute("content") ?? "";
  const r = await fetch("/api/tool/staging_flag", { method: "POST", headers: { "Content-Type": "application/json",
    "X-Librarian-Token": token }, body: JSON.stringify({ arguments: { item_id: "topic-smoke-safe",
      sensitive: true, reason: "A concurrent reviewer changed this proposal." } }) });
  const out = await r.json();
  return r.ok && !out.error;
}), "a topic proposal changes after Settings reviewed it");
await page.click("dialog.lib-settings .lib-srv:has(input[aria-label='Topic name']) button:has-text('Accept')");
await page.waitForSelector("dialog.lib-settings >> text=changed after it was read");
await expect(page.inputValue("dialog.lib-settings input[aria-label='Topic name']").then((v) => v === "Smoke Topics Reviewed"),
  "stale topic review keeps the edited name without silently retrying");
await page.click("dialog.lib-settings button:has-text('Reload topics (discards edits)')");
await page.waitForSelector("dialog.lib-settings input[aria-label='Topic name']");
await page.fill("dialog.lib-settings input[aria-label='Topic name']", "Smoke Topics Reviewed");
const topicAcceptance = page.waitForResponse((r) => r.url().endsWith("/api/tool/staging_decide") && r.request().method() === "POST");
await page.click("dialog.lib-settings .lib-srv:has(input[aria-label='Topic name']) button:has-text('Accept')");
const topicOutcome = await (await topicAcceptance).json();
await expect(!topicOutcome.error && topicOutcome.accepted === 1, `topic acceptance: ${JSON.stringify(topicOutcome)}`);
await page.waitForSelector("dialog.lib-settings >> text=Smoke Topics Reviewed (1)");
await expect(page.isVisible("dialog.lib-settings input[aria-label='Topic name']").then((v) => !v),
  "accepted topic leaves the proposal list");
await page.click("dialog.lib-settings button:has-text('Close')");
step("taxonomy: structured refresh refusal stays visible; stale proposal requires explicit reload before accepting");

// Interrupted source acceptance never turns into automatic re-ingestion or a
// blind retry. Only the UI response is mocked; no partial note is published.
const partialSource = { id: "partial-fixture", name: "Partial Source", kind: "source", status: "staged",
  file: "Project/docs/paper.pdf", evidence_text: "The retained source evidence.",
  review: { draft: { status: "ok", bottom_line: "The approved wording." } },
  promotion_progress: { source: { path: "Sources/repository/Partial Source.md" },
    completed_paths: ["Sources/repository/files/paper.pdf", "Sources/repository/Partial Source.md"] } };
let explicitFinishes = 0;
await page.route("**/api/tool/staging_decide", (route) => {
  explicitFinishes += 1;
  return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
    accepted: 1, results: [{ id: partialSource.id, status: "accepted", coverage: "captured",
      originals_retained: [partialSource.file], promotion: { catalogued: true },
      handoff_warning: { status: "not_recorded", error: "SESSION_REQUIRED" } }] }) });
});
await page.route("**/api/tool/staging_list", (route) => route.fulfill({ status: 200,
  contentType: "application/json", body: JSON.stringify({ total: 1, items: [partialSource] }) }));
await page.route("**/api/tool/staging_show", (route) => route.fulfill({ status: 200,
  contentType: "application/json", body: JSON.stringify(partialSource) }));
await page.click(".lib-app nav button:has-text('Staging')");
await page.click(".lib-staging .lib-seg button:has-text('Sources')");
await page.waitForSelector(".lib-staging .lib-item:has-text('Partial Source')");
await page.click(".lib-staging .lib-item:has-text('Partial Source')");
await page.waitForSelector(".lib-staging .lib-detail button:has-text('Finish acceptance')");
await expect(page.isVisible(".lib-staging .lib-detail label >> text=Bottom Line (previously approved; review it)"),
  "retained person-authored text is not misattributed to the clerk");
await expect(page.isVisible(".lib-staging .lib-detail >> text=Original attachments remain in place"),
  "the retained originals and incomplete work are visible");
await expect(page.isVisible(".lib-staging .lib-detail >> text=Rejecting or deferring does not undo"),
  "deferral/rejection does not promise rollback");
await expect(page.locator(".lib-staging .lib-detail button:has-text('Approve')").count().then((n) => n === 0),
  "a partial promotion cannot be re-ingested");
await expect(page.locator(".lib-staging .lib-detail button:has-text('Redraft')").count().then((n) => n === 0),
  "the saved approved content is not silently redrafted");
await expect(explicitFinishes === 0, "opening partial work never accepts it automatically");
await page.click(".lib-staging .lib-detail button:has-text('Finish acceptance')");
await page.waitForSelector(".lib-staging .lib-detail >> text=Session handoff was not recorded");
await expect(explicitFinishes === 1, "only the deliberate finish sends an acceptance");
await expect(page.isVisible(".lib-staging .lib-detail >> text=Attachments were copied; originals remain in place"),
  "finishing retains original attachments and keeps a missing-session warning separate");
await page.unroute("**/api/tool/staging_decide");
await page.unroute("**/api/tool/staging_show");
await page.unroute("**/api/tool/staging_list");
await page.click(".lib-app nav button:has-text('Chat')");
step("interrupted source acceptance shows retained originals, completed paths and an explicit finish action");

// UX-01: an audited thread exposes the Core's per-predicate projection in the
// plan pane.  A review action uses the existing person tool, then the UI
// explicitly refreshes session_status and renders the revised requirement.
const auditedSession = await page.evaluate(async () => {
  const token = document.querySelector("meta[name=librarian-token]")?.getAttribute("content") ?? "";
  const call = async (name, args, session = "") => {
    const response = await fetch(`/api/tool/${name}`, { method: "POST", headers: {
      "Content-Type": "application/json", "X-Librarian-Token": token },
      body: JSON.stringify({ arguments: args, session }) });
    const out = await response.json();
    if (!response.ok || out.error || out.refused) throw new Error(JSON.stringify(out));
    return out;
  };
  const opened = await call("open_session", { purpose: "audited",
    question: "inspect acceptance predicates" });
  const session = String(opened.session?.session ?? "");
  await call("set_requirement", { requirement_id: "R1", text: "The quoted evidence is present.",
    predicates: ["the quote is present"], verifiers: { "the quote is present": {
      verifier: "quote.located", params: { evidence: "E1" } } } }, session);
  const attached = await fetch("/api/chat/attach", { method: "POST", headers: {
    "Content-Type": "application/json", "X-Librarian-Token": token },
    body: JSON.stringify({ session_id: session }) });
  if (!attached.ok) throw new Error(await attached.text());
  return session;
});
await page.reload();
await page.waitForSelector("header nav");
await page.waitForSelector(".lib-predicate-inspector code:has-text('R1.p1')");
await expect(page.isVisible(".lib-predicate-inspector >> text=evidence = E1"),
  "the inspector shows the person-bound subject");
await expect(page.isVisible(".lib-predicate-inspector >> text=Core verification from exact or bounded checks"),
  "the inspector distinguishes verifier authority from person acceptance");
await page.fill(`input[aria-label='Evidence needed for R1']`, "a second independent quote");
const evidenceRequest = page.waitForResponse((r) => r.url().endsWith("/api/tool/request_evidence") &&
  r.request().method() === "POST");
const inspectorRefresh = page.waitForResponse((r) => r.url().endsWith("/api/tool/session_status") &&
  r.request().method() === "POST");
await page.click(".lib-predicate-inspector button:has-text('Request evidence')");
await Promise.all([evidenceRequest, inspectorRefresh]);
await page.waitForSelector(".lib-predicate-inspector code:has-text('R1.p2')");
await expect(page.isVisible(".lib-predicate-inspector >> text=revision 2"),
  "the inspector refreshes after its existing person action");
await expect(page.evaluate(() => document.body.textContent?.includes("Person acceptance is a separate judgment")),
  "the inspector never presents person acceptance as verification");
await expect(Boolean(auditedSession), "the audited smoke thread has an id");
step("audited predicate inspector shows bindings and refreshes after a person review action");

// MF-007: the app's dialog rules stay inside its own dialog. A host's or
// another plugin's dialog keeps the browser's own styling.
await expect(page.evaluate(() => {
  const foreign = document.createElement("dialog");
  foreign.innerHTML = "<div class='page tabs'><button class='ghost'>x</button><input type='text'></div>";
  document.body.append(foreign);
  foreign.show();
  const child = foreign.querySelector("div"), button = foreign.querySelector("button"), input = foreign.querySelector("input");
  const ok = getComputedStyle(child).boxSizing === "content-box"
    && getComputedStyle(child).paddingTop === "0px"
    && getComputedStyle(button).cursor !== "pointer"
    && getComputedStyle(input).width !== getComputedStyle(foreign).width
    && getComputedStyle(foreign).borderRadius !== "12px";
  foreign.remove();
  return ok;
}), "a foreign dialog is not restyled by the Librarian's dialog rules");
await expect(page.evaluate(() => {
  const own = document.querySelector("dialog.lib-dialog.lib-settings");
  return !!own && getComputedStyle(own).borderRadius === "12px";
}), "the Librarian's own settings dialog keeps its styling");
step("dialog styles are rooted in the app's own dialog");

// MF-007 (incoming): every class the app puts in the DOM is namespaced, so a
// host's generic rules cannot match it. A hostile host sheet that hides the
// old generic names changes nothing on screen.
const bare = await page.evaluate(() => {
  const root = document.querySelector(".librarian-root") ?? document.getElementById("librarian-root");
  const found = new Set();
  for (const el of [root, ...root.querySelectorAll("*")]) {
    for (const name of el.classList) {
      if (!name.startsWith("lib-") && !name.startsWith("librarian-")) found.add(name);
    }
  }
  return [...found];
});
await expect(bare.length === 0, `every owned class is namespaced (bare: ${bare.join(" ")})`);
await page.addStyleTag({ content: ".title, .badge, .tabs, .page, .primary, .ghost, .row, .row2, .item, "
  + ".menuitem, .opt, .slot, .send, .composer, .live { display: none !important; }" });
await expect(page.isVisible(".lib-app header .lib-title"), "the header title survives a host .title rule");
await expect(page.isVisible("button.lib-send"), "the send button survives host .send/.primary rules");
step("owned classes are namespaced; host generic rules do not match them");
await page.reload();
await page.waitForSelector(".lib-toolbar .lib-effort input");

// MF-006: a refused change rolls back to what the Core confirmed, and says so.
// Refusals are 409s, which the console-error collector above already expects.
const refuse = (error, status = 409) => (route) => route.fulfill({ status, contentType: "application/json",
  body: JSON.stringify({ error }) });
await page.waitForFunction(() => (document.querySelector(".lib-toolbar .lib-effort")?.getAttribute("title") ?? "").startsWith("Effort up to"));
const confirmedEffort = await page.inputValue(".lib-toolbar .lib-effort input");
await page.route("**/api/effort", refuse("effort store unavailable"));
await page.$eval(".lib-toolbar .lib-effort input", (el, now) => {
  el.value = now === "3" ? "4" : "3";
  el.dispatchEvent(new Event("input"));
  el.dispatchEvent(new Event("change"));
}, confirmedEffort);
await page.waitForSelector(".lib-notice >> text=Effort not changed");
await expect(page.inputValue(".lib-toolbar .lib-effort input").then((v) => v === confirmedEffort),
  "a refused effort change returns the slider to the confirmed level");
await page.unroute("**/api/effort");

await page.route("**/api/mode", refuse("a reply is running", 409));
await page.click(".lib-toolbar .lib-tb:nth-child(3)");
const confirmedMode = await page.$eval("input[name=librarian-mode]:checked", (el) => el.value);
const otherMode = await page.$eval("input[name=librarian-mode]:not(:checked)", (el) => el.value);
await page.click(`input[name=librarian-mode][value=${otherMode}]`);
await page.waitForSelector(".lib-notice >> text=Mode not changed");
await expect(page.$eval("input[name=librarian-mode]:checked", (el) => el.value).then((v) => v === confirmedMode),
  "a refused mode change leaves the confirmed mode selected");
await page.keyboard.press("Escape");
await page.unroute("**/api/mode");

await page.route("**/api/libraries", (route) => route.fulfill({ status: 200, contentType: "application/json",
  body: JSON.stringify({ libraries: [
    { path: "C:/smoke/current", name: "Current", last_opened: "2026-11-04T10:00:00", current: true, missing: false },
    { path: "C:/smoke/other", name: "Other", last_opened: "2026-11-03T10:00:00", current: false, missing: false }] }) }));
await page.route("**/api/libraries/forget", refuse("the library list is read-only"));
await page.click("button.lib-switch");
await page.click("#lib-libraries button[aria-label='Forget Other']");
await page.waitForSelector("#lib-libraries >> text=Other was not forgotten");
await expect(page.isEnabled("#lib-libraries button[aria-label='Forget Other']"), "a refused Forget keeps its row usable");
await page.keyboard.press("Escape");
await page.unroute("**/api/libraries");
await page.unroute("**/api/libraries/forget");

let resolvePosts = 0;
await page.route(/\/api\/checkpoints\?pending=1/, (route) => route.fulfill({ status: 200, contentType: "application/json",
  body: JSON.stringify({ checkpoints: [{ id: "cp-smoke", type: "write_conflict", scope: "Notes/A.md",
    choices: ["retry_after_review", "cancel"], default: "cancel", evidence: {} }] }) }));
let releaseResolve;
await page.route("**/api/checkpoints/resolve", async (route) => {
  resolvePosts += 1;
  await new Promise((done) => { releaseResolve = done; });
  await refuse("the decision log is busy")(route);
});
await page.click("button[title='Decisions waiting for you']");
await page.click("#lib-checkpoints .lib-checkpoint button >> text=cancel");
await expect(page.isDisabled("#lib-checkpoints .lib-checkpoint button >> text=Mark reviewed; retry manually"),
  "a decision's choices are disabled while it is being recorded");
releaseResolve();
await page.waitForSelector(".lib-notice >> text=Decision not recorded");
await expect(page.isEnabled("#lib-checkpoints .lib-checkpoint button >> text=cancel"), "a refused decision can be made again");
await expect(resolvePosts === 1, "one press records one decision");
await page.keyboard.press("Escape");
await page.unroute(/\/api\/checkpoints\?pending=1/);
await page.unroute("**/api/checkpoints/resolve");

let releaseCancel;
await page.route("**/api/state", async (route) => {
  try {
    const response = await route.fetch();
    const body = await response.json();
    body.actions = [{ id: "run-smoke", name: "smoke-flow", status: "running", steps: 2 }];
    await route.fulfill({ response, json: body });
  } catch { /* the page moved on */ }
});
await page.route("**/api/actions/run-smoke/cancel", async (route) => {
  await new Promise((done) => { releaseCancel = done; });
  await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ cancelled: true }) });
});
await page.reload();
await page.click("button[aria-label='Cancel smoke-flow']");
await page.waitForSelector("button[aria-label='Cancelling smoke-flow'][disabled]");
releaseCancel();
await expect(page.isVisible("button[aria-label='Cancelling smoke-flow']"),
  "an accepted cancel stays pending until the Core reports the run stopped");
await page.unroute("**/api/state");
await page.unroute("**/api/actions/run-smoke/cancel");
await page.reload();
await page.waitForSelector(".lib-toolbar .lib-effort input");
step("refused changes roll back to the confirmed state; pending cancels and decisions say so");

// MF-008: the layout follows the Librarian's own root, not the window, so a
// narrow Obsidian split in a wide window gets the narrow layout. A draft
// survives every resize.
await page.setViewportSize({ width: 1440, height: 900 });
const draft = "a draft that must survive resizing";
await page.fill("#lib-msg", draft);
const atRootWidth = async (width) => page.evaluate((w) => {
  const root = document.getElementById("librarian-root");
  root.style.width = w ? `${w}px` : "";
  const shown = (sel) => { const el = root.querySelector(sel); return !!el && getComputedStyle(el).display !== "none"; };
  return { crumb: shown("header .lib-crumb"), title: shown("header .lib-title"),
           overflow: root.scrollWidth > root.clientWidth + 1 };
}, width);
const at1100 = await atRootWidth(1100);
await expect(at1100.crumb && at1100.title && !at1100.overflow, `1100px root keeps the full header ${JSON.stringify(at1100)}`);
const at760 = await atRootWidth(760);
await expect(!at760.crumb && at760.title && !at760.overflow, `760px root in a 1440px window is compact ${JSON.stringify(at760)}`);
const at420 = await atRootWidth(420);
await expect(!at420.crumb && !at420.title && !at420.overflow, `420px root is narrow ${JSON.stringify(at420)}`);
const at320 = await atRootWidth(320);
await expect(!at320.overflow, `320px root does not overflow sideways ${JSON.stringify(at320)}`);
await atRootWidth(420);
await page.click(".lib-app nav button:has-text('Search')");
const searchWidth = await page.$eval(".lib-search input[type=search]", (el) => el.getBoundingClientRect().width);
await expect(searchWidth >= 280, `the Search input keeps at least 280px in a 420px root (${searchWidth}px)`);
await page.click(".lib-app nav button:has-text('Chat')");
await expect(page.inputValue("#lib-msg").then((v) => v === draft), "the draft survives resizing and switching views");
await atRootWidth(0);
await page.fill("#lib-msg", "");
step("the layout follows the root's width, not the window's; drafts survive");

// MF-008: a saved split wider than the root's room is clamped (pane >= 300px,
// chat >= 360px) without overwriting the person's saved preference.
await page.evaluate(() => {
  localStorage.setItem("librarian:pane-w", "1200px");
  localStorage.setItem("librarian:pane", "open");
});
await page.reload();
await page.waitForSelector(".lib-pane");
const splitAt = async (width) => page.evaluate(async (w) => {
  const root = document.getElementById("librarian-root");
  root.style.width = w ? `${w}px` : "";
  await new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)));
  const main = root.querySelector(".lib-main").getBoundingClientRect().width;
  const pane = root.querySelector(".lib-pane").getBoundingClientRect().width;
  return { main, pane, saved: localStorage.getItem("librarian:pane-w") };
}, width);
const split1100 = await splitAt(1100);
await expect(split1100.main >= 360 && split1100.pane >= 300 && split1100.saved === "1200px",
  `a 1200px saved split in an 1100px root keeps the chat usable ${JSON.stringify(split1100)}`);
const split1000 = await splitAt(1000);
await expect(split1000.main >= 360 && split1000.pane >= 300,
  `and in a 1000px root ${JSON.stringify(split1000)}`);
await splitAt(0);
await page.evaluate(() => localStorage.removeItem("librarian:pane-w"));
step("a saved split is clamped to the root's room and the preference is kept");

// MF-008: an overlay focuses its first control once its content arrives, and
// Escape closes it, is consumed, and hands focus back to its trigger. With
// nothing open, Escape passes by untouched.
await page.evaluate(() => {
  window.__lastEscape = null;
  window.addEventListener("keydown", (e) => { if (e.key === "Escape") window.__lastEscape = e; }, true);
});
await page.click("button.lib-switch");
await page.waitForFunction(() => {
  const pop = document.getElementById("lib-libraries");
  return !!pop && !pop.hidden && pop.contains(document.activeElement) && document.activeElement !== pop;
});
await page.keyboard.press("Escape");
await expect(page.evaluate(() => document.getElementById("lib-libraries").hidden
  && document.activeElement?.classList.contains("lib-switch")
  && window.__lastEscape?.defaultPrevented === true),
  "Escape closes the popover, is consumed, and returns focus to its trigger");
await page.keyboard.press("Escape");
await expect(page.evaluate(() => window.__lastEscape?.defaultPrevented === false),
  "with nothing open, Escape is left to the host");
step("overlays focus their content, and Escape closes, is consumed and restores focus");

// MF-009: a legacy audit history is read-only and says so, empty or not, even
// though the Core sends `invalid: ""` beside `legacy`. File edits are listed
// without claiming which requirement they affected. The payload has the shape
// tests/test_closure_lifecycle.py reads from a real legacy session log.
const legacyText = "a verified reduction of 'R1' names no contract: preserved for review, not current evidence";
const legacyAs = (requirements) => async (route) => {
  try {
    const response = await route.fetch();
    const body = await response.json();
    const base = body.session ?? { session: "legacy-smoke", purpose: "audited", status: "parked", phase: "frame" };
    body.session = { ...base, predicate_inspector: { actionable: false, invalid: "", legacy: legacyText,
      scope: "exact predicates", requirements },
      audit: { ...(base.audit ?? {}), external_edits: [{ path: "Notes/A.md", fingerprint: "", source: "obsidian", epoch: 2 }] } };
    await route.fulfill({ response, json: body });
  } catch { /* the page moved on */ }
};
await page.route("**/api/state", legacyAs([]));
await page.reload();
await page.evaluate(() => { const pane = document.querySelector(".lib-pane"); if (pane && getComputedStyle(pane).display === "none") document.querySelector("button[aria-label='Show the document pane']")?.click(); });
await page.waitForSelector(".lib-predicate-inspector >> text=This audit history is legacy and is read-only");
await expect(page.isVisible(".lib-predicate-inspector >> text=This history records no requirements."),
  "an empty legacy history still shows its read-only banner");
await expect(page.isVisible(".lib-predicate-inspector button:has-text('Start a new thread')"),
  "a halted history offers a separate new thread");
await expect(page.isVisible(".lib-predicate-inspector .lib-inspector-edits code:has-text('Notes/A.md')"),
  "the changed file is listed");
await expect(page.isVisible(".lib-predicate-inspector .lib-inspector-edits >> text=not only those that read the changed file"),
  "the list does not claim which requirement a change affected");
await page.unroute("**/api/state");
await page.route("**/api/state", legacyAs([{ id: "R1", text: "The quoted evidence is present.",
  closure: "authoritative", revision: 1, status: "stale", artifacts: [], predicates: [] }]));
await page.reload();
await page.waitForSelector(".lib-predicate-inspector >> text=This audit history is legacy and is read-only");
await expect(page.isVisible(".lib-predicate-inspector .lib-requirement-card >> text=The quoted evidence is present."),
  "a nonempty legacy history keeps its requirements visible");
await expect(page.locator(".lib-predicate-inspector button:has-text('Request evidence')").count().then((n) => n === 0),
  "a read-only history offers no review actions");
await page.unroute("**/api/state");
await page.route("**/api/tool/list_sessions", (route) => route.fulfill({ status: 200, contentType: "application/json",
  body: JSON.stringify({ sessions: [{ id: "legacy-smoke", purpose: "audited", status: "parked", phase: "frame",
    opened_at: "2026-10-28T10:00:00", question: "an older audited thread", audit_history: "legacy" }] }) }));
await page.reload();
await page.click(".lib-app header button:has-text('Sessions')");
await page.waitForSelector("#lib-sessions >> text=read-only legacy audit history");
await page.keyboard.press("Escape");
await page.unroute("**/api/tool/list_sessions");
await page.reload();
await page.waitForSelector("header nav");
step("legacy audit histories are read-only and say so; changed files are listed without invented causes");

// MF-010: a stopped requirement shows who stopped it and why; a text-only
// revision sends back the exact predicates and verifier parameters (checked
// against the real Core); a refusal keeps its structured details on demand;
// the contract skeleton is read only when opened.
const coreCall = (name, args = {}) => page.evaluate(async ([n, a, s]) => {
  const token = document.querySelector("meta[name=librarian-token]")?.getAttribute("content") ?? "";
  const response = await fetch(`/api/tool/${n}`, { method: "POST", headers: {
    "Content-Type": "application/json", "X-Librarian-Token": token }, body: JSON.stringify({ arguments: a, session: s }) });
  return response.json();
}, [name, args, auditedSession]);
const bindings = (view) => {
  const r1 = view.predicate_inspector.requirements.find((r) => r.id === "R1");
  return { revision: r1.revision, closure: r1.closure,
    predicates: r1.predicates.map((p) => ({ text: p.text, verifier: p.verifier?.id ?? "", subject: p.subject ?? {} })) };
};
const before = bindings(await coreCall("session_status"));
const stopText = "no progress in 3 interactions (3 questions, 0 refused calls): parked for the person";
await page.route("**/api/state", async (route) => {
  try {
    const response = await route.fetch();
    const body = await response.json();
    if (body.session?.predicate_inspector) {
      body.session.predicate_inspector.requirements = body.session.predicate_inspector.requirements.map((r) =>
        r.id === "R1" ? { ...r, status: "blocked", stop: { status: "blocked", by: "core", epoch: 1, reason: stopText } } : r);
    }
    await route.fulfill({ response, json: body });
  } catch { /* the page moved on */ }
});
await page.reload();
await page.evaluate(() => { const pane = document.querySelector(".lib-pane"); if (pane && getComputedStyle(pane).display === "none") document.querySelector("button[aria-label='Show the document pane']")?.click(); });
await page.waitForSelector(".lib-predicate-inspector .lib-inspector-stop >> text=Stopped, by the Core");
await expect(page.isVisible(`.lib-predicate-inspector .lib-inspector-stop >> text=${stopText}`), "the stop reason is shown");
await page.click(".lib-predicate-inspector summary:has-text('Revise the wording and reopen')");
await page.fill("textarea[aria-label='Revised wording for R1']", "The quoted evidence is present, word for word.");
const revised = page.waitForResponse((r) => r.url().endsWith("/api/tool/set_requirement") && r.request().method() === "POST");
await page.click(".lib-predicate-inspector button:has-text('Revise and reopen')");
await revised;
await page.unroute("**/api/state");
const after = bindings(await coreCall("session_status"));
await expect(after.revision === before.revision + 1, `the revision reopened R1 (${before.revision} -> ${after.revision})`);
await expect(JSON.stringify(after.predicates) === JSON.stringify(before.predicates) && after.closure === before.closure,
  `a text-only revision keeps the exact predicates, verifiers and parameters ${JSON.stringify({ before, after })}`);
await page.route("**/api/tool/request_evidence", (route) => route.fulfill({ status: 200, contentType: "application/json",
  body: JSON.stringify({ error: "refused", refused: "AUDIT_EVENT_INVALID", detail: "that requirement is not open",
    details: { kind: "unknown_id", known: ["R1"] } }) }));
await page.reload();
await page.waitForSelector(".lib-predicate-inspector");
await page.fill("input[aria-label='Evidence needed for R1']", "a second quote");
await page.click(".lib-predicate-inspector button:has-text('Request evidence')");
await page.waitForSelector(".lib-predicate-inspector >> text=refused (AUDIT_EVENT_INVALID): that requirement is not open");
await page.click(".lib-predicate-inspector .lib-refusal-details summary");
await expect(page.isVisible(".lib-predicate-inspector .lib-refusal-details pre >> text=unknown_id"),
  "the refusal's structured details are there on demand");
await page.unroute("**/api/tool/request_evidence");
let skeletonReads = 0;
page.on("request", (r) => { if (r.url().includes("/api/session/skeleton")) skeletonReads += 1; });
await expect(skeletonReads === 0, "the skeleton is not read until it is opened");
await page.click(".lib-predicate-inspector summary:has-text('Contract skeleton')");
await page.waitForFunction(() => {
  const body = document.querySelector(".lib-inspector-skeleton");
  return !!body && (!!body.querySelector("pre") || (body.textContent ?? "").startsWith("No skeleton"));
});
await expect(skeletonReads === 1, "opening the skeleton reads it once");
step("stop reasons, exact text-only revision, refusal details and the skeleton on demand");

// Phone width: nothing overflows sideways.
await page.setViewportSize({ width: 390, height: 800 });
await expect(page.evaluate(() => document.documentElement.scrollWidth <= 391), "no horizontal scroll at phone width");
step("phone width");

if (errors.length) throw new Error("page errors: " + errors.join("\n"));
console.log("smoke check passed");
await browser.close();
