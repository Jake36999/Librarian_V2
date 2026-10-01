import json
from pathlib import Path

import pytest

from resource_librarian import clerk, intake, scout, tools, trace  # noqa: F401
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.vault import render_config

from conftest import add_source, write_note

REPO_ROOT = Path(__file__).resolve().parents[2]


def gh_item(name, stars=100, archived=False, spdx="MIT", pushed="2026-09-01T00:00:00Z"):
    return {"full_name": name, "html_url": f"https://github.com/{name}",
            "description": f"{name} does change data capture for Postgres databases",
            "language": "Python", "license": {"spdx_id": spdx}, "topics": ["cdc"],
            "archived": archived, "stargazers_count": stars, "pushed_at": pushed, "size": 900}


SEARCH = "https://api.github.com/search/repositories?q="


@pytest.fixture
def register(vault):
    path = vault.root / "About" / "Domain Register.md"
    path.write_text(path.read_text() + "| Data | change data capture; cdc postgres | databases "
                                       "| no |\n| Offence | exploit kit | | yes |\n")
    add_source(vault.root, "held - one", "Already held.", extra_fm="repo_key: held/one")
    return vault


def ctx(vault, responses=None, tier="contribute"):
    return Context(tier=tier, vault=vault, extras={
        "fetcher": intake.Replay(responses or {}),
        "clerk": clerk.Scripted(lambda p: {"bullets": []} if p["task"] in (
            "mechanics", "uses", "inside", "claims") else {"terms": []} if p["task"] == "terms"
            else {"sensitivity": "normal", "reason": "r"} if p["task"] == "sensitivity"
            else {"bottom_line": "", "what_it_solves": "", "confident": False})})


def test_register_is_parsed(register):
    domains = scout.domains(register)
    assert [d.name for d in domains] == ["Data", "Offence"]
    assert domains[0].seeds == ("change data capture", "cdc postgres")
    assert domains[1].sensitive


def test_discover_records_corroborates_and_skips_held(register):
    responses = {f"{SEARCH}change%20data%20capture*": {"items": [gh_item("a/one"),
                                                                 gh_item("held/one")]},
                 f"{SEARCH}cdc%20postgres*": {"items": [gh_item("a/one"), gh_item("b/two")]}}
    out = REGISTRY.call("scout_discover", {"domain": "Data"}, ctx(register, responses))
    assert out == {"added": 2, "corroborated": 1, "already_held": 1, "errors": []}
    ranked = REGISTRY.call("scout_rank", {}, ctx(register))
    first = ranked["candidates"][0]
    assert first["key"] == "a/one"                       # seen twice outranks seen once
    assert {s["signal"] for s in first["signals"]} == set(scout.DEFAULT_WEIGHTS)
    assert all(s["detail"] for s in first["signals"])


def test_adjudication_audit_never_zeroes(register):
    for role in ("reference", "integration"):
        for posture in ("private", "distributed"):
            audit = scout.audit(role, posture)
            assert audit["total"] > 0, (role, posture)
            assert min(audit["vitality"], audit["reusability"], audit["adoption"]) > 0
    assert scout.audit("reference", "private")["vitality"] > 0.5    # archived is settled


def test_container_expansion_uses_the_curators_words(register):
    add_source(register.root, "someone - awesome-cdc", "A curated list of CDC tools.",
               extra_fm="repo_key: someone/awesome-cdc\ncontainer: true")
    readme = ("# Awesome CDC\n- [rowstream](https://github.com/acme/rowstream) - WAL to Kafka\n"
              "- [held](https://github.com/held/one) - already here\n")
    out = REGISTRY.call("scout_expand", {}, ctx(register, {
        "https://api.github.com/repos/someone/awesome-cdc/readme": readme}))
    assert out == {"containers": 1, "added": 1, "corroborated": 0}
    candidate = scout.CandidateStore(register).all()["acme/rowstream"]
    assert candidate["description"] == "rowstream" and \
        candidate["found_via"] == ["container:someone - awesome-cdc"]


def test_cohort_is_frozen_to_a_visible_note(register):
    REGISTRY.call("scout_discover", {"domain": "Data"}, ctx(register, {
        f"{SEARCH}*": {"items": [gh_item("a/one"), gh_item("b/two")]}}))
    frozen = REGISTRY.call("cohort_freeze", {"size": 5}, ctx(register))
    assert frozen["members"] == 2
    note = (register.root / frozen["note"]).read_text()
    assert "a/one" in note and "select nothing" in note
    assert REGISTRY.call("scout_rank", {}, ctx(register))["total"] == 0   # frozen, not new


def test_sweep_is_gated_then_runs(register):
    c = ctx(register, {f"{SEARCH}*": {"items": [gh_item("a/one")]},
                       "https://api.github.com/repos/a/one": {**gh_item("a/one"),
                                                              "default_branch": "main"},
                       "https://api.github.com/repos/a/one/readme": "a/one streams rows.",
                       "https://api.github.com/repos/a/one/git/trees/main?recursive=1":
                           {"tree": []}})
    REGISTRY.call("scout_discover", {}, c)
    REGISTRY.call("cohort_freeze", {}, c)
    gated = REGISTRY.call("sweep", {}, c)
    assert gated["refused"] == "SWEEP_GATED" and "evaluated" in gated["detail"]
    eval_dir = register.work("eval")
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / "last.json").write_text(json.dumps({"total": 6, "hit": 0.5}))
    assert "0.50" in REGISTRY.call("sweep", {}, c)["detail"]
    (eval_dir / "last.json").write_text(json.dumps({"total": 6, "hit": 1.0}))
    assert "not been read by a person" in REGISTRY.call("sweep", {}, c)["detail"]
    assert REGISTRY.call("cohort_reviewed", {"cohort_id": "cohort-001"},
                         c)["refused"] == "TIER_REFUSED"
    person = Context(tier="curate", vault=register)
    REGISTRY.call("cohort_reviewed", {"cohort_id": "cohort-001"}, person)
    swept = REGISTRY.call("sweep", {}, c)
    assert swept["staged"] == 1 and swept["results"][0]["name"] == "a - one"


def test_evaluate_writes_the_gate_record(register):
    (register.work("eval")).mkdir(parents=True, exist_ok=True)
    (register.work("eval") / "questions.json").write_text(json.dumps({"questions": [
        {"id": "q", "question": "already held", "intent": "donor",
         "expects": ["held - one"]}]}))
    REGISTRY.call("evaluate", {}, Context(tier="consult", vault=register))
    last = json.loads((register.work("eval") / "last.json").read_text())
    assert last["total"] == 1 and last["hit"] == 1.0


SYNTHETIC_TRACE = """
Mapping The Field

I am starting by establishing what hierarchical task planning is, which systems implement it, and where the published benchmarks for it are, before narrowing to multi-agent settings.

[![](https://t1.gstatic.com/faviconV2?url=https://arxiv.org/)

arxiv.org

Hierarchical Planning Survey

](https://arxiv.org/abs/2401.00001)[![](https://t1.gstatic.com/faviconV2?url=https://en.wikipedia.org/)

en.wikipedia.org

Hierarchical task network - Wikipedia

](https://en.wikipedia.org/wiki/Hierarchical_task_network)

Narrowing To Gym Environments

Having read the survey, I am now targeting standardized multi-agent environments that expose hierarchical problems in a common format, which the survey names as the missing piece.

[![](https://t1.gstatic.com/faviconV2?url=https://arxiv.org/)

arxiv.org

A Gym For Hierarchical Problems

](https://arxiv.org/abs/2402.00002)
"""


def test_trace_parser_and_record(vault):
    rounds = trace.parse(SYNTHETIC_TRACE)
    assert [len(r.sources) for r in rounds] == [2, 1]
    assert rounds[1].checkpoints[0]["heading"] == "Narrowing To Gym Environments"
    write_note(vault.root, "Inbox/Trace.md", "type: external_report_process", SYNTHETIC_TRACE)
    out = REGISTRY.call("record_trace", {"path": "Inbox/Trace.md", "tool_name": "Gemini"},
                        Context(tier="contribute", vault=vault))
    assert out["rounds"] == 2 and out["cited_links"] == 3
    from resource_librarian.evidence import EvidenceStore
    links = [r for r in EvidenceStore(vault).iter("external_link")]
    assert {r.payload["identifier"] for r in links} >= {"2401.00001", "2402.00002"}
    assert all("topic" not in r.payload for r in links)


def _atom(entries):
    body = "".join(f"<entry><id>http://arxiv.org/abs/{i}v1</id><title>{t}</title>"
                   f"<summary>{t} abstract.</summary></entry>" for i, t in entries)
    return f'<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">{body}</feed>'


@pytest.mark.skipif(not (REPO_ROOT / "internal docs" / "archive" / "Thinking process.md").exists(),
                    reason="the recorded Gemini trace is not in this checkout")
def test_replay_of_the_recorded_deep_research_trace(vault):
    """M3/M4 acceptance, mechanics: a scripted model walks the trace's own
    rounds through research_round(outside=True) and checkpoint; V2 surfaces
    every arXiv source the trace named, within the trace's round count, and
    its stopping rule fires once the process stops finding anything new.
    (With recorded search responses this tests the harness, not a model's
    judgement; a live run with a real model is the owner's to make.)"""
    text = (REPO_ROOT / "internal docs" / "archive" / "Thinking process.md").read_text()
    # Recorded arXiv search can return only the trace's arXiv sources, so a
    # round that read none (Wikipedia, ResearchGate only) would look empty and
    # correctly stop the replay. The replay covers the rounds it can represent.
    rounds = [r for r in trace.parse(text) if any(trace.ARXIV.search(s["url"])
                                                  for s in r.sources)]
    assert len(rounds) >= 8
    responses: dict = {}
    targets = set()
    for r in rounds:
        found = []
        for s in r.sources:
            m = trace.ARXIV.search(s["url"])
            if m:
                found.append((m.group(1), s["title"].replace("&", "and")))
                targets.add(f"arXiv:{m.group(1)}")
        query = r.checkpoints[0]["heading"]
        responses[f"https://export.arxiv.org/api/query?search_query=all:"
                  f"{__import__('urllib.parse').parse.quote(query)}*"] = _atom(found)
    responses[f"{SEARCH}*"] = {"items": []}
    responses["https://export.arxiv.org/api/query?search_query=*"] = _atom([])
    for i in range(3):
        add_source(vault.root, f"filler {i}", f"Draws pictures number {i}.")
    c = Context(tier="contribute", vault=vault, extras={"fetcher": intake.Replay(responses)})
    import resource_librarian.intake as intake_mod
    intake_mod.ARXIV_INTERVAL, saved = 0.0, intake_mod.ARXIV_INTERVAL
    try:
        for name, args in (("open_session", {"purpose": "explore", "question": "HTN"}),
                           ("advance", {}), ("update_plan", {"fields": {"map": "nothing"}}),
                           ("advance", {}),
                           ("open_brief", {"need": "hierarchical task networks",
                                           "disqualifiers": ["none"]}),
                           ("advance", {})):
            assert "error" not in REGISTRY.call(name, args, c), name
        seen, used = set(), 0
        for r in rounds + [rounds[-1]]:
            used += 1
            out = REGISTRY.call("research_round", {"queries": [r.checkpoints[0]["heading"]],
                                                   "outside": True}, c)
            assert "error" not in out, out
            seen |= {f["ref"] for f in out["outside_found"]}
            headings = [cp["heading"] for cp in r.checkpoints][:4]
            cp = REGISTRY.call("checkpoint", {"learned": r.checkpoints[-1]["text"][:300],
                                              "subthreads": headings[:max(2, len(headings))],
                                              "next_targets": headings[-1:]}, c)
            assert "error" not in cp, cp
            if cp["stop"]:
                break
        assert targets <= seen, sorted(targets - seen)
        assert cp["stop"] and used <= len(rounds) + 1
    finally:
        intake_mod.ARXIV_INTERVAL = saved
