"""One scripted session, written once and driven through every surface: the
registry directly, the MCP server, and the agent loop (M5's acceptance)."""
import re

from resource_librarian.init import init
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.vault import Vault

from conftest import add_source
from test_sessions import OSQUERY_LINE


def library(root):
    init(root, name="Test Vault")
    add_source(root, "osquery", OSQUERY_LINE,
               "Query operating system state such as processes and open sockets.")
    add_source(root, "duckdb", "An in-process analytical SQL database for a laptop.",
               "Analytical queries over local files.")
    add_source(root, "painter", "Draws pictures of cats.", "Illustration.")
    return Vault(root)


def add_project_walk(vault, call):
    """The add_project walk as a model makes it, one tool call at a time; the
    person's answer goes through their own surface at their own tier."""
    session = call("open_session", purpose="add_project")["opened"]

    def ok(_tool, **arguments):
        result = call(_tool, **arguments)
        assert "error" not in result, result
        return result
    ok("create_project", name="Host Watch", stage="planning", summary="Watch our hosts.",
       constraints={"license_class": "Permissive"}, disqualifiers=["requires a GPU"])
    ok("advance")
    ok("update_plan", fields={"ingested": "none"})
    ok("advance")
    ok("search", query="operating system state", intent="orient")
    ok("update_plan", fields={"map": "host tooling is held under Unfiled"})
    ok("advance")
    ok("open_brief", need="query operating system state as a database")
    if ok("advance")["moved"] == "search":
        for _ in range(4):
            ok("research_round", queries=["operating system state database",
                                          "process sockets"], brief="B1")
            if ok("checkpoint", learned="the field says 'host instrumentation'",
                  subthreads=["host tables", "event streams"],
                  next_targets=["osquery tables"])["stop"]:
                break
        ok("advance")
    else:
        ok("add_candidate", source="osquery", brief="B1")
    for c in ok("session_status")["candidates"]:
        if c["disposition"] == "undecided":
            keep = c["source"] == "osquery"
            ok("decide", source=c["source"], disposition="keep" if keep else "reject",
               **({"role": "exposes host state to queries"} if keep
                  else {"reason": "does not do the job"}))
    ok("record_assumptions", assumptions=[
        {"assumption": "the hosts can run a local agent", "settled_by": "unverifiable"}])
    ok("advance")
    ok("record_synthesis", outcome="offering", together="osquery alone covers the need",
       unknowns="performance at fleet scale", open_first="osquery")
    staged = ok("draft_offering", title="Host Watch Starter", summary="Start with osquery.",
                claims=[{"text": "osquery turns host state into SQL tables",
                         "source": "osquery", "quote": OSQUERY_LINE.lower()}])
    asked = ok("promote_offering", offering=staged["offering"])
    person = Context(tier="curate", vault=vault, session=session)
    assert "error" not in REGISTRY.call("answer", {"question_id": asked["question_id"],
                                                   "answer": "yes"}, person)
    ok("promote_offering", offering=staged["offering"])
    ok("advance")
    ok("close_brief", brief="B1", coverage="covered", note="answered by osquery")
    ok("close_session", summary="Framed Host Watch; osquery offered.",
       gaps="nothing on fleet-scale performance")
    return session


STAMP = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?"
                   r"|\"(elapsed|seconds|ms|duration)[a-z_]*\": [0-9.]+"
                   # B4's chain hashes cover each event's clock reading, so they differ too
                   r"|\"h\": \"[0-9a-f]{24}\""
                   # R3's trace names the model behind each call: only the loop knows it
                   r"|\"model\": \"[^\"]*\"")


def artefacts(vault, session):
    """Every file the walk leaves, with the session id and clock readings
    masked; binary index files are derived and compared by what they answer."""
    out = {}
    for path in sorted(vault.root.rglob("*")):
        rel = path.relative_to(vault.root).as_posix()
        if not path.is_file() or "/derived/" in f"/{rel}" or rel.endswith((".sqlite",
                                                                           "-wal", "-shm")):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        out[rel.replace(session, "SESSION")] = STAMP.sub("T", text.replace(session, "SESSION"))
    return out
