"""P7 (2026-10-01): V1 behaviours carried over, each reporting rather than editing.

- freshness (V1 freshness.py): the host asked again; drift reported, never written into a
  note; the least recently checked first.
- duplicates (V1 duplicates.py): pairs that do the same job, above the library's own
  distribution (V1 found a fixed floor could sit above every real pair).
- promote dry run (V1 propose --dry-run): every check an accept makes, nothing written.
- the screening shelf (V1 research_queue shelve): a find screened for a need is not paid
  for twice.
- ingest-cited takes DOIs as well as arXiv ids (V1 ingest_resolved_links did)."""
import json

from resource_librarian import clerk, intake, trace, tools  # noqa: F401  (registers tools)
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.staging import StagingStore

from conftest import add_source, write_note
from test_intake import RESPONSES, clerk_answers

API = "https://api.github.com/repos/example/"


def call(vault, tool_name, /, tier="contribute", fetcher=None, **args):
    extras = {"fetcher": fetcher} if fetcher else {}
    return REGISTRY.call(tool_name, args, Context(tier=tier, vault=vault, extras=extras))


def repos(vault):
    add_source(vault.root, "alpha", "A query planner.", extra_fm="stars: 100")
    add_source(vault.root, "beta", "A log shipper.")
    add_source(vault.root, "gamma", "A metrics store.")
    return {f"{API}alpha": {"full_name": "example/alpha", "archived": True, "stargazers_count": 300,
                            "license": {"spdx_id": "GPL-3.0"}},
            f"{API}beta": {"full_name": "someone-else/beta", "license": {"spdx_id": "MIT"}}}


def test_freshness_reports_drift_and_never_edits_a_note(vault):
    responses = repos(vault)
    before = (vault.root / "Sources/repository/alpha.md").read_text(encoding="utf-8")
    out = call(vault, "freshness_check", fetcher=intake.Replay(responses))
    found = {r["source"]: {f["kind"] for f in r["findings"]} for r in out["results"]}
    assert found["alpha"] == {"archived", "licence_class_disagrees", "stars"}
    assert found["beta"] == {"moved"}
    assert found["gamma"] == {"gone"}
    assert out["warnings"] == 3 and out["drifted"] == 3
    assert (vault.root / "Sources/repository/alpha.md").read_text(encoding="utf-8") == before
    assert list((vault.librarian / "evidence").glob("metadata/*.json")) or \
        list(vault.evidence.glob("metadata/*.json"))                     # each reading kept


def test_freshness_checks_the_least_recently_checked_first(vault):
    responses = repos(vault)
    first = call(vault, "freshness_check", fetcher=intake.Replay(responses), limit=1)
    second = call(vault, "freshness_check", fetcher=intake.Replay(responses), limit=1)
    assert first["results"][0]["source"] != second["results"][0]["source"]


def test_duplicates_are_shortlisted_with_their_evidence(vault):
    same = "Turns the operating system into relational tables you can query with SQL joins."
    add_source(vault.root, "osquery", same, extra_fm="")
    add_source(vault.root, "sysql", same.replace("relational", "SQL-queryable"))
    for i, text in enumerate(["Draws pictures of cats.", "Plays music from a playlist.",
                              "Schedules trains across a network.", "Sorts mail by sender."]):
        add_source(vault.root, f"other {i}", text)
    out = call(vault, "duplicate_report", tier="consult")
    top = out["pairs"][0]
    assert {top["a"], top["b"]} == {"osquery", "sysql"}
    assert {"operating", "tables", "query"} <= set(top["shared_terms"])
    assert top["declared"] == ["kind"] and out["floor"] >= 0.12   # "Unfiled" agrees on nothing
    assert len(out["pairs"]) == 1                             # the unrelated ones stay out


def test_an_accept_can_be_rehearsed_without_writing_anything(library):
    c = Context(tier="curate", vault=library, extras={
        "clerk": clerk.Scripted(clerk_answers), "fetcher": intake.Replay(RESPONSES)})
    item = REGISTRY.call("ingest", {"ref": "acme/rowstream"}, c)["item"]
    out = REGISTRY.call("staging_decide", {"item_ids": [item], "decision": "accept",
                                           "dry_run": True}, c)
    r = out["results"][0]
    assert out["dry_run"] and r["ok"] and r["path"] == "Sources/repository/acme - rowstream.md"
    assert r["coverage"] == "captured" and "What Is Inside" in r["sections"]
    assert not (library.root / r["path"]).exists()
    assert StagingStore(library).load(item)["status"] == "staged"
    agent = REGISTRY.call("staging_decide", {"item_ids": [item], "decision": "accept",
                                             "dry_run": True},
                          Context(tier="contribute", vault=library))
    assert any("promotion.mode" in p for p in agent["results"][0]["problems"])
    write_note(library.root, "Notes/acme - rowstream.md", "type: note", "x")
    clash = REGISTRY.call("staging_decide", {"item_ids": [item], "decision": "accept",
                                             "dry_run": True}, c)
    assert any("UNIQUE_NOTE_NAMES" in p for p in clash["results"][0]["problems"])


def test_a_find_screened_for_a_need_is_not_screened_again(vault):
    from test_scout import SEARCH, _atom
    from test_research_loop import to_need
    from test_sessions import Model
    add_source(vault.root, "osquery", "Exposes the operating system as SQL tables.")
    screens = []

    def answers(payload):
        if payload["task"] == "screen":
            screens.append(payload)
            return {"verdict": "keep", "reason": "does not contradict"}
        return {}
    m = Model(vault)
    m.ctx.extras.update(clerk=clerk.Scripted(answers), fetcher=intake.Replay({
        f"{SEARCH}*": {"items": [{"full_name": "acme/hostwatch", "description": "Host SQL"}]},
        "https://export.arxiv.org/api/query?search_query=*": _atom([])}))
    to_need(m, topics=["host inventory"])
    m.ok("open_brief", need="query operating system state", disqualifiers=["needs a GPU"])
    m.ok("advance")
    first = m.ok("research_round", queries=["host"], brief="B1", outside=True, screen=1)
    assert first["screened"][0]["verdict"] == "keep" and len(screens) == 1
    # a later session, the same need: the find is on the shelf, so no second screen is paid
    later = Model(vault)
    later.ctx.extras.update(m.ctx.extras)
    to_need(later, topics=["host inventory"])
    later.ok("open_brief", need="query operating system state", disqualifiers=["needs a GPU"])
    later.ok("advance")
    again = later.ok("research_round", queries=["host"], brief="B1", outside=True, screen=1)
    assert again["screened"][0]["shelved"] and "already screened" in again["screened"][0]["reason"]
    assert len(screens) == 1


def test_a_cited_doi_is_identified_for_ingest(vault, tmp_path):
    report = tmp_path / "report.md"
    report.write_text("## Findings\nSee [a](https://doi.org/10.1145/3292500.3330701), "
                      "[b](https://arxiv.org/abs/2405.01234) and [c](https://example.org/blog)\n",
                      encoding="utf-8")
    out = trace.record(vault, report, "a research tool")
    refs = {r["url"]: r for r in out["refs"]}
    assert refs["https://doi.org/10.1145/3292500.3330701"]["ref"] == "doi:10.1145/3292500.3330701"
    assert refs["https://arxiv.org/abs/2405.01234"]["identifier_kind"] == "arxiv"
    assert refs["https://example.org/blog"]["identifier_kind"] == ""


from test_intake import library  # noqa: E402,F401  (fixture)


def test_check_notes_flags_copied_prose_and_unaccepted_topics(vault):
    line = "Exposes the operating system as relational tables you can query."
    add_source(vault.root, "osquery", line)
    add_source(vault.root, "copycat", line)
    add_source(vault.root, "drifter", "Something else entirely, described at length here.",
               topic="Made Up Topic")
    out = call(vault, "check_notes", tier="consult", limit=500)
    checks = {(v["check"], v["note"]) for v in out["violations"]}
    assert ("distinct_resource_prose", "osquery") in checks or \
        ("distinct_resource_prose", "copycat") in checks
    assert ("topic_keys_known", "drifter") in checks


def surveyed(vault, name="planner", tree="t1"):
    from resource_librarian.evidence import EvidenceStore
    store = EvidenceStore(vault)
    ids = [store.put("survey", f"https://github.com/example/{name}",
                     {"files": 1436, "truncated": False, "paths": ["src/plan.py"],
                      "tree_sha": tree}).id,
           store.put("code_structure", f"https://github.com/example/{name} (shallow clone)",
                     {"files": 1436, "source_files_read": 40, "test_files": 12,
                      "languages": {"python": 40}, "limited": False,
                      "modules": [{"file": "src/plan.py", "symbols": ["def plan"]}] * 3}).id,
           store.put("access_point", f"https://github.com/example/{name} (shallow clone)",
                     {"routes": [{"path": "/a", "method": "GET"}, {"path": "/b", "method": "GET"}],
                      "entry_points": []}).id]
    add_source(vault.root, name, "A query planner with 1,436 files, 12 test files and 40 "
               "python files.", "It defines 5 modules and serves 2 endpoints.",
               extra_fm="evidence:\n" + "".join(f"- {i}\n" for i in ids))
    return ids


def test_the_numbers_a_note_states_are_checked_against_its_evidence(vault):
    surveyed(vault)
    out = call(vault, "provenance_check", tier="consult", source="planner")
    claims = {c["quantity"]: c for c in out["results"][0]["claims"]}
    assert claims["files"]["outcome"] == "supported" and claims["files"]["stated"] == 1436
    assert claims["test files"]["outcome"] == "supported"
    assert claims["python files"]["outcome"] == "supported"
    assert claims["endpoints"]["outcome"] == "supported"
    assert claims["modules"]["outcome"] == "contradicted" and claims["modules"]["recorded"] == 3
    assert out["contradicted"] == 1


def test_a_repository_file_is_read_at_the_surveyed_version(vault):
    import base64
    surveyed(vault, tree="abc123")
    api = "https://api.github.com/repos/example/planner"
    replay = intake.Replay({
        f"{api}/git/trees/abc123?recursive=1": {"tree": [
            {"path": "src/plan.py", "type": "blob", "sha": "b1"},
            {"path": "logo.png", "type": "blob", "sha": "b2"}]},
        f"{api}/git/blobs/b1": {"content": base64.b64encode(b"def plan():\n    pass\n").decode()},
        f"{api}/git/blobs/b2": {"content": base64.b64encode(b"\x89PNG\x00\x00").decode()}})
    out = call(vault, "read_source_file", tier="consult", fetcher=replay, source="planner",
               path="src/plan.py")
    assert out["text"].startswith("def plan") and out["version"] == "tree abc123 (as surveyed)"
    assert call(vault, "read_source_file", tier="consult", fetcher=replay, source="planner",
                path="src/missing.py")["error"] == "invalid_arguments"
    assert "binary" in call(vault, "read_source_file", tier="consult", fetcher=replay,
                            source="planner", path="logo.png")["detail"]
    assert call(vault, "read_source_file", tier="consult", fetcher=replay, source="planner",
                path="../etc/passwd")["error"] == "invalid_arguments"


def test_the_work_is_searchable_staging_sessions_and_activity(vault):
    from test_sessions import Model
    add_source(vault.root, "osquery", "Exposes the operating system as SQL tables.")
    call(vault, "queue_source", tier="consult", ref="https://example.org/café-planner",
         note="seen in the Zürich talk")
    m = Model(vault)
    m.ok("open_session", purpose="explore", question="host monitoring for Zürich offices")
    m.ok("search", query="operating system")
    m.ok("write_note", folder="Notes", name="Host Plan", body="Start with osquery.")
    staged = call(vault, "search_work", tier="consult", query="zurich talk", scope="staging")
    assert [r["id"] for r in staged["results"]][:1] and staged["results"][0]["status"] == "queued"
    sessions = call(vault, "search_work", tier="consult", query="Zürich monitoring",
                    scope="sessions")
    assert [r["session"] for r in sessions["results"]] == [m.ctx.session]
    assert call(vault, "search_work", tier="consult", query="zurich gardening",
                scope="sessions")["results"] == []                 # every word must match
    activity = call(vault, "search_work", tier="consult", query="host plan", scope="activity")
    assert any(r["what"] == "wrote" and r["target"] == "Notes/Host Plan.md"
               for r in activity["results"])
