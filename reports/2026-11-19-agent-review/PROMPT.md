# Review and live test of Librarian V2 and Geo-Grapher (UI, UX, design, clarity, inferability)

You are the reviewer. Your job has two parts. **Part A** reviews how both products look, read and behave:
the interface, the experience, the design choices, how clear everything is, and how much a person (or an
agent) can work out *without being told*. **Part B** is a live test: you use both platforms' services the way a
newcomer would, to do real tasks, and you review them as you go. You are not fixing anything. You are
producing evidence about what a first-time user can and cannot do, and why.

Treat every claim in this brief and in earlier reports as something to check, not something to trust.

## 0. Ground rules (read first)

**What you may change**
- **Review only.** Do not edit, commit, push or deploy anything in `D:\Librarian_V2` or
  `F:\uv-data\Geo_Grapher`. Do not switch branches or stash in either checkout (other agents work in them). If you
  want to try something in code, use a throwaway `git worktree` outside the repo.
- The only files you write are your reports, under `D:\Librarian_V2\reports\2026-11-19-agent-review\` (create
  `evidence\` inside it for screenshots and logs). Do not commit them.

**Where you may act on data**
- **Sandbox (you may write here):** the ACCEPT-02 library, `C:\Users\jakem\Librarian ACCEPT-02 Vault`, with source
  material from `E:\DataManagement`. The owner trusts tier-0 agents with full permissions in this isolated setup.
  Use the batch / policy route for accepting sources; do not work around a refusal, and do not change
  `[promotion] mode` or the broker mode without the owner's explicit say-so in this session. If ACCEPT-02 is
  unusable, create a scratch library in your own temp folder instead:
  `.venv\Scripts\python.exe -m resource_librarian init <dir> --name "review-sandbox"`.
- **Real libraries (read only):** `G:\Libraries\Resource-Library`, `G:\Libraries\Parallax`,
  `G:\Libraries\Nonlinear Field Lab`. You may open them, search, read, browse graphs, hover and inspect. You may
  **not** ingest, add a folder, accept, apply, delete, link, change Settings, start or stop their Geo service, or
  restart their Cores. When an action is only worth testing by doing it, do it in the sandbox.
- **Never open a code repository as a library** (`docs/agent-guide.md`, "Which library to use").

**Cores and Geo**
- Agents manage Cores (`docs/agent-guide.md`, "Managing Cores"). Run `host status` first. You may start, restart or
  stop the **sandbox** Core and its Geo service; say what you did. Leave every other Core alone.
- Record what you are testing **at the start**: the Librarian commit (`git -C D:\Librarian_V2 log -1 --oneline`),
  whether the sandbox Core runs that code (a Core keeps the code it started with: restart the sandbox Core if it is
  older), and the Geo-Grapher build (commit `42a4474`; the served bundle should be `index-D0AQRNRL.js`).

**Safety and cost**
- Never print, paste or store API keys, connection tokens, or a Geo `open_url` (it carries a token). Redact them in
  evidence. A Core's loopback API needs the owner connection record (`resource_librarian.connection.load`) and the
  `X-Librarian-Token` header; the Geo page needs its token turned into a cookie. Use them in code; do not echo them.
- **Spend cap: $3 total** on model calls. If the sandbox has no `[budget]`, add `ceiling_usd = 2` to its
  `.librarian/config.toml` for your session and put it back afterwards. Report what you spent (the vault's usage
  log). Do not change Settings → Models & services or any effort setting: they change defaults for every library.
- Windows + Git Bash: `MSYS_NO_PATHCONV=1` for anything starting `/api/...`; heredoc Python turns `\n` into real
  newlines, so write scripts with the editor tools; wrap every command that could run long in `timeout`, send its
  output to a file, and never pipe a long run into `tail`. Never pass `tests/ui_demo_core.py` to pytest (it serves
  forever).
- For the browser, use the built-in browser or the Chrome extension (both reach `127.0.0.1`). Take screenshots as
  evidence. Check light and dark.
- If you find something unsafe or data-losing, stop that line of testing and put it at the top of `SUMMARY.md`
  straight away.

## 1. The surface under test

**Librarian V2** (`D:\Librarian_V2`, branch `feat/geo-per-library-service`). A research library over a vault of
Sources, Concepts and Projects. Surfaces:
- The browser UI, source in `ui/src`, bundled to `src/resource_librarian/ui/`: Chat and sessions (purposes,
  phases, briefs), Staging, Search, Settings, Models, Checkpoints, the library menu, the document pane (Note,
  Browse, Plan, This week), the paperclip menu (attach, link a note or folder, skill registry, workflows), modes.
- The Obsidian plugin (`obsidian/`) hosting the same view.
- The MCP server (`resource-librarian mcp --tier consult|contribute`): tools for open_session, search, ingest,
  staging, claims, projects, and so on.
- Docs a newcomer would meet: the library's own guide note (`About the Librarian and how to use it.md` at the
  root of a new library, if present), `About/Tool Reference.md`, `docs/agent-guide.md`, `docs/operator-guide.md`,
  `docs/terminology.md`, `docs/product-contract.md`.

**Geo-Grapher** (`F:\uv-data\Geo_Grapher`, branch `feat/per-library-service`, commit `42a4474`). A code and
document graph explorer. Surfaces:
- The per-library Geo web app, served by that library's Core (open it from the library; how you find it is part of
  the test). Top bar, canvas tool rail, zoom slider, 3D/List/Matrix views, the Hierarchy, and a right panel with
  **Inspect / Graphs / Build** modes. Build holds: Add a folder (folder map sheet, role correction, licence
  labels), Keep only or remove (with counts), Combine graphs, Compare graphs, Link graphs (declared links), and the
  Graphs tab holds per-graph accent colours. Threads are one colour fading away from their source; hovering a
  thread shows an arrow and its details.
- The MCP server named `geo-grapher` in the client config (tools such as `list_graphs`, `search_entities`,
  `get_entity_content`, `get_architecture_context`, `find_dependants`, `find_similar_code`, `check_architecture`,
  `compile_task_packet`, `federated_search`, `analyze_cross_graphs`, `list_bridges`, `paper_*`).
- Docs: `README.md`, `docs/BUILD_OPERATORS.md`, `docs/INGESTION_POLICY.md`, `GRAPH_WORKSPACE_SPECIFICATION.md`.

**Environment facts to verify, not assume** (they affect what you can reach):
- Four libraries run the current Geo bundle: ACCEPT-02, Nonlinear Field Lab, Parallax, Resource-Library.
- The client config (`~/.claude.json`) at the time of writing points the `librarian` MCP at `F:/uv-data/Geo_Grapher`
  (a code repository, which the agent guide says not to use as a library) and the `geo-grapher` MCP at a catalog
  under `F:/uv-data/Geo_Grapher/output/named-graphs`, which may not be the per-library catalogs the Geo web app
  uses. Find out what your client really offers and
  what each tool actually reaches. Report which services you could reach, how, and what it took. Do not "fix" the
  config; if you must work around it, say how.

## 2. Method and evidence

- **Measured over reported.** A claim about behaviour needs something you observed: a screenshot, a DOM or API
  result, a log line, a count. Where you only read the cause in code, say so.
- Tag every finding **verified** (you reproduced it twice) / **plausible** (read, not reproduced) / **unverified**.
  Give exact steps (URL, viewport, theme, click path, command, input) so someone else can repeat it.
- Rank: **blocker** (cannot proceed, data loss, unsafe) / **high** / **medium** / **low**.
- Report negative results ("tried X, it held") and what was clear, not only what was wrong. An empty search is not
  evidence of absence.
- Keep speculation in sections labelled **Hypothesis**, apart from evidence.
- Cite code as `path:line`. Name screenshots descriptively (`geo-build-tab-dark-1440.png`) and refer to them.
- **Verify task outcomes independently.** "The agent said it worked" is not a result. Check the file, the
  graph, the staged item, the citation.
- You may use helper sub-agents, but the evidence behind every finding must be first-hand or re-checked by you, and
  they follow every rule above.

## 3. Order of work

Do the steps in this order. The order matters: the blind pass is only blind before you read the reviews.

1. **Set up and record** the builds under test and which services you can reach (section 0).
2. **Blind pass (Part B0 and A2).** With only the products themselves (the UI, tool descriptions, the library's own
   guide note, `docs/agent-guide.md`), do **not** read anything under `reports/`, and do not read design docs or
   commit messages yet. Do the cold-start tasks in B0 and the label-only predictions in A2. Write your notes as you
   go; they are evidence of what is and is not inferable.
3. **Read the context.** Now read the earlier reviews and design intent: `reports/2026-11-17-ui-review/`,
   `reports/2026-11-18-ui-review/`, `reports/2026-11-19-stress-test/` (including `GEO-GRAPHER-DESIGN-REVIEW.md` and
   `GEO-GRAPHER-REVIEW-ASSESSMENT.md`), `docs/terminology.md`, `docs/product-contract.md`,
   `F:\uv-data\Geo_Grapher\docs\BUILD_OPERATORS.md`. Note where they now disagree with what you saw.
4. **Part A, the full review** (section 4).
5. **Part B, the live test** (section 5).
6. **Write up** (section 6).

## 4. Part A: review the interface, experience and design

Review both products with these lenses. For each, give findings with evidence and say how much it hurts a newcomer.

**A1. Orientation.** Within about 30 seconds of opening each product, can a newcomer say what it is for, what they
can do, and where to start? What does the first screen tell them, and what does it leave out? What does the
empty or first-run state say? How does a person get from the Librarian to Geo and back, and is it obvious that
they are two products?

**A2. The inferability test (the centre of this review).** For each screen, **before you click anything**, list
every control (text buttons, icon-only controls, tabs, menus, toggles, the scissors, tool-rail icons, zoom slider,
mode tabs, status chips) and write down, from its label, icon, position and neighbours alone:
(a) what you predict it does, (b) what you expect to see afterwards, (c) confidence 1 to 3. Then use it and
record what happened. Score each: **match / partial / wrong / nothing happened**. Cover **at least 60 controls**
across both products, including every icon-only control and every disabled control (is the reason given?).
Produce a scorecard (`INFERABILITY-SCORECARD.md`) with the full table, the match rate by product and by control type
(text, icon-only, menu, toggle, disabled), the ten most misleading labels or icons, and the ten clearest ones.

**A3. Vocabulary and mental model.** List every noun and verb the two products use for their own concepts (library,
vault, source, note, concept, project, session, phase, brief, checkpoint, staging, offering, graph, snapshot,
partition, entity, thread/edge, enclosure, bridge, declared link, ingest, add a folder, combine, compare, keep
only, prune, derive, role, stratum, trust tier, and any others you meet). Flag the same thing with two names, two
things with one name, jargon with no explanation, and words that mean something different in the two products
(compare with `docs/terminology.md`). Then write the mental model a newcomer would form from the interface alone and
compare it with the real one.

**A4. Consistency across the two products.** Visual language (colour, type, spacing, icons, buttons, empty states,
errors, light and dark), interaction patterns (panels, dialogs, confirmations, undo, how a long job is shown),
and names for equivalent actions. Do they feel like one product family? Where do they diverge without a reason?

**A5. Feedback, state and recovery.** For each action that takes time, changes data or can fail: is progress
visible, is success confirmed, is a failure explained (what happened, why, what to do next), is a disabled
control explained, can the action be undone, and is it clear **before** acting whether it can be? Examine the
parts where this matters most: ingest and staging, accept and apply, session phases and refusals, Geo's
Build operators ("sources are never changed"), declared links and taking them back, the folder-map sheet.

**A6. Information design and the Geo canvas.** Hierarchy, density, truncation, readability, contrast. For the
canvas, test whether a viewer can **decode** it: node colour by content, a graph's accent on its enclosure,
thread colour by relationship family, the fade away from the source as direction, dashes as status, bubble size,
the hover arrow and details, the Legend. Give someone's-eye-view questions ("which way does this thread point?",
"which graph is this node in?", "is this link declared or extracted?") and answer them from the screen alone.
Is the Legend enough, and is it where a person would look?

**A7. Accessibility and responsiveness.** Keyboard only (tab order, focus visible, Escape on every popover and
dialog, no traps), screen-reader names (run axe where it helps), 375x812, 768x1024, 1280x900 and 1440x1000
viewports, 200% zoom, reduced motion, light and dark. Note what is lost on a narrow screen.

**A8. Design decisions audit.** List each notable design decision you meet (for example: right-panel modes, the
Build tab, scissors opening Build, the folder-map sheet, "licence status is a label, not a gate", per-graph
colours, "declared link" as a concept kept apart from extracted facts, permission modes, the phase and brief
workflow, the paperclip menu). For each: the intent (from the docs), what a first-time user would infer, whether
it is defensible, the best alternative, and a verdict **Keep / Clarify / Rethink** with a reason.

**A9. Agent experience.** Read the tools as an agent that has never seen them: names, descriptions, parameter
names and defaults, the envelope and `next` hints, tiers, refusal messages, budgets. Would a fresh agent pick the
right tool, and recover from a refusal without help? Where do descriptions disagree with behaviour? Which tool
would it reach for to answer "where is X implemented?" versus "what do the sources say about X?", and is the
boundary between the two products' tools clear from the tools alone?

Useful frameworks: Nielsen's ten heuristics, cognitive load (intrinsic, extraneous, germane), recognition over
recall, and error prevention. Use whichever design-review skill your harness offers, but your findings must come
from using the product.

## 5. Part B: the live test

Use both platforms' services as a newcomer who has a job to do. Before each task write down its **goal** and its
**success criteria**. After it, record the table row below. Keep a **stuck ledger**: every moment you stopped
because you did not know what to do or what a thing meant, with what you tried next.

**B0. Cold start (do first, blind).** From nothing, find out: what the sandbox library contains; how to search it;
how to open its Geo view; what graphs exist and what they cover. Note the first thing you tried, the dead ends and
how you found the way. Count steps.

**B1. Librarian tasks** (sandbox):
1. Answer a real question from the library's sources with citations; spot-check at least five citations against
   the sources.
2. Bring new material in: choose a small folder or a few files from `E:\DataManagement`, ingest it, follow it
   through Staging to accepted, and find it again through Search. Note whether each status made sense.
3. Run sessions in at least two purposes (for example explore, then add_project or suggest) through their phases.
   Note where the phase system guides you and where it blocks or surprises you.
4. Use Search with several scopes, a pinned note or checkpoint, and read Settings enough to say what each section
   is for.

**B2. Geo-Grapher tasks** (sandbox, UI and MCP):
1. In the Geo UI: orient on the graphs; add a folder through Build (read the folder map, correct a wrong role,
   see the licence labels, ingest a part); use **Keep only** and **Remove** on a selection and read the counts
   first; **Compare** two graphs; **declare a link** from a selected item and then take it back; change a graph's
   accent colour; hover threads and say which way they point.
2. Through the `geo-grapher` MCP tools: answer three questions about Librarian V2's own code with citations
   (for example "what calls X?", "where is the permission grant enforced?", "which modules does Y depend on?"),
   then verify each answer by reading the code.

**B3. Cross-platform tasks (the heart of the test).** Tasks that need both products, where you must decide which
to use:
1. "What do the library's sources say about topic T, and which code implements it?" (Librarian sources, then Geo
   code graph.)
2. Ingest a folder in one product and find it in the other. What carries over, and what is named differently?
3. Declare a link between a document graph and a code graph, then try to get from one end to the other as a
   person would. Does the link lead anywhere useful?
4. From a Geo node, get to the Librarian note that discusses it, and back. If there is no path, say what a person
   would have to do.
5. Give a one-paragraph answer to a question a researcher might ask that truly needs both, and say which parts of
   it came from which product and how you verified them.

For **every task**, record:

| Field | What to write |
|---|---|
| Task and success criteria | written before you start |
| Service used | UI, MCP tool, or both, and which |
| Outcome | done / partial / failed, and the independent check you used |
| Effort | clicks or tool calls, wrong turns, rough time |
| Inferable? | what you could tell from the product alone / had to look up / had to guess |
| Friction | 1 (smooth) to 5 (blocked), with the moment it peaked |
| Evidence | screenshot or log path |

Finish Part B with a **service reachability matrix**: for each of the four surfaces (Librarian UI, Librarian MCP,
Geo UI, Geo MCP), whether you reached it, how, how long it took, and what a newcomer would have had to know.

## 6. Deliverables

All in `D:\Librarian_V2\reports\2026-11-19-agent-review\`, uncommitted.

1. `REVIEW-UI-UX.md`: Part A by lens (A1 to A9). A findings table (ID, area, lens, severity, tag, evidence, effect
   on a newcomer, suggested direction in words, not code). Include **at least five specific things done well**,
   naming the control or screen and why it works.
2. `INFERABILITY-SCORECARD.md`: the A2 table and its statistics.
3. `LIVE-TEST.md`: the B0 notes, the task table for B1 to B3, the stuck ledger, the service reachability matrix,
   and a short "what I would change first to make this easier to use" list grounded in the evidence.
4. `SUMMARY.md` (one page): the ten highest-impact findings in order; the three strongest and three weakest design
   choices; the three places a newcomer is most likely to give up; what you recommend doing first; what you could
   not test and why; spend and which builds you tested; open questions for the owner.
5. `evidence\`: screenshots and logs, with secrets redacted.

Before you finish, re-read `SUMMARY.md` and check that every number in it appears in the other files, and that
every severity is backed by a finding you reproduced.

## 7. Out of scope

Fixing anything; performance benchmarking beyond what you notice; a code-quality or security audit (an earlier
round did that: `reports/2026-11-19-stress-test/`), except that a security or data-loss problem you stumble on is
reported at once; changes to the real libraries; changes to shared model settings.
