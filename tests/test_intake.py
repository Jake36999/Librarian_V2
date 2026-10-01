"""M4 acceptance: capture -> staged -> promoted for a repository, a paper and a
PDF in Inbox/, each passing the findability check; screening stays on the
candidate; failures are quarantined, never dropped."""
import json

import pytest

from resource_librarian import clerk, intake, notes, tools  # noqa: F401
from resource_librarian.evidence import FRAMING_KEYS, EvidenceStore
from resource_librarian.registry import REGISTRY, Context

from conftest import add_source, pdf_bytes

REPO_META = {"full_name": "acme/rowstream", "html_url": "https://github.com/acme/rowstream",
             "description": "Change data capture that streams row changes from Postgres",
             "language": "Python", "stargazers_count": 1200, "pushed_at": "2026-09-01T00:00:00Z",
             "default_branch": "main", "license": {"spdx_id": "MIT"}, "topics": ["cdc"],
             "archived": False}
README = ("# rowstream\n\nrowstream reads the Postgres write-ahead log and streams every row "
          "change to Kafka topics. Install it with pip and run `rowstream serve`.\n\n"
          "It is used for keeping search indexes and caches in sync with a database.")
TREE = {"truncated": False, "tree": [{"path": p, "type": "blob"} for p in (
    "rowstream/__init__.py", "rowstream/wal.py", "rowstream/kafka.py", "tests/test_wal.py",
    "README.md", "pyproject.toml", "LICENSE")]}
ATOM = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry>
<title>Log-Based Change Capture at Scale</title>
<summary>We show that reading a database write-ahead log gives exactly-once change capture
with bounded lag, and measure it on three production systems.</summary>
<published>2024-05-01T00:00:00Z</published>
<author><name>Ada Lovelace</name></author><author><name>Alan Turing</name></author>
</entry></feed>"""

RESPONSES = {
    "https://api.github.com/repos/acme/rowstream": REPO_META,
    "https://api.github.com/repos/acme/rowstream/readme": README,
    "https://api.github.com/repos/acme/rowstream/license": "MIT License\n\nPermission is "
        "hereby granted, free of charge, to any person",
    "https://api.github.com/repos/acme/rowstream/git/trees/main?recursive=1": TREE,
    "https://export.arxiv.org/api/query?id_list=2405.01234": ATOM,
    "https://api.crossref.org/works/10.1000/xyz": {"message": {
        "title": ["Write-Ahead Logging Revisited"], "author": [{"given": "Grace",
                                                                  "family": "Hopper"}],
        "issued": {"date-parts": [[2019]]}, "container-title": ["Journal of Logs"],
        "abstract": "<p>A survey of write-ahead logging in relational databases.</p>"}},
}


def first_sentence(payload):
    chunk = payload["user"].split("---\n", 1)[1].rsplit("\n---", 1)[0]
    for line in chunk.splitlines():
        line = line.strip("-#* ")
        if len(line.split()) >= 6:
            return line[:150]
    return chunk[:150]


def clerk_answers(payload):
    task = payload["task"]
    line = first_sentence(payload)
    if task in ("mechanics", "uses", "inside", "claims", "points"):
        return {"bullets": [line]}
    if task == "limits":
        return {"bullets": []}                  # most texts state none: a normal answer
    if task == "terms":
        chunk = payload["user"].split("---\n", 1)[1]
        sentence = next((s.strip(" #\n") for s in chunk.split(".") if "write-ahead log" in s),
                        "")
        return {"terms": [{"term": "write-ahead log", "sentence": sentence.split("\n")[-1]}]}
    if task == "sensitivity":
        return {"sensitivity": "normal", "reason": "database tooling"}
    if task == "bottom_line":
        return {"bottom_line": line, "what_it_solves": line, "confident": True}
    if task == "screen":
        return {"verdict": "unclear", "reason": "does not say"}
    if task.startswith("axis:"):
        return {"value": payload["schema"]["properties"]["value"]["enum"][0],
                "confident": False}
    return {}


@pytest.fixture
def library(vault):
    for i in range(4):
        add_source(vault.root, f"filler {i}", f"Draws pictures number {i}.")
    return vault


def ctx(vault, tier="curate", answers=clerk_answers):
    endpoint = clerk.Scripted(answers)
    return Context(tier=tier, vault=vault, extras={
        "clerk": endpoint, "fetcher": intake.Replay(RESPONSES)})


def accept(c, item):
    out = REGISTRY.call("staging_decide", {"item_ids": [item], "decision": "accept"}, c)
    return out["results"][0]


def test_repository_capture_to_catalogued(library):
    c = ctx(library)
    staged = REGISTRY.call("ingest", {"ref": "acme/rowstream"}, c)
    assert staged["status"] == "staged", staged
    item = json.loads((library.work("staging") / "source" / f"{staged['item']}.json").read_text())
    assert item["fields"]["license_class"] == "Permissive"          # read, not guessed
    assert item["fields"]["ecosystem"] == "Python" and item["fields"]["stars"] == 1200
    assert "Architecture & Mechanics" in item["sections"] and "What Is Inside" in item["sections"]
    kinds = sorted(e["kind"] for e in item["evidence"])
    assert kinds == ["metadata", "readme", "survey"]
    assert any(r.kind == "term_usage" for r in EvidenceStore(library).iter())
    result = accept(c, staged["item"])
    assert result["promotion"]["catalogued"], result
    note = notes.load(library.root / result["promotion"]["path"])
    assert note.frontmatter["kind"] == "repository" and len(note.frontmatter["evidence"]) == 3
    assert "`" in note.sections()["Evidence"]


def test_paper_capture_to_catalogued(library):
    c = ctx(library)
    staged = REGISTRY.call("ingest", {"ref": "arXiv:2405.01234"}, c)
    assert staged["status"] == "staged" and staged["name"].startswith("Lovelace, 2024 - ")
    result = accept(c, staged["item"])
    assert result["promotion"]["catalogued"], result
    note = notes.load(library.root / result["promotion"]["path"])
    assert note.frontmatter["identifier_kind"] == "arxiv"
    assert note.frontmatter["authors"] == ["Ada Lovelace", "Alan Turing"]
    assert "Claim" in note.sections()
    assert "What It Solves" not in note.sections()         # a paper's schema has no such heading
    doi = REGISTRY.call("ingest", {"ref": "https://doi.org/10.1000/xyz"}, c)
    assert doi["status"] == "staged" and doi["name"].startswith("Hopper, 2019")


def test_a_papers_off_topic_abstract_is_screened_out_before_claims_runs(library):
    def answers(payload):
        if payload["task"] == "relevance":
            return {"verdict": "reject", "reason": "shares no substance with the topic"}
        return clerk_answers(payload)
    c = ctx(library, answers=answers)
    REGISTRY.call("open_session", {"purpose": "explore", "question": "cooking recipes"}, c)
    REGISTRY.call("advance", {}, c)                                # frame -> map
    REGISTRY.call("update_plan", {"fields": {"map": "done"}}, c)
    REGISTRY.call("advance", {}, c)                                # map -> need
    REGISTRY.call("open_brief", {"need": "cooking recipes",
                                 "disqualifiers": ["needs an oven"]}, c)
    REGISTRY.call("advance", {}, c)                                # need -> search
    out = REGISTRY.call("ingest", {"ref": "arXiv:2405.01234", "brief": "B1"}, c)
    assert out["status"] == "screened_out"
    assert "does not engage" in out["detail"]
    assert out["screen"]["relevance"]["verdict"] == "reject"
    # The larger claims pass is spent only on survivors.
    assert not any(p["task"] == "claims" for p in c.extras["clerk"].payloads)


def test_a_papers_on_topic_abstract_is_not_screened_out(library):
    def answers(payload):
        if payload["task"] == "relevance":
            return {"verdict": "keep", "reason": "engages with the topic"}
        return clerk_answers(payload)
    c = ctx(library, answers=answers)
    REGISTRY.call("open_session", {"purpose": "explore", "question": "database logs"}, c)
    REGISTRY.call("advance", {}, c)                                # frame -> map
    REGISTRY.call("update_plan", {"fields": {"map": "done"}}, c)
    REGISTRY.call("advance", {}, c)                                # map -> need
    REGISTRY.call("open_brief", {"need": "database logs",
                                 "disqualifiers": ["needs a GPU"]}, c)
    REGISTRY.call("advance", {}, c)                                # need -> search
    out = REGISTRY.call("ingest", {"ref": "arXiv:2405.01234", "brief": "B1"}, c)
    assert out["status"] == "staged"
    assert out["screen"]["relevance"]["verdict"] == "keep"
    assert any(p["task"] == "claims" for p in c.extras["clerk"].payloads)


MODEL_PAGE = """<html><head><title>openai/gpt-oss-20b - DeepInfra</title></head><body>
<h1>gpt-oss-20b</h1>
<p>OpenAI's open-weight 21B-parameter model, released under the Apache 2.0 licence, with
native tool and function calling support.</p>
<table><tr><td>Context</td><td>131,072 tokens</td></tr>
<tr><td>Input price</td><td>$0.03 per 1M tokens</td></tr>
<tr><td>Output price</td><td>$0.14 per 1M tokens</td></tr></table>
</body></html>"""


def model_answers(payload):
    task = payload["task"]
    if task == "model_specs":
        return {"modality": "Text_Generation", "best_for": ["Small_Coding_Tasks"],
                "license_class": "Permissive", "suggested_tier": "Tier_3", "context_length": 131072,
                "price_input_per_1m": 0.03, "price_output_per_1m": 0.14, "tool_calling": True,
                "reasoning": False, "confident": True,
                "evidence": "Context 131,072 tokens"}
    if task == "bottom_line":
        return {"bottom_line": "OpenAI's own open-weight 21B-parameter model.",
                "what_it_solves": "A cheap, capable default for high-volume sub-agent and "
                                  "tool-calling work.", "confident": True}
    if task == "sensitivity":
        return {"sensitivity": "normal", "reason": "a language model"}
    if task == "terms":
        return {"terms": []}
    return {}


def test_model_capture_to_catalogued(library):
    c = Context(tier="curate", vault=library, extras={
        "clerk": clerk.Scripted(model_answers),
        "fetcher": intake.Replay({"https://deepinfra.com/openai/gpt-oss-20b": MODEL_PAGE})})
    staged = REGISTRY.call("ingest", {"ref": "model:deepinfra:openai/gpt-oss-20b"}, c)
    assert staged["status"] == "staged", staged
    item = json.loads((library.work("staging") / "source" / f"{staged['item']}.json").read_text())
    assert item["source_kind"] == "model"
    assert item["fields"]["provider"] == "deepinfra"
    assert item["fields"]["model_id"] == "openai/gpt-oss-20b"
    assert item["fields"]["best_for"] == ["Small_Coding_Tasks"] and item["fields"]["tool_calling"] is True
    assert item["fields"]["context_length"] == 131072
    assert "Specs" in item["sections"] and "131,072" in item["sections"]["Specs"]
    assert any(r.kind == "model_listing" for r in EvidenceStore(library).iter())
    result = accept(c, staged["item"])
    assert result["promotion"]["catalogued"], result
    note = notes.load(library.root / result["promotion"]["path"])
    assert note.frontmatter["kind"] == "model" and result["promotion"]["path"].startswith(
        "Sources/model/")
    assert note.frontmatter["provider"] == "deepinfra"
    assert note.frontmatter["suggested_tier"] == "Tier_3"
    assert "What It's For" in note.sections() and "What It Solves" not in note.sections()
    assert "Specs" in note.sections()

    again = REGISTRY.call("ingest", {"ref": "model:deepinfra:openai/gpt-oss-20b"}, c)
    assert again["status"] == "already_held"

    refused = REGISTRY.call("ingest", {"ref": "model:openai:gpt-5"}, c)
    assert refused["status"] == "quarantined"       # no known listing page for "openai"


def test_pdf_in_inbox_to_catalogued(library, tmp_path):
    pytest.importorskip("pypdf")
    pdf = library.root / "Inbox" / "wal-notes.pdf"
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(pdf_bytes([["Write-ahead logging keeps every committed change durable before",
                                "it is applied to the tables, so recovery can replay the log."]]))
    c = ctx(library)
    staged = REGISTRY.call("ingest", {"ref": "Inbox/wal-notes.pdf"}, c)
    assert staged["status"] == "staged", staged
    result = accept(c, staged["item"])
    assert result["promotion"]["catalogued"], result
    note = notes.load(library.root / result["promotion"]["path"])
    assert note.frontmatter["file"] == "Sources/document/files/wal-notes.pdf"
    assert not pdf.exists() and (library.root / note.frontmatter["file"]).exists()
    found = REGISTRY.call("search", {"query": "replay the log recovery", "intent": "in_text"}, c)
    assert found["results"] and found["results"][0]["fields"]["note"] == "wal-notes"


def test_a_markdown_file_in_inbox_is_not_taken_for_a_note_already_held(library):
    # A converted PDF arrives as Markdown; the index sees it as a note under
    # its own name, which is the file being ingested, not a copy already held.
    (library.root / "Inbox").mkdir(exist_ok=True)
    (library.root / "Inbox" / "Log Recovery.md").write_text(
        "# Log Recovery\n\nWrite-ahead logging keeps every committed change durable before "
        "it is applied to the tables, so recovery can replay the log.\n", encoding="utf-8")
    c = ctx(library)
    REGISTRY.call("search", {"query": "write-ahead"}, c)          # the index now holds the file
    staged = REGISTRY.call("ingest", {"ref": "Inbox/Log Recovery.md"}, c)
    assert staged["status"] == "staged", staged


def test_evidence_and_staging_carry_no_framing(library):
    c = ctx(library, tier="contribute")
    REGISTRY.call("open_session", {"purpose": "explore", "question": "cdc"}, c)
    REGISTRY.call("advance", {}, c)
    REGISTRY.call("update_plan", {"fields": {"map": "m"}}, c)
    REGISTRY.call("advance", {}, c)
    REGISTRY.call("open_brief", {"need": "SECRET-NEED stream row changes",
                                 "disqualifiers": ["needs a GPU"]}, c)
    REGISTRY.call("advance", {}, c)
    out = REGISTRY.call("ingest", {"ref": "acme/rowstream", "brief": "B1"}, c)
    assert out["status"] == "staged" and out["screen"]["verdict"] == "unclear"
    for record in EvidenceStore(library).iter():
        assert "SECRET-NEED" not in json.dumps(record.payload)
        assert not set(record.payload) & FRAMING_KEYS
    staged = (library.work("staging") / "source" / f"{out['item']}.json").read_text()
    assert "SECRET-NEED" not in staged
    screen = next(p for p in c.extras["clerk"].payloads if p["task"] == "screen")
    assert "SECRET-NEED" in screen["user"]                  # a framed task
    queries = next(p for p in c.extras["clerk"].payloads if p["task"] == "queries")
    assert "SECRET-NEED" in queries["user"]                 # also framed: open_brief's own
    for payload in c.extras["clerk"].payloads:
        if payload["task"] not in ("screen", "queries", "relevance", "fit"):
            assert "SECRET-NEED" not in json.dumps(payload), payload["task"]
    status = REGISTRY.call("session_status", {}, c)
    assert any(cand["source"] == "acme - rowstream" for cand in status["candidates"])


def test_screen_reject_is_recorded_on_the_candidate_not_staged(library):
    def rejecting(payload):
        if payload["task"] == "screen":
            return {"verdict": "reject", "reason": "Postgres only",
                    "contradicts": ["reads the Postgres write-ahead log"]}
        return clerk_answers(payload)
    c = ctx(library, tier="contribute", answers=rejecting)
    REGISTRY.call("open_session", {"purpose": "explore", "question": "cdc"}, c)
    REGISTRY.call("advance", {}, c)
    REGISTRY.call("update_plan", {"fields": {"map": "m"}}, c)
    REGISTRY.call("advance", {}, c)
    REGISTRY.call("open_brief", {"need": "cdc for MySQL", "disqualifiers": ["Postgres only"]}, c)
    REGISTRY.call("advance", {}, c)
    out = REGISTRY.call("ingest", {"ref": "acme/rowstream", "brief": "B1"}, c)
    assert out["status"] == "screened_out"
    assert not list((library.work("staging") / "source").glob("*.json")) \
        if (library.work("staging") / "source").exists() else True
    status = REGISTRY.call("session_status", {}, c)
    cand = next(x for x in status["candidates"] if x["source"] == "acme - rowstream")
    assert cand["disposition"] == "reject" and "Postgres" in cand["reason"]


def test_failures_are_quarantined_and_duplicates_held(library):
    c = ctx(library)
    assert REGISTRY.call("ingest", {"ref": "nobody/nothing"}, c)["status"] == "quarantined"
    assert REGISTRY.call("ingest", {"ref": "hello world"}, c)["status"] == "quarantined"
    quarantined = list((library.work("quarantine") / "intake").glob("*.json"))
    assert len(quarantined) == 2
    assert json.loads(quarantined[0].read_text())["stage"] in ("fetch", "capture")
    first = REGISTRY.call("ingest", {"ref": "acme/rowstream"}, c)
    again = REGISTRY.call("ingest", {"ref": "https://github.com/acme/rowstream"}, c)
    assert again["status"] == "already_held" and again["item"] == first["item"]


def test_no_clerk_queues_descriptions(library):
    c = Context(tier="curate", vault=library, extras={"fetcher": intake.Replay(RESPONSES)})
    staged = REGISTRY.call("ingest", {"ref": "acme/rowstream"}, c)
    assert staged["status"] == "staged" and staged["detail"]["draft"] == "queued"
    assert list((library.work("queue") / "clerk").glob("*.json"))
    item = json.loads((library.work("staging") / "source" / f"{staged['item']}.json").read_text())
    assert item["fields"]["license_class"] == "Permissive"          # facts still read


def test_queue_then_run(library):
    c = ctx(library)
    REGISTRY.call("queue_source", {"ref": "acme/rowstream", "note": "seen in a talk"}, c)
    REGISTRY.call("queue_source", {"ref": "acme/rowstream"}, c)
    out = REGISTRY.call("intake_run", {}, c)
    assert out["processed"] == 1 and out["still_waiting"] == 0


def test_capture_forms():
    assert intake.capture("https://github.com/a/b.git").key == "a/b"
    assert intake.capture("2405.01234v2").kind == "arxiv"
    assert intake.capture("https://arxiv.org/abs/2405.01234").key == "2405.01234"
    assert intake.capture("doi:10.1000/xyz").key == "10.1000/xyz"
    assert intake.capture("https://example.org/post").kind == "page"
