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

// No model yet: sending says so, plainly.
await page.fill("#lib-msg", "hello");
await page.keyboard.press("Enter");
await page.waitForSelector(".notice >> text=Choose a chat model first");
step("sending without a model says what to do");

// Model tile: click order sets tiers; clicking again explains; right-click clears.
await page.click(".toolbar .tb:nth-child(4)");
await page.waitForSelector("#lib-models .card");
// The cards re-render once the choice is saved; a click before the save has
// answered lands on the old card and simply chooses it again. Wait for it.
await Promise.all([
  page.waitForResponse((r) => r.url().endsWith("/api/tiers") && r.request().method() === "POST"),
  page.click("#lib-models section:has-text('Local server') .card")]);
// R10: no lead has completed the M0 suite yet, so leading asks for a recorded override.
await page.waitForSelector("#lib-models >> text=has not completed the M0 completion suite");
await Promise.all([
  page.waitForResponse((r) => r.url().endsWith("/api/tiers") && r.status() === 200),
  page.click("#lib-models button:has-text('Use it as lead anyway')")]);
await page.waitForSelector("#lib-models .slot:first-child >> text=scripted-demo");
await page.waitForSelector("#lib-models section:has-text('Local server') .card.sel");
await page.click("#lib-models section:has-text('Local server') .card");
await page.waitForSelector("#lib-models .toast >> text=is tier 1");
await page.click("#lib-models section:has-text('Local server') .card", { button: "right" });
await page.waitForSelector("#lib-models .toast >> text=Selection cleared");
await page.waitForSelector("#lib-models section:has-text('Local server') .card:not(.sel)");
await page.click("#lib-models section:has-text('Local server') .card");
await page.waitForSelector("#lib-models section:has-text('Local server') .card.sel");
await page.keyboard.press("Escape");
await page.waitForSelector(".toolbar >> text=scripted-demo");
step("tiers by click order, right-click clears");

// A turn: tool rail, reply with a note link, plan beside it.
await page.fill("#lib-msg", "explore host monitoring");
await page.keyboard.press("Enter");
await page.waitForSelector(".msg >> text=exposes the operating system");
await page.waitForSelector(".working", { state: "detached" });      // the turn is done, not just its text
await expect(page.isVisible(".tool >> text=opened a thread"), "the rail shows the session opening");
await expect(page.isVisible(".lib-pane .plan >> text=Frame"), "the plan shows the phases beside the chat");
step("a turn streams into the rail and the plan");

// Ask mode: a write waits on a card; switching to Auto releases it.
await page.fill("#lib-msg", "make the project");
await page.keyboard.press("Enter");
await page.waitForSelector(".perm:not(.done)");
await page.click(".toolbar .tb:nth-child(3)");
await page.check("input[name=librarian-mode][value=auto]");
await page.waitForSelector(".perm.done >> text=released by the switch to auto");
await page.waitForSelector(".msg >> text=written");
await page.keyboard.press("Escape");
await page.waitForSelector(".toolbar >> text=Auto");
step("a mode switch releases the waiting write");

// A note link opens the note beside the chat, rendered; ⋮ browses the vault.
await page.click(".msg .wl:has-text('osquery')");
await page.waitForSelector(".lib-pane .doc >> text=Exposes the operating system");
await expect(page.isVisible(".lib-pane .doc table.props >> text=repository"), "frontmatter shows as properties");
// Text to speech: mode A under a reply, mode B beside ⋮ while a document is open.
await expect(page.isVisible(".msg-wrap:not(.user) .msg-actions button[aria-label='Read aloud']"), "a reply can be read aloud");
await expect(page.isVisible(".lib-pane .pane-actions button[aria-label='Read this document']"), "the open document can be read aloud");
await expect(page.isVisible(".lib-pane .pane-crumbs >> text=osquery.md"), "the path shows as breadcrumbs");
await page.click(".lib-pane button[aria-label='Documents menu']");
await page.click(".pane-menu .menuitem.up");
await page.click(".pane-menu .menuitem.up");
await page.click(".pane-menu .menuitem.dir:has-text('Projects/')");
await page.click(".pane-menu .menuitem.file:has-text('Host Watch')");
await page.waitForSelector(".lib-pane .doc-title >> text=Host Watch");
step("a [[link]] opens the note beside the chat; ⋮ browses folders and returns to the plan");

// The Desk: opening a note on this pursuit's thread touches it onto the
// desk automatically; pinning keeps one there for good.
await page.click(".lib-pane button[aria-label='Documents menu']");
await page.waitForSelector(".pane-menu >> text=Desk — Host Watch");
await page.waitForSelector(".pane-menu .desk-row:has-text('osquery')");   // the async desk fetch
await expect(page.isVisible(".pane-menu .desk-row:has-text('Host Watch')"), "the pursuit's own note is on its desk too");
await expect(page.isVisible('.pane-menu .menuitem.pin >> text=Pin "Host Watch"'), "the open note can be pinned from here");
await page.click('.pane-menu button[aria-label="Pin osquery"]');
await page.waitForSelector('.pane-menu button[aria-label="Unpin osquery"]');
step("opening a note on a pursuit's thread touches its desk; pinning keeps it there for good");

// The agenda: "This week" scans every note's own checkboxes, seeded (in the
// demo core) on notes that already exist, with no dependence on this walk.
await page.click(".pane-menu .menuitem:has-text('This week')");
await page.waitForSelector(".lib-pane .agenda >> text=osquery");
await expect(page.isVisible(".lib-pane .agenda >> text=check for a new stable release"), "a dated task shows under its bucket");
await expect(page.isVisible(".lib-pane .agenda h4:has-text('No date')"), "an undated task gets its own bucket");
await expect(page.isVisible(".lib-pane .agenda >> text=review the changelog"), "the undated task itself is shown");
step("This week scans every note's checkboxes and buckets them by due date");

await page.click(".lib-pane button[aria-label='Documents menu']");
await page.click(".pane-menu .menuitem:has-text('Plan')");
await page.waitForSelector(".lib-pane .plan >> text=Frame");
await expect(page.evaluate(() => {
  const composer = document.querySelector(".composer").getBoundingClientRect();
  return composer.bottom > window.innerHeight - 4;
}), "the composer sits at the bottom of the window");
step("⋮ returns to the plan; the composer stays docked at the bottom");

// ⋮ → Rename or move: the note moves, the chat's link to it follows; then back.
await page.click(".msg .wl:has-text('osquery')");
await page.waitForSelector('.lib-pane .doc-title >> text="osquery"');
await page.click(".lib-pane button[aria-label='Documents menu']");
await page.click(".pane-menu .menuitem:has-text('Rename or move')");
await page.fill("#lib-mv-name", "osquery host");
await page.click(".pane-menu .move-form button:has-text('Move')");
await page.waitForSelector('.lib-pane .doc-title >> text="osquery host"');
await expect(page.isVisible(".lib-pane .pane-crumbs >> text=osquery host.md"), "the breadcrumbs show the new name");
await expect(page.isVisible(".lib-pane .doc .moved"), "the pane says what moved");
await expect(page.isVisible(".msg .wl:has-text('osquery host')"), "the chat's link followed the rename");
await page.click(".lib-pane button[aria-label='Documents menu']");
await page.click(".pane-menu .menuitem:has-text('Rename or move')");
await page.fill("#lib-mv-name", "osquery");
await page.click(".pane-menu .move-form button:has-text('Move')");
await page.waitForSelector('.lib-pane .doc-title >> text="osquery"');
await page.click(".lib-pane button[aria-label='Documents menu']");
await page.click(".pane-menu .menuitem:has-text('Plan')");
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
await page.click("#lib-attach .menuitem:has-text('Projects/')");
await page.click("#lib-attach .menuitem:has-text('Host Watch')");
await page.waitForFunction(() => document.querySelector("#lib-msg").value.includes("[[Host Watch]]"));
await page.fill("#lib-msg", "");
step("the paperclip attaches a file into Inbox/, and links an existing note, both inserted into the message");

// Settings: save a key, then overwriting asks first; the key never shows.
// OpenAI, not the default DeepInfra tab: the demo core profiles a DeepInfra
// model with its own key, so DeepInfra already has one saved here.
await page.click(".tb.icon");
await page.selectOption("#lib-provider", "openai");
await page.fill("#lib-key", "sk-demo-SECRET-9999");
await page.click("dialog.settings button:has-text('Save key')");
await page.waitForSelector("dialog.settings #lib-key[placeholder*='9999']");
await page.fill("#lib-key", "sk-demo-OTHER-1111");
await page.click("dialog.settings button:has-text('Overwrite key')");
await page.waitForSelector("dialog.settings .confirm >> text=Replace the saved OpenAI key?");
await page.click("dialog.settings .confirm button:has-text('Cancel')");
await expect(page.evaluate(() => !document.body.innerHTML.includes("SECRET")), "the key is not in the page");
await page.click("dialog.settings button:has-text('Check usage')");
await page.waitForSelector("dialog.settings .usage a:has-text('View on the provider')");
await expect(page.isVisible("dialog.settings .usage >> text=has no usage endpoint"),
  "no usage endpoint says so plainly, alongside the dashboard link");
await page.click("dialog.settings [role=tab]:has-text('Working context')");
await page.fill("#lib-sys", "A thesis on host monitoring");
await page.click("dialog.settings .seg button:has-text('Short')");
await page.click("dialog.settings .seg button:has-text('Coach')");
await page.click("dialog.settings button:has-text('Save')");
await page.waitForSelector("dialog.settings >> text=Saved.");
await page.click("dialog.settings [role=tab]:has-text('Working context')");
await expect(page.isVisible("dialog.settings .seg button[aria-pressed=true]:has-text('Coach')"),
  "the stance choice is saved and shown pressed on reopening the page");
await page.click("dialog.settings [role=tab]:has-text('Library')");
await page.waitForSelector("dialog.settings .srv");
step("settings: key saved and confirmed, usage falls back to a dashboard link, context and library shown");

// Lens packs (roadmap §4 C3): a standard pack is listed, not accepted; Accept
// installs its lenses, and the pack then shows as accepted.
await page.waitForSelector("dialog.settings .lens-packs .srv:has-text('tool-choice')");
await page.click("dialog.settings .lens-packs .srv:has-text('tool-choice') button:has-text('Accept')");
await page.waitForSelector("dialog.settings .lens-packs >> text=tool-choice: 10 lens(es) installed");
await expect(page.isVisible("dialog.settings .lens-packs .srv:has-text('tool-choice') >> text=· accepted ·"),
  "the pack shows as accepted");
await expect(page.isVisible("dialog.settings .lens-packs .srv:has-text('tool-choice') button:has-text('Accept')")
  .then((v) => !v), "and offers no Accept once accepted");
step("lens packs: a standard pack is accepted from Settings → Library, and its lenses installed");

// MCP servers: the curated skill is listed (not installed); browsing the
// registry (a fixed fake page, not the real network) finds a result and
// fills the hand-add form from it without connecting anything; a hand-added
// server (the test fixture, a real stdio subprocess) connects and lists its
// tools; per-tool permission and the enable toggle both reach the API.
await page.click("dialog.settings [role=tab]:has-text('MCP servers')");
await page.waitForSelector("dialog.settings .srv >> text=Semantic Scholar");
await page.click("dialog.settings button:has-text('Search')");
await page.waitForSelector("dialog.settings .browse-results .srv >> text=Weather MCP");
await page.click("dialog.settings .browse-results button:has-text('Fill in below')");
await expect(page.inputValue("dialog.settings input[placeholder='server name']")
  .then((v) => v === "weather-mcp"), "Fill in below carries the registry result's own name in");
await expect(page.inputValue("dialog.settings input[placeholder='command, e.g. npx']")
  .then((v) => v === "npx"), "and its resolved command");
step("MCP servers: browsing the registry finds a result and pre-fills the hand-add form, unconnected");

await page.fill("dialog.settings input[placeholder='server name']", "fake");
await page.fill("dialog.settings input[placeholder='command, e.g. npx']", PYTHON);
await page.fill("dialog.settings input[placeholder='args, space-separated']", FAKE_MCP);
await page.click("dialog.settings button:has-text('Add and accept')");
await page.waitForSelector("dialog.settings .srv-block:has-text('2 tools')");
await page.click("dialog.settings .tool-perms .row2:has-text('fake__echo') button:has-text('Deny')");
await page.waitForSelector("dialog.settings .tool-perms .row2:has-text('fake__echo') button[aria-pressed=true]:has-text('Deny')");
await page.click("dialog.settings .srv-block button:has-text('Disable')");
await page.waitForSelector("dialog.settings .srv-block button:has-text('Enable')");
step("MCP servers: curated skill listed, a hand-added server connects and lists tools, per-tool permission and disable both work");

// Service models (R17, slot 4): chosen with the same model tile, kept with the library.
await page.click("dialog.settings [role=tab]:has-text('Connections')");
await page.waitForSelector("dialog.settings .slot-ocr >> text=Qwen/Qwen3.5-397B-A17B");
await expect(page.isVisible("dialog.settings .slot-ocr >> text=(default)"), "the assigned default is marked");
await expect(page.isVisible("dialog.settings .slot-tts >> text=hexgrad/Kokoro-82M"), "slot 5 (text to speech) holds its default");
await expect(page.isVisible("dialog.settings .slot-tts >> text=cap"), "slot 5 says its spend against its cap");
await expect(page.isVisible("dialog.settings .slot-embeddings >> text=none chosen"), "slot 6 starts empty: nothing is embedded unasked");
await expect(page.isVisible("dialog.settings .slot-embeddings button:has-text('Use a local model')"), "a local embedding model is one click");
await page.click("dialog.settings .slot-ocr button:has-text('Choose…')");
await page.waitForSelector("#lib-models >> text=Choose the OCR model");
await page.click("#lib-models button:has-text('Show all')");
await page.click("#lib-models .card:has-text('openai/gpt-oss-20b')");
await page.waitForSelector("dialog.settings .slot-ocr >> text=openai/gpt-oss-20b");
step("service slot 4: OCR chosen through the model tile and kept with the library");
await page.click("dialog.settings .slot-ocr", { button: "right" });
await page.waitForSelector("dialog.settings .slot-ocr >> text=none chosen");
step("right-click empties a service slot");

// Research Pipeline §6.1: project access is a person's switch, off by default.
await page.click("dialog.settings [role=tab]:has-text('Projects')");
await page.waitForSelector("dialog.settings >> text=Enable project access");
await expect(page.isChecked("#lib-projects-on").then((on) => !on), "project access starts off");
await expect(page.isVisible("dialog.settings >> text=No project folders yet."), "no folder is allowed until a person adds one");
step("settings: project access is off by default and folders are a person's to add");

// Editing is a second, per-folder permission: off when a folder is added.
const projectDir = mkdtempSync(join(tmpdir(), "librarian-project-"));
await page.fill("#lib-project-path", projectDir);
await page.click("dialog.settings button:has-text('Add')");
await page.waitForSelector("dialog.settings .project-root");
const editsBox = "dialog.settings .project-root .project-writes input";
await expect(page.isChecked(editsBox).then((on) => !on), "edits start off for a new folder");
await page.click(editsBox);
await page.waitForSelector("dialog.settings >> text=Edits allowed: each one is still asked.");
await expect(page.isChecked(editsBox), "edits allowed for this folder only");
await page.click("dialog.settings button:has-text('Remove this project')");
await page.waitForSelector("dialog.settings >> text=No project folders yet.");
step("settings: edits are a separate per-folder permission, off until a person ticks it");

await page.click("dialog.settings button:has-text('Close')");

// The effort slider: one control, saved with the app, its meaning in the tooltip.
await page.$eval(".toolbar .effort input", (el) => {
  el.value = "8";
  el.dispatchEvent(new Event("input"));
  el.dispatchEvent(new Event("change"));
});
await page.waitForFunction(() => (document.querySelector(".toolbar .effort")?.getAttribute("title") ?? "").startsWith("Effort 8 of 10"));
await expect(page.textContent(".toolbar .effort .effort-value").then((t) => t === "8"), "the slider shows its level");
step("effort slider: saved, and its tooltip says what it allows");

// Search and staging.
await page.click(".lib-app nav button:has-text('Search')");
await page.fill(".search input[type=search]", "operating system");
await page.keyboard.press("Enter");
// SM-1: everything, grouped by the intent that answered; result-derived facets; tiles that
// say how much of each source was read; a click opens the note beside it.
await page.waitForSelector(".search .tile >> text=osquery");
await expect(page.isVisible(".search .group h3 >> text=Sources"), "everything is grouped by intent");
await expect(page.isVisible(".search >> text=Ran: orient, pattern, made"), "which intents ran is said");
await expect(page.isVisible(".search .tile .depth >> text=read:"), "a tile shows its read depth");
if (await page.locator(".search .facets .chip").count()) {
  await page.locator(".search .facets .chip").first().click();
  await page.waitForSelector(".search button:has-text('Clear filters (1)')");
  await page.click(".search button:has-text('Clear filters')");
  await page.waitForSelector(".search .tile >> text=osquery");
}
await page.click(".search .tile .wl:has-text('osquery')");
await page.waitForSelector(".lib-pane .doc >> text=Exposes the operating system");
step("search: everything grouped by intent, facets narrow and clear, a tile opens its note");
await page.selectOption(".search select[aria-label='Search in']", "staging");
await page.fill(".search input[type=search]", "rowstream");
await page.keyboard.press("Enter");
await page.waitForSelector(".search .tile >> text=acme - rowstream");
await page.selectOption(".search select[aria-label='Search in']", "library");
step("search: the work too - a staged source found by name");
await page.click(".lib-app nav button:has-text('Staging')");
await page.click(".staging .item");
await page.waitForSelector(".staging .evidence");
await expect(page.isVisible(".staging >> text=Only the opening of this source has been read"), "the unread state is said");
await page.click(".staging button:has-text('Deep read')");
await page.waitForSelector(".staging >> text=/Read \\d+ of \\d+ parts/");
await expect(page.isVisible(".staging >> text=/Deep read: \\d+ of \\d+ parts read/"), "progress is kept on the item");
step("deep read reads the source and reports progress");

// The lens review view: every grounded claim shown inline - the quote, the
// probe questions, the failure caught, when it applies - not just a link.
// The list item is matched by its own text, not a bare ".item": switching
// kind repaints the list asynchronously, and a bare selector can still hit
// the previous kind's item for one frame.
await page.click(".staging .seg button:has-text('Lenses')");
await page.waitForSelector(".staging .item:has-text('Change-stream first')");
await page.click(".staging .item:has-text('Change-stream first')");
await page.waitForSelector(".staging .detail >> text=Change-stream first");
await expect(page.isVisible(".staging .detail blockquote.lens-quote >> text=write-ahead log"), "the grounding quote is shown");
await expect(page.isVisible(".staging .detail >> text=Ask this of a similar artifact"), "probe questions are shown");
await expect(page.isVisible(".staging .detail blockquote.lens-quote.small"), "a probe's own grounding quote is shown inline");
await expect(page.isVisible(".staging .detail >> text=describing the current state instead of how it got there"), "the failure it catches is shown");
await expect(page.isVisible(".staging .detail >> text=Applies when:"), "when it applies is shown");
await expect(page.isVisible(".staging .detail >> text=Not when:"), "when it does not apply is shown");
await expect(page.isVisible(".staging .detail >> text=Also fits"), "the transfer test's situations are shown");
step("deep read stages a lens, and its review shows every grounded claim inline");

// Edit at acceptance (C3): a person rewords the stance's name before accepting;
// the edited lens is what the store holds (checked when it is adopted below).
await page.click(".staging .detail summary:has-text('Edit before accepting')");
await page.fill("#lens-edit-name", "Change-stream first, as I put it");
await page.click(".staging .detail button:has-text('Accept')");
await page.waitForSelector(".staging .detail >> text=accepted into the lens store");
step("a lens is edited before it is accepted");
await page.click(".staging .seg button:has-text('Sources')");
await page.waitForSelector(".staging .item:has-text('acme - rowstream')");
await page.click(".staging .item:has-text('acme - rowstream')");
await page.waitForSelector(".staging .evidence");

await page.fill("#lib-bl", "A change-data-capture tool that streams row changes from Postgres.");
await page.fill("#lib-solves", "Getting row changes out of Postgres as a stream.");
await page.click(".staging button:has-text('Accept')");
await page.waitForSelector(".staging >> text=Accepted");
step("search finds; staging accepts with the person's Bottom Line");

// The two approvals (Research Pipeline §4.2): approving only queues a source; a person
// begins the batch from the banner; the ingested source comes back to be accepted.
await page.click(".staging .item:has-text('Lovelace')");
await page.waitForSelector(".staging .evidence");
await page.click(".staging button:has-text('Approve for ingestion')");
await page.waitForSelector(".staging >> text=Approved for ingestion: it waits for the batch");
await page.waitForSelector(".staging .batch-banner >> text=1 source approved and awaiting ingestion.");
await page.click(".staging .batch-banner button:has-text('Click here to begin')");
await page.waitForFunction(() => {
  const text = document.querySelector(".staging .batch-banner")?.textContent ?? "";
  return !text.includes("Processing") && !text.includes("awaiting ingestion");
}, null, { timeout: 30000 });
// The demo's clerk does not answer the full read, so the batch ends with that stage
// unfinished: the source is "partial", never "enriched", and its note says so.
await page.selectOption(".staging select[aria-label='Which sources']", "partial");
await page.click(".staging .item:has-text('Lovelace')");
await page.waitForSelector(".staging .detail >> text=/Ingested in batch-.* with gaps: coverage partial/");
await expect(page.isVisible(".staging .detail >> text=/Not examined: .*waiting for the clerk model/"), "what was not examined is shown");
await page.fill("#lib-bl", "A paper on streaming rows out of a write-ahead log.");
await page.fill("#lib-solves", "Reading database changes as a stream.");
await page.click(".staging button:has-text('Accept with partial coverage')");
await page.waitForSelector(".staging >> text=/Accepted into the library and catalogued \\(coverage: partial/");
await page.selectOption(".staging select[aria-label='Which sources']", "staged");
step("approving queues a source; the banner begins the batch; a partly ingested source is accepted with its coverage stated");

// The concept-candidate flow: a term seen across two sources (seeded in the
// demo core) is scanned, staged, and shows its quoted usages and sources -
// then a person's own Definition, never drafted for them, turns it into a
// Concept note.
await page.click(".staging .seg button:has-text('Concepts')");
await page.click(".staging button:has-text('Scan for concepts')");
await page.waitForSelector(".staging .items >> text=staged");
await page.waitForSelector(".staging .item:has-text('host instrumentation')");
await page.click(".staging .item:has-text('host instrumentation')");
await page.waitForSelector(".staging .detail >> text=Seen across 2 sources");
await expect(page.isVisible(".staging .detail blockquote.lens-quote.small"), "a usage's own quoted sentence is shown");
await expect(page.isVisible(".staging .detail >> text=osquery"), "the sources it was seen in are shown");
await expect(page.isVisible(".staging .detail >> text=duckdb"), "the sources it was seen in are shown");
await page.click(".staging .detail button:has-text('Accept')");
await page.waitForSelector(".staging .detail >> text=A Definition, in your own words, is needed to accept a concept.");
await page.fill("#lib-def", "How much of a host's live state you can see and query.");
await page.click(".staging .detail button:has-text('Accept')");
await page.waitForSelector(".staging >> text=accepted as a Concept note");
step("a term seen across sources is scanned, staged, and accepted with a person's own Definition");
await page.click(".staging .seg button:has-text('Sources')");

// Sessions: the thread is listed and can be picked back up - under the library's own
// name (its folder is "Demo Vault"; the library is called "Test Vault").
await page.click(".lib-app nav button:has-text('Chat')");
await expect(page.isVisible(".lib-switch:has-text('Test Vault')"), "the toolbar names the open library");
await page.click("header .ghost:has-text('Sessions')");
await page.waitForSelector("#lib-sessions h4 >> text=Threads in Test Vault");
await page.waitForSelector("#lib-sessions .menuitem >> text=Host Watch");
await page.click("#lib-sessions .menuitem:has-text('Host Watch')");
await page.waitForSelector(".tool >> text=continuing the thread");
step("sessions list and attach");

// Adoption (C3): the ⋮ menu lists this thread's lenses - the edited one under
// its new name, and the accepted pack's - and a person adopts one into the thread.
await page.click(".lib-pane button[aria-label='Documents menu']");
await page.waitForSelector(".pane-menu >> text=Lenses — this thread");
await page.waitForSelector(".pane-menu .lens-name:has-text('Change-stream first, as I put it')");
await expect(page.isVisible(".pane-menu .lens-name:has-text('The Least-Privilege-First Lens')"),
  "the accepted pack's lenses are offered too");
await page.click('.pane-menu button[aria-label="Adopt Change-stream first, as I put it"]');
await page.waitForSelector('.pane-menu button[aria-label="Drop Change-stream first, as I put it"]');
await page.keyboard.press("Escape");
step("a lens is adopted into the thread from the ⋮ menu, under the name it was accepted with");

// Model profiling: an unprofiled model can be profiled (staged like any other
// source); a model already profiled with tool_calling: false can't lead a
// session, but can still be tier 2 or 3.
await page.click(".toolbar .tb:nth-child(4)");
await page.waitForSelector("#lib-models section:has-text('DeepInfra') .card");
await expect(page.isVisible("#lib-models .card:has-text('acme/no-tools-model') >> text=no tool calling"),
  "a profiled model shows its real specs, not 'unprofiled'");
await page.click("#lib-models button:has-text('Clear selection')");    // start the gate check with no tier chosen
await page.click("#lib-models .card:has-text('acme/no-tools-model')");
await page.waitForSelector("#lib-models .toast >> text=can't lead a session");
await expect(page.locator("#lib-models .slot").first().innerText().then((t) => t.includes("not chosen")),
  "the gated model was not made tier 1");
await page.click("#lib-models section:has-text('DeepInfra') button.profile-link");
await page.waitForSelector("#lib-models .toast >> text=staged for review");
await page.click("#lib-models .card:has-text('openai/gpt-oss-20b')");         // unprofiled: still fine as tier 1
await page.click("#lib-models button:has-text('Use it as lead anyway')");       // R10: not M0-qualified
await page.waitForSelector("#lib-models .slot:first-child >> text=openai/gpt-oss-20b");
await page.click("#lib-models .card:has-text('acme/no-tools-model')");        // now tier 2, no gate on tier 2/3
await page.waitForSelector("#lib-models .slot:nth-child(2) >> text=acme/no-tools-model");
await page.keyboard.press("Escape");
step("an unprofiled model can be profiled; a profiled non-tool-calling model can't lead, but can be tier 2");

await page.click(".lib-app nav button:has-text('Staging')");
await page.click(".staging .item:has-text('gpt-oss-20b')");
await page.waitForSelector(".staging .evidence");
await page.fill("#lib-bl", "OpenAI's own open-weight 21B-parameter model.");
await page.fill("#lib-solves", "A cheap default for high-volume sub-agent work.");
await page.click(".staging button:has-text('Accept')");
await page.waitForSelector(".staging >> text=Accepted");
await page.click(".lib-app nav button:has-text('Chat')");
await page.click(".toolbar .tb:nth-child(4)");
await page.waitForSelector("#lib-models section:has-text('DeepInfra') .card:has-text('openai/gpt-oss-20b') >> text=Tier 3");
await expect(page.isVisible("#lib-models .card:has-text('openai/gpt-oss-20b') >> text=131k ctx"),
  "the accepted model now shows its measured specs in the tile");
await page.keyboard.press("Escape");
step("accepting the staged model finishes profiling it; the tile shows the real specs");

// Test Directive A2 (a): a staged revision of an accepted note says so, and Accept merges it.
await page.click(".lib-app nav button:has-text('Staging')");
await page.click(".staging .seg button:has-text('Sources')");
await page.selectOption(".staging select[aria-label='Which sources']", "staged");
await page.waitForSelector(".staging .item:has-text('osquery (whole text read)')");
await page.click(".staging .item:has-text('osquery (whole text read)')");
await page.waitForSelector(".staging .detail >> text=A revision of an accepted note");
await page.click(".staging .detail button:has-text('Accept')");
await page.waitForSelector(".staging >> text=/Merged Claims into Sources\\/repository\\/osquery.md/");
await expect(page.evaluate(async () => {
  const token = document.querySelector("meta[name=librarian-token]")?.getAttribute("content") ?? "";
  const r = await fetch("/api/file?path=Sources/repository/osquery.md", { headers: { "X-Librarian-Token": token } });
  return r.ok && (await r.json()).text.includes("a fleet can query");
}), "the revision's Claims are in the note");
step("a staged revision of an accepted note: its banner, and Accept merges it");

// (c) a document-level lens: drawn from the whole text; a probe answered elsewhere in it.
await page.click(".staging .seg button:has-text('Lenses')");
await page.waitForSelector(".staging .item:has-text('Read the whole system by its changes')");
await page.click(".staging .item:has-text('Read the whole system by its changes')");
await page.waitForSelector(".staging .detail >> text=Drawn from the whole text");
await expect(page.isVisible(".staging .detail >> text=differential queries report what changed (part 3)"), "the claims it rests on are listed");
await expect(page.isVisible(".staging .detail >> text=Answered elsewhere in the text"), "a probe answered elsewhere says so");
step("a document-level lens: drawn from the whole text, a probe answered elsewhere in it");

// (b) a staged offering is read in full before it is promoted, and promoted from there.
await page.click(".staging .seg button:has-text('Offerings')");
await page.waitForSelector(".staging .item:has-text('Host Watch Starter') >> text=asked: promote?");
await page.click(".staging .item:has-text('Host Watch Starter')");
await page.waitForSelector(".staging .offering-body >> text=osquery turns host instrumentation into queryable SQL tables.");
await expect(page.isVisible(".staging .detail >> text=The session has asked you to promote this"), "the pending question is named");
await page.click(".staging .detail button:has-text('Promote into the library')");
await page.waitForSelector(".staging .detail >> text=/promoted to Offerings\\/Insights\\/Host Watch Starter.md/");
await expect(page.isVisible(".staging >> text=No offering waits to be promoted."), "the list is empty after promoting");
step("a staged offering: read in full in Staging -> Offerings, then promoted from there");

// (d) the review-due action opens a parked learn session for the review that fell due.
await page.click(".lib-app nav button:has-text('Chat')");
await page.click(".toolbar .tb:has-text('Modes')");
await page.click("#lib-modes .menuitem:has-text('review-due')");
await page.waitForFunction(async () => {
  const token = document.querySelector("meta[name=librarian-token]")?.getAttribute("content") ?? "";
  const r = await fetch("/api/tool/list_sessions", { method: "POST", headers: { "Content-Type": "application/json",
    "X-Librarian-Token": token }, body: JSON.stringify({ arguments: {} }) });
  if (!r.ok) return false;
  const out = await r.json();
  return (out.sessions ?? []).some((s) => s.purpose === "learn" && s.status === "parked");
}, null, { timeout: 20000 });
step("the review-due action opens a parked learn session");

// Phone width: nothing overflows sideways.
await page.setViewportSize({ width: 390, height: 800 });
await expect(page.evaluate(() => document.documentElement.scrollWidth <= 391), "no horizontal scroll at phone width");
step("phone width");

if (errors.length) throw new Error("page errors: " + errors.join("\n"));
console.log("smoke check passed");
await browser.close();
