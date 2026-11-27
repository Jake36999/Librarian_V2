"""M5's planted cases: a commissioned ingestion of a planted folder, through a real Core.

Implementation plan M5, "Done when": a commissioned ingestion of a fixed test folder ends with one
result, reconciles its ledger and stores every link; and these planted cases also pass:
1. one folder held while its siblings continue;
2. every item held;
3. a partial source;
4. cancel and resume;
5. the link kept through acceptance.

Each case runs the real path, through `App.person_call` with the Core's vault writer live: survey, the
Clerk's folder draft (its sensitivity check), the `ingest-folder` pipeline (policy acceptance under
promotion mode agent, queueing, capture), approval, the batch, and acceptance. Only the outside services
are stood in for: the Clerk and the PDF cleanup model are scripted (so they take the standalone endpoint
contract, not the Core's per-route qualification gate), and Geo-Grapher's workspace plan, folder
application and paper publication return what its v1.2 receipts return. The M5 acceptance run of 27 November
covered the same path with the real services.
"""
from __future__ import annotations

import json

import pytest

from resource_librarian import batch, clerk, folder_review, paper_graph
from resource_librarian.app import App
from resource_librarian.ingestion import ledger
from resource_librarian.keys import KeyStore
from resource_librarian.staging import StagingStore
from resource_librarian.tickets import TicketStore
from resource_librarian.vault import render_config

from test_ingest_service import BODY, HEADER, Cleaner, make_pdf
from test_intake import clerk_answers

GRAPH = "planted-third-party-papers"


def paper(path, title):
    """A text PDF like the intake tests' mechanical one, with its own title in its text (identical bytes
    would be caught, rightly, as the same content already held)."""
    return make_pdf(path, [[HEADER, f"{title}, part {i}.", *body, str(i)] for i, body in enumerate(BODY, 1)])


def answers(sensitive: tuple[str, ...]):
    """The Clerk: folder drafts describe the inventory, and the sensitivity check marks the folders
    named in `sensitive`; every other task is the intake tests' scripted Clerk."""
    def answer(payload):
        task, user = payload["task"], payload["user"]
        if task == "folder_brief":
            return {"description": "A folder of PDF documents."}
        if task == "sensitivity" and '"path"' in user:
            path = json.loads(user.split("---\n", 1)[1].rsplit("\n---", 1)[0])["path"]
            return {"sensitivity": "review_required" if path in sensitive else "normal",
                    "reason": "personal records" if path in sensitive else "public papers"}
        return clerk_answers(payload)
    return answer


@pytest.fixture
def planted(vault, tmp_path, monkeypatch):
    """A Core over a fresh library, and a folder outside it: three subfolders of PDFs, one scanned."""
    config = vault.config()
    config.setdefault("promotion", {})["mode"] = "agent"          # the owner's setting, for the policy
    config.setdefault("folders", {})["production_drafting"] = True  # the owner's approval of Clerk drafts
    vault.config_path.write_text(render_config(config))
    root = tmp_path / "planted"
    paper(root / "baseline" / "Stream Systems.pdf", "Stream Systems")
    paper(root / "external" / "Change Capture.pdf", "Change Capture")
    make_pdf(root / "external" / "Scanned Survey.pdf", [[], []])  # no text layer: a partial source
    paper(root / "private" / "Ledger Notes.pdf", "Ledger Notes")
    # Geo-Grapher, stood in: `init-workspace` plans the folder's partitions and suggests a purpose for
    # each (the planted input), and `apply-folder-review` applies the decided groups.
    (vault.librarian / "geographer.json").write_text(json.dumps({"enabled": True, "wheel_version": "0.2.0"}))
    purposes = {".": "own-current", "baseline": "research-docs", "external": "third-party",
                "private": "research-docs"}  # the root as the real plan suggested it (27 November)
    applied: list = []

    def cli(config, operation, payload):
        if operation[0] == "init-workspace":
            return {"plan_version": "workspace-init-v1", "geographer_version": "0.2.0",
                    "shared_survey_fingerprint": payload["fingerprint"], "root": payload["root"],
                    "partitions": [dict(key=name, subtrees=[name], file_counts={".pdf": 1}, bytes=900,
                                        suggestion=dict(purpose=purpose, reasons=["planted"]))
                                   for name, purpose in purposes.items()],
                    "excluded": [], "credential_refusals": {"count": 0, "paths": []}}
        applied.append(payload)
        return {"graphs": [{"label": GRAPH}], "geographer_version": "0.2.0"}
    monkeypatch.setattr(folder_review, "cli", cli)

    def write_artifact(vault, item, *, text_layer=False):
        return {"path": f".librarian/derived/papers/{item['id']}.json", "authorship": "generated",
                "coverage": {"status": "full_conversion", "limitations": []}, "provisional": not text_layer,
                "source": item.get("file", ""), "sha256": "0" * 64}
    published: list = []

    def publish_artifact(vault, item, artifact):
        published.append(item["id"])
        n = len(published)
        return {"published": True, "graph_id": "g_planted", "documents": n, "paper_database": "papers.sqlite",
                "document_id": f"doc:{n}", "cite_as": f"{GRAPH}/doc:{n}", "status": "complete"}
    monkeypatch.setattr(paper_graph, "write_artifact", write_artifact)
    monkeypatch.setattr(paper_graph, "publish_artifact", publish_artifact)
    core = App(vault, coordinate=True, keys=KeyStore(use_keyring=False))
    sensitive: list[str] = []
    original = App._extras

    def extras(self):
        out = original(self)
        out["clerk"] = clerk.Scripted(answers(tuple(sensitive)))
        out["pdf_endpoint"] = Cleaner()
        # The Core's per-route profile gate qualifies real model routes; a scripted Clerk is not one, so
        # it takes the standalone endpoint contract (tools.staging._profile_endpoint). The M5 acceptance
        # run of 27 November passed the gate with the real DeepInfra route.
        out.pop("background_profile_endpoint", None)
        return out
    monkeypatch.setattr(App, "_extras", extras)
    try:
        yield core, root, sensitive, published
    finally:
        core.close_runtime()


def to_the_persons_decisions(core, root, approve_folder_drafts=True):
    """The pipeline, commissioned with the Clerk's folder drafts approved: it surveys, drafts every
    waiting card (the Clerk describes it and checks its sensitivity), accepts by policy, queues and
    captures."""
    run = core.person_call("run_pipeline", {"name": "ingest-folder", "inputs": {
        "path": str(root), "limit": 20, "approve_folder_drafts": approve_folder_drafts}})
    assert run["status"] == "finished", run
    return run


def open_tickets(core, scope_prefix=""):
    return [t for t in TicketStore(core.vault).all(open_only=True) if t["scope"].startswith(scope_prefix)]


def items(core, status):
    return [i["id"] for i in StagingStore(core.vault).items("source", status)]


def test_one_folder_held_while_its_siblings_continue(planted):
    core, root, sensitive, _ = planted
    sensitive.append("private")
    run = to_the_persons_decisions(core, root)
    cards = {c["path"]: c for c in core.person_call("folder_overview", {})["cards"]}
    assert cards["private"]["status"] != "accepted"
    assert cards["baseline"]["status"] == "accepted" and cards["external"]["status"] == "accepted"
    # The held folder has an owner: a reserved decision on the person's agenda, with its reason.
    [held] = open_tickets(core, "folder:")
    assert held["scope"] == f"folder:{cards['private']['id']}" and held["class"] == "reserved_decision"
    assert "sensitive" in held["summary"] and held["queue"] == "agenda"
    # Its siblings went on: their documents were queued and captured; the held folder's were not.
    names = {i["name"] for i in StagingStore(core.vault).items("source")}
    assert {"Stream Systems", "Change Capture", "Scanned Survey"} <= names and "Ledger Notes" not in names
    books = run["outputs"]
    assert books["folders"]["waiting"] == 1 and books["documents"]["not_yet_queued"] == 0
    # The person decides it: the ticket closes by the Core's recheck.
    card = cards["private"]
    out = core.person_call("folder_accept", {"id": card["id"], "folder_fingerprint": card["folder_fingerprint"],
                                             "purpose": "research-docs", "graph": GRAPH})
    assert out.get("status") == "accepted", out
    assert open_tickets(core, "folder:") == []


def test_every_item_held_ends_with_one_result_and_a_ticket_each(planted):
    core, root, sensitive, _ = planted
    sensitive.extend([".", "baseline", "external", "private"])
    run = to_the_persons_decisions(core, root)
    books = run["outputs"]
    assert books["folders"]["accepted"] == 0 and books["folders"]["waiting"] == books["folders"]["surveyed"]
    assert "wait for a decision" in books["next"]
    assert not list(StagingStore(core.vault).items("source"))            # nothing queued or captured
    held = open_tickets(core, "folder:")
    assert len(held) == books["folders"]["surveyed"]
    assert {t["class"] for t in held} == {"reserved_decision"}
    # Run again: still one ticket per held card, never a second.
    to_the_persons_decisions(core, root)
    assert len(open_tickets(core, "folder:")) == len(held)


def test_a_partial_source_is_held_with_a_ticket_and_the_rest_go_on(planted):
    core, root, _, _ = planted
    to_the_persons_decisions(core, root)
    staged = items(core, "staged")
    assert len(staged) == 4
    core.person_call("staging_decide", {"item_ids": staged, "decision": "approve", "reason": "planted"})
    out = core.person_call("process_approved", {})
    assert out["status"] == "finished", out
    store = StagingStore(core.vault)
    by_name = {i["name"]: i for i in store.items("source")}
    assert by_name["Scanned Survey"]["status"] == "partial"
    assert {by_name[n]["status"] for n in ("Stream Systems", "Change Capture", "Ledger Notes")} == {"enriched"}
    [ticket] = open_tickets(core, "batch:")
    assert ticket["class"] == "partial_or_unmet" and ticket["owner"] == "lead"
    assert ticket["evidence"]["items"] == [by_name["Scanned Survey"]["id"]]
    assert ledger(core.vault, str(root))["sources"] == {"enriched": 3, "partial": 1}
    # Rejecting the partial source leaves nothing partial: the next run's recheck closes the ticket.
    core.person_call("staging_decide", {"item_ids": [by_name["Scanned Survey"]["id"]], "decision": "reject",
                                        "reason": "a scan; OCR it first"})
    core.person_call("staging_decide", {"item_ids": [by_name["Stream Systems"]["id"]], "decision": "defer"})
    core.person_call("staging_decide", {"item_ids": [by_name["Stream Systems"]["id"]], "decision": "approve"})
    assert core.person_call("process_approved", {})["status"] == "finished"
    assert open_tickets(core, "batch:") == []


def test_cancel_and_resume_repeats_no_finished_stage(planted, monkeypatch):
    core, root, _, _ = planted
    to_the_persons_decisions(core, root)
    staged = sorted(items(core, "staged"))
    core.person_call("staging_decide", {"item_ids": staged, "decision": "approve"})
    calls: list[tuple[str, str]] = []
    stopped: list[str] = []
    wrapped = []
    for name, fn in batch.STAGES:
        def stage(ctx, item, _name=name, _fn=fn):
            calls.append((item["id"], _name))
            result = _fn(ctx, item)
            if _name == "review" and not stopped:
                stopped.append(item["id"])
                ctx.extras["cancel"].set()                # stop once, after the first source's review
            return result
        wrapped.append((name, stage))
    monkeypatch.setattr(batch, "STAGES", wrapped)
    out = core.person_call("process_approved", {})
    assert out["status"] == "cancelled", out
    before = list(calls)
    resumed = core.person_call("process_approved", {"resume": out["run"]})
    assert resumed["status"] == "finished", resumed
    again = calls[len(before):]
    first = before[0][0]
    # The stopped source finishes from where it stopped: none of its finished stages runs again
    # (before the fix, the resume re-ran validate, parse and the whole read: `clean_file`, which parse
    # writes, was in every stage's completion key).
    done_before = {s for i, s in before if i == first}
    assert not [s for i, s in again if i == first and s in done_before]
    assert ("publish" in {s for i, s in again if i == first})
    # Every source is read exactly once across the two runs.
    reads = [i for i, s in calls if s == "read"]
    assert sorted(reads) == sorted(set(reads)) and len(reads) == len(staged)


def test_the_paper_link_is_kept_through_acceptance(planted):
    from resource_librarian import notes
    core, root, _, published = planted
    to_the_persons_decisions(core, root)
    staged = items(core, "staged")
    core.person_call("staging_decide", {"item_ids": staged, "decision": "approve"})
    core.person_call("process_approved", {})
    store = StagingStore(core.vault)
    enriched = {i["id"]: i for i in store.items("source", "enriched")}
    assert len(enriched) == 3 and sorted(published) == sorted(enriched)  # each read paper published once
    links = {}
    for item_id, item in enriched.items():
        cite = item["processing"]["publication"]["cite_as"]
        out = core.person_call("staging_decide", {"item_ids": [item_id], "decision": "accept"})
        assert out["accepted"] == 1, out
        note = notes.load(core.vault.root / store.load(item_id)["accepted_to"])
        assert note.frontmatter["graph_paper"] == cite
        links[cite] = note.name
    assert len(links) == 3                                  # one paper per note, none shared
    # The ledger reconciles: every captured document accounted for.
    books = ledger(core.vault, str(root))
    assert books["unaccounted_count"] == 0 and books["sources"].get("accepted") == 3



def test_the_pipeline_describes_every_waiting_folder_when_the_spend_is_approved(planted):
    # M5's floor: at least 90% of the non-excluded folders described, with no silent failure.
    core, root, _, _ = planted
    run = to_the_persons_decisions(core, root)
    drafted = run["outputs"]["drafted"]
    assert sorted(drafted["drafted"]) == [".", "baseline", "external", "private"] and drafted["failed"] == []
    cards = core.person_call("folder_overview", {})["cards"]
    described = [c for c in cards if (c.get("description") or {}).get("state") == "model_draft"]
    assert len(described) == len(cards) == 4
    assert all((c.get("sensitivity") or {}).get("sensitivity") == "normal" for c in cards)
    # A second run finds nothing left to draft: drafting is never repeated, so never paid twice.
    again = to_the_persons_decisions(core, root)
    assert again["outputs"]["drafted"]["drafted"] == [] and again["outputs"]["drafted"]["failed"] == []


def test_without_the_spend_approved_nothing_is_drafted_and_each_card_is_held_with_its_remedy(planted):
    core, root, _, _ = planted
    run = to_the_persons_decisions(core, root, approve_folder_drafts=False)
    assert run["outputs"]["drafted"] == {"skipped": True}
    assert run["outputs"]["folders"]["accepted"] == 0
    held = open_tickets(core, "folder:")
    assert len(held) == 4 and {t["class"] for t in held} == {"partial_or_unmet"}
    assert all("folder_draft" in t["summary"] for t in held)
    # The tool itself refuses spend that was not approved, by name.
    out = core.person_call("folder_draft_pending", {"root": str(root)})
    assert out["refused"] == "SPEND_APPROVAL_REQUIRED"


def test_a_draft_refused_for_every_card_is_said_once(planted, vault, monkeypatch):
    # Without the owner's approval of a real Clerk route, each draft would be refused the same way. A
    # scripted Clerk is exempt from that gate by design, so it is wrapped as a plain endpoint here.
    from resource_librarian.vault import render_config
    core, root, _, _ = planted
    config = vault.config()
    config["folders"]["production_drafting"] = False
    vault.config_path.write_text(render_config(config))

    class Plain(clerk.Endpoint):
        name = "plain"

        def __init__(self, inner):
            self.inner = inner

        def complete(self, payload, repair=""):
            return self.inner.complete(payload, repair)
    scripted = App._extras

    def extras(self):
        out = scripted(self)
        out["clerk"] = Plain(out["clerk"])
        return out
    monkeypatch.setattr(App, "_extras", extras)
    run = to_the_persons_decisions(core, root)
    failed = run["outputs"]["drafted"]["failed"]
    assert len(failed) == 1 and failed[0]["refused"] == "FOLDER_DRAFT_DISABLED"


def _decisions(core):
    return {c["path"]: c for c in core.person_call("folder_overview", {})["cards"]}


def test_files_that_appear_in_a_root_decided_by_its_subfolders_are_held_for_the_person(planted):
    # Owner, 27 November: the root accepted as Geo-Grapher suggested (own-current) is fine "as long as no
    # conflicts arise from any changes to the content of the folder". Before, a file added directly to
    # the root re-staged its card and policy re-accepted it as own-current, so the new file was taken as
    # the owner's own work, silently.
    core, root, _, _ = planted
    to_the_persons_decisions(core, root)
    assert _decisions(core)["."]["status"] == "accepted"
    paper(root / "Loose Draft.pdf", "Loose Draft")              # a file directly in the root
    to_the_persons_decisions(core, root)
    cards = _decisions(core)
    assert cards["."]["status"] != "accepted"
    assert cards["."]["previous_decision"]["purpose"] == "own-current"
    [held] = open_tickets(core, "folder:")
    assert held["scope"] == f"folder:{cards['.']['id']}" and held["class"] == "reserved_decision"
    assert "directly in this folder" in held["summary"]
    # Its subfolders' decisions stand, and their documents went on.
    assert {cards[p]["status"] for p in ("baseline", "external", "private")} == {"accepted"}


def test_a_paper_added_to_a_decided_reference_folder_is_still_accepted_by_policy(planted):
    # No conflict: the folder's decision covered files of its own, and the policy decided it, so policy
    # decides it again as before (adding papers to a reference folder stays automatic).
    core, root, _, _ = planted
    to_the_persons_decisions(core, root)
    paper(root / "external" / "New Survey.pdf", "New Survey")
    to_the_persons_decisions(core, root)
    cards = _decisions(core)
    assert cards["external"]["status"] == "accepted"
    assert cards["external"]["decision"]["accepted_by"] == "agent-policy"
    assert open_tickets(core, "folder:") == []
    assert "New Survey" in {i["name"] for i in StagingStore(core.vault).items("source")}


def test_a_persons_decision_is_never_replaced_after_its_content_changes(planted):
    core, root, sensitive, _ = planted
    sensitive.append("private")                                  # held by policy: the person decides it
    to_the_persons_decisions(core, root)
    card = _decisions(core)["private"]
    out = core.person_call("folder_accept", {"id": card["id"], "folder_fingerprint": card["folder_fingerprint"],
                                             "purpose": "third-party", "graph": GRAPH})
    assert out.get("status") == "accepted", out
    sensitive.clear()                                            # the content no longer looks sensitive
    paper(root / "private" / "Another Note.pdf", "Another Note")
    to_the_persons_decisions(core, root)
    cards = _decisions(core)
    assert cards["private"]["status"] != "accepted"             # not re-decided by suggestion
    [held] = open_tickets(core, "folder:")
    assert held["class"] == "reserved_decision" and "after a person decided it" in held["summary"]
