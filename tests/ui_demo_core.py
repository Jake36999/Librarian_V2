"""A demo core for the interface smoke check (ui/smoke.mjs): a seeded vault and
a scripted model, on a free loopback port. Run from .v2: python tests/ui_demo_core.py"""
import json, os, sys, tempfile, threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from walks import library
from test_intake import RESPONSES
from resource_librarian import clerk, intake, providers
from resource_librarian.app import App, build
from resource_librarian.keys import KeyStore
from resource_librarian.providers import Reply, ToolCall
from resource_librarian.registry import REGISTRY, Context

root = Path(tempfile.mkdtemp()) / "Demo Vault"
# A fresh config dir every run: otherwise a key really saved by an earlier
# demo (the settings smoke steps do save one) lands in the real, persistent
# ~/.config/resource-librarian/.env and contaminates every run after it.
os.environ["LIBRARIAN_CONFIG_DIR"] = str(root.parent / "config")
vault = library(root)
REGISTRY.call("ingest", {"ref": "acme/rowstream"}, Context(tier="curate", vault=vault,
              extras={"fetcher": intake.Replay(RESPONSES)}))
# A second, for the two approvals: approved for ingestion, begun from the banner, then
# accepted into the library once ingested (Research Pipeline §4.2).
REGISTRY.call("ingest", {"ref": "arXiv:2405.01234"}, Context(tier="curate", vault=vault,
              extras={"fetcher": intake.Replay(RESPONSES)}))

# Two already-catalogued sources (osquery, duckdb) both use one term: enough
# for the "Scan for concepts" button to have a real candidate to stage, rather
# than an empty queue.
from resource_librarian.evidence import EvidenceStore
EvidenceStore(vault).put("term_usage", "osquery",
                        {"term": "host instrumentation",
                         "sentence": "osquery turns host instrumentation into queryable SQL tables."})
EvidenceStore(vault).put("term_usage", "duckdb",
                        {"term": "host instrumentation",
                         "sentence": "duckdb can analyse host instrumentation data collected across "
                                    "a fleet."})

# A dated and an undated task, on notes that already exist, so "This week"
# has something real to show without depending on the chat walk's own timing.
# On osquery deliberately: task_add re-dumps that note's frontmatter through
# PyYAML, and the properties table is checked on it right after, exercising
# the fix for the flow-style collapse this once triggered (notes.render).
from datetime import date, timedelta
_agenda_ctx = Context(tier="contribute", vault=vault)
REGISTRY.call("task_add", {"note": "osquery", "text": "check for a new stable release",
                          "due": (date.today() + timedelta(days=2)).isoformat()}, _agenda_ctx)
REGISTRY.call("task_add", {"note": "duckdb", "text": "review the changelog"}, _agenda_ctx)

# Test Directive A2 (2026-10-01): three more flows the smoke check walks.
from resource_librarian.staging import StagingStore
_store = StagingStore(vault)
# (a) a staged revision of an accepted note: its banner, and Accept merging it
_store.add({"id": "rev-osquery", "kind": "source", "status": "staged", "source_kind": "repository",
            "name": "osquery (whole text read)", "revision_of": "Sources/repository/osquery.md",
            "sections": {"Claims": "- osquery turns the host into SQL tables a fleet can query "
                                   "(part 1)."},
            "evidence": [], "history": []})
# (c) a document-level lens: drawn from the whole text, a probe answered elsewhere in it
_store.add({"id": "lens-doc-change", "kind": "lens", "status": "staged",
            "name": "Read the whole system by its changes", "source": "osquery",
            "source_quote": "osquery turns host instrumentation into queryable SQL tables.",
            "level": "document",
            "rests_on": ["tables describe the host's state (part 1)",
                         "differential queries report what changed (part 3)"],
            "perspective": "ask what changed across the fleet before what the state is",
            "attends_to": [{"what": "what changed between two queries",
                            "because": "differential queries report what changed"}],
            "probes": [{"question": "what changed since the last scheduled query?",
                        "because": "differential queries report what changed",
                        "confirmed_by": {"claim": "the scheduler keeps the previous result",
                                         "locator": "part 4"}}],
            "history": []})
# (d) a concept review that has fallen due: the review-due action opens a parked learn session
REGISTRY.call("task_add", {"note": "osquery", "text": "Review: host instrumentation",
                          "due": date.today().isoformat()}, _agenda_ctx)
# (b) a staged offering its session has asked the person to promote: read in Staging ->
# Offerings, and promoted from there. Its session is seeded as a log, the way a run that
# drafted it and asked would have left it.
from resource_librarian import notes as _notes
from resource_librarian.session import SessionStore as _Sessions
_sid = REGISTRY.call("open_session", {"purpose": "explore", "question": "watch our hosts"},
                     Context(tier="contribute", vault=vault))["session"]["session"]
_oid = f"{_sid}-host-watch-starter"
_staged = vault.work("staging") / "offerings" / f"{_oid}.md"
_staged.parent.mkdir(parents=True, exist_ok=True)
_staged.write_text(_notes.render(
    {"type": "offering", "offering_kind": "branch_offering", "status": "draft",
     "created": date.today().isoformat(), "sources": ["[[osquery]]"], "project": "",
     "attested_by": "agent", "session": _sid},
    _notes.compose("Host Watch Starter", [
        ("Summary", "Start with osquery: it answers questions about the hosts in SQL."),
        ("Claims", "1. osquery exposes the host as SQL tables.\n"
                   "   > osquery turns host instrumentation into queryable SQL tables.\n"
                   "   - [[osquery]] (Bottom Line)"),
        ("Sources", "- [[osquery]]")])), encoding="utf-8")
_rel = _staged.relative_to(vault.root).as_posix()
_Sessions(vault).append(_sid, {"type": "offering", "id": _oid, "title": "Host Watch Starter",
                               "status": "staged", "path": _rel, "claims": 1})
_Sessions(vault).append(_sid, {"type": "question", "id": "q1", "kind": "confirm", "ref": _oid,
                               "question": f"Promote the offering 'Host Watch Starter' ({_rel}) "
                                           f"into the vault?", "options": ["yes", "no"]})

def model(system, messages, tools):
    last = messages[-1]
    if last["role"] == "user":
        text = last["content"]
        if "project" in text:
            return Reply(text="I'll frame it.", tool_calls=[ToolCall("p1", "create_project", {
                "name": "Host Watch", "stage": "idea", "summary": "Watch our hosts."})])
        return Reply(tool_calls=[ToolCall("o1", "open_session", {"purpose": "explore", "question": "host monitoring"}),
                                 ToolCall("s1", "search", {"query": "operating system state", "intent": "orient"})])
    tool_turns = [m for m in messages if m["role"] == "tool"]
    if tool_turns and tool_turns[-1]["name"] == "create_project":
        return Reply(text="The project note is **written**: [[Host Watch]].")
    return Reply(text="The catalogue holds [[Sources/repository/osquery]], which exposes the operating system "
                      "as SQL tables.\n\n| Source | Fit |\n| --- | --- |\n| osquery | strong |\n| duckdb | partial |\n\n"
                      "- [x] searched the catalogue\n- [ ] check fleet-scale performance")

# The "Local server" listing shows one already-known model and one real,
# unprofiled model id, so the tile's "Profile this model" action has something
# to fetch and describe (the model_specs clerk task below answers it).
MODEL_PAGE = """<html><head><title>openai/gpt-oss-20b - DeepInfra</title></head><body>
<p>OpenAI's open-weight 21B-parameter model, with native tool and function calling
support.</p>
<table><tr><td>Context</td><td>131,072 tokens</td></tr>
<tr><td>Input price</td><td>$0.03 per 1M tokens</td></tr>
<tr><td>Output price</td><td>$0.14 per 1M tokens</td></tr></table></body></html>"""


def model_specs_answers(payload):
    if payload["task"] == "model_specs":
        return {"modality": "Text_Generation", "best_for": ["Long_Conversations"],
                "license_class": "Permissive", "suggested_tier": "Tier_3", "context_length": 131072,
                "price_input_per_1m": 0.03, "price_output_per_1m": 0.14, "tool_calling": True,
                "reasoning": False, "confident": True, "evidence": "Context 131,072 tokens"}
    if payload["task"] == "bottom_line":
        return {"bottom_line": "OpenAI's own open-weight 21B-parameter model.",
                "what_it_solves": "A cheap default for high-volume sub-agent work.",
                "confident": True}
    if payload["task"] == "sensitivity":
        return {"sensitivity": "normal", "reason": "a language model"}
    return {"terms": []}


class LocalServer(providers.Scripted):
    def models(self):
        return ["scripted-demo"]


class DeepInfra(providers.Scripted):
    def models(self):
        return ["openai/gpt-oss-20b", "acme/no-tools-model"]


# A fake key, so the tile's DeepInfra tab queries its listing instead of
# showing "no key saved". The chat model (tier 1) stays under Local server,
# unaffected: this key is never used to call a real endpoint in the demo.
os.environ.setdefault("DEEPINFRA_API_KEY", "sk-demo-fake-not-a-real-key")
local_provider = LocalServer(model, name="scripted-demo")
deepinfra_provider = DeepInfra(model, name="deepinfra-demo")
app = App(vault, token="demo", keys=KeyStore(use_keyring=False),
          allowed_origins=set(filter(None, [os.environ.get("DEMO_HOST_ORIGIN")])),
          provider_for=lambda choice: deepinfra_provider if choice.get("provider") == "deepinfra"
                                     else local_provider,
          broker_timeout=120)

# The person's own "Profile this model" click needs a real fetcher and clerk
# endpoint, which this demo's chat provider does not carry; give ingest its own.
_profile_ctx = Context(tier="curate", vault=vault, extras={
    "clerk": clerk.Scripted(model_specs_answers),
    "fetcher": intake.Replay({"https://deepinfra.com/openai/gpt-oss-20b": MODEL_PAGE})})
from resource_librarian.index import Index as _Index
from resource_librarian.promote import promote as _promote, Draft as _Draft
from resource_librarian.search import Engine as _Engine
_promote(vault, _Engine(_Index(vault)), _Draft(
    name="no-tools-model - deepinfra", kind="model", title="acme/no-tools-model",
    canonical_url="https://deepinfra.com/acme/no-tools-model",
    bottom_line="A small text model with no tool-calling support.",
    what_it_solves="Plain completions where no tool use is needed.",
    fields={"provider": "deepinfra", "model_id": "acme/no-tools-model",
            "modality": "Text_Generation", "best_for": ["Small_Coding_Tasks"],
            "license_class": "Permissive", "suggested_tier": "Tier_2", "tool_calling": False},
    sections={"Specs": "- **Provider**: deepinfra (`acme/no-tools-model`)\n"
                       "- No tool/function calling."}, attested_by="agent"))

# The Deep read button also needs its own clerk, standing in for a model
# running the full lens chain (perspective -> attention -> challenge -> role
# -> probe -> synthesize), so the lens review view has a real, richly-filled
# lens to show rather than an empty queue.
ROWSTREAM_QUOTE = ("rowstream reads the Postgres write-ahead log and streams every row change "
                  "to Kafka topics.")


def deep_read_answers(payload):
    task = payload["task"]
    if task == "points":
        return {"bullets": ["rowstream streams every Postgres row change to Kafka"]}
    if task == "limits":
        return {"bullets": []}
    if task == "terms":
        return {"terms": []}
    if task == "lens_perspective":
        return {"has_perspective": True, "name": "Change-stream first",
                "explanation": "read a data system by asking what changed, not what it "
                              "currently holds",
                "source_quote": ROWSTREAM_QUOTE}
    if task == "lens_attention":
        return {"attends_to": [{"what": "what changed, not the current state",
                                "because": ROWSTREAM_QUOTE}],
                "deprioritizes": ["the database's current snapshot"]}
    if task == "lens_discriminate":
        from conftest import blind_answer
        return blind_answer(payload, "Change-stream first", ROWSTREAM_QUOTE)
    if task == "lens_role":
        return {"role_purpose": "trace what changed and where it propagated",
                "role_capabilities": ["stream processing"],
                "role_expectations": ["names the change, not just the end state"],
                "transfers_to": ["auditing a bank ledger by its transactions, not its balance",
                                 "debugging a UI by its event log, not its final render"]}
    if task == "lens_probe":
        return {"probes": [{"question": "what changed here, not just what the state is now?",
                            "because": ROWSTREAM_QUOTE}],
                "catches": "describing the current state instead of how it got there",
                "applies_when": "on a system with an event or change log",
                "not_when": "on a system with no history, only a snapshot"}
    if task == "lens_synthesize":
        return {"prompt_fragment": "Before describing the current state, trace what changed "
                                   "and where each change propagated to."}
    return {"terms": []}


_deep_read_ctx = Context(tier="contribute", vault=vault,
                         extras={"clerk": clerk.Scripted(deep_read_answers)})
_person_call = app.person_call


def person_call(name, arguments, session=""):
    if name == "ingest" and str(arguments.get("ref", "")).startswith("model:"):
        return REGISTRY.call(name, arguments, _profile_ctx)
    if name == "deep_read":
        return REGISTRY.call(name, arguments, _deep_read_ctx)
    return _person_call(name, arguments, session)


# A tiny fixed MCP Registry, for the settings smoke steps' Browse box - not
# the real network (offline, deterministic), same fake-server-on-a-thread
# pattern as test_clerk.py, shaped like the real registry's own response
# (confirmed live against registry.modelcontextprotocol.io on 2026-09-27;
# see tests/test_mcp_client.py's fixture for the same fixed page).
if app.mcp is not None:
    import resource_librarian.mcp_client as _mcp_client
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _FakeRegistry(BaseHTTPRequestHandler):
        def do_GET(self):                                     # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"servers": [{"server": {
                "name": "io.github.example/weather-mcp",
                "title": "Weather MCP",
                "description": "Current conditions and forecasts, no key required.",
                "repository": {"url": "https://github.com/example/weather-mcp"},
                "packages": [{"registryType": "npm", "identifier": "weather-mcp",
                             "transport": {"type": "stdio"}}]}}]}).encode())

        def log_message(self, *a):
            pass

    _registry_server = HTTPServer(("127.0.0.1", 0), _FakeRegistry)
    threading.Thread(target=_registry_server.serve_forever, daemon=True).start()
    _mcp_client.REGISTRY_SEARCH_URL = (
        f"http://127.0.0.1:{_registry_server.server_address[1]}/v0/servers")

app.person_call = person_call

server = build(app, 0)
print(json.dumps({"url": f"http://127.0.0.1:{server.server_address[1]}/"}), flush=True)
server.serve_forever()
