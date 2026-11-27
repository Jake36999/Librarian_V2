"""Semantic metadata from the read (Research Pipeline §3.4 and §4.3 step 5, 30 September; as-is W-REA-02).

The batch's metadata stage asks the Clerk's closed-choice axis and topic tasks again for what is still
unknown after the full read, with the Data and Information records as evidence. What it must keep:
- a value is one of the library's own permitted values, with a quote found in the records;
- an unsupported or unconfident answer leaves the field Unknown;
- a field already set is never asked again or replaced;
- no project or need reaches the task;
- with no Clerk, the literal Data facts are kept, the waiting tasks recorded, and coverage untouched;
- a source with nothing to ask behaves exactly as before.
"""
from __future__ import annotations

import pytest

from resource_librarian import batch, clerk, dik
from resource_librarian.app import App
from resource_librarian.keys import KeyStore
from resource_librarian.registry import Context
from resource_librarian.staging import StagingStore

# Every repository axis but two is already known, so the stage asks only `ecosystem` and
# `interface_protocol` (`domain_primary` has no permitted values yet, so it is never asked).
KNOWN = {"license_class": "Permissive", "maturity_stage": "Active", "deployment_target": "Local_Only",
         "data_locality": "Local_First", "hardware_footprint": "CPU_Only",
         "security_compliance": "Uncertified", "agent_surface": "Callable", "repo_key": "acme/tool"}
RECORD = {"kind": "repository", "data": [
    {"id": "language:Python", "kind": "language", "name": "Python", "locator": "pyproject.toml",
     "status": "observed"},
    {"id": "entry_point:tool", "kind": "entry_point", "name": "tool",
     "locator": "pyproject.toml [project.scripts]", "status": "observed",
     "evidence": "console script tool runs the command-line interface"},
    {"id": "module:hidden", "kind": "module", "name": "never read", "locator": "src/hidden.py",
     "status": "not examined", "evidence": "Rust web dashboard"}], "information": []}


@pytest.fixture
def core(vault):
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False))
    try:
        yield app
    finally:
        app.close_runtime()


def _ctx(core, endpoint=None):
    extras = {"vault_writer": core.writer, "index_service": core.index_service, "caller_kind": "person"}
    if endpoint is not None:
        extras["clerk"] = endpoint
    return Context(tier="curate", vault=core.vault, extras=extras)


def _item(core, name="acme-tool", kind="repository", fields=None, record=RECORD, **values):
    item = {"id": name, "kind": "source", "name": name, "source_kind": kind, "status": "approved",
            "fields": dict(KNOWN if fields is None else fields), "evidence": [{"id": "fixture"}],
            "readiness": ["ecosystem", "interface_protocol"], **values}
    core.writer.submit(lambda: StagingStore(core.vault).add(item), caller="test-seed")
    if record is not None:
        core.writer.submit(lambda: dik.save(core.vault, {"source": name, **record}))
    return item


def _answers(**by_axis):
    def answer(payload):
        return by_axis.get(payload["task"], {"value": "Unknown", "evidence": "", "confident": False})
    return clerk.Scripted(answer)


def test_an_unknown_axis_is_proposed_from_the_reads_records_with_its_evidence(core):
    endpoint = _answers(**{
        "axis:ecosystem": {"value": "Python", "evidence": "language: Python", "confident": True},
        "axis:interface_protocol": {"value": "CLI", "evidence": "runs the command-line interface",
                                    "confident": True}})
    item = _item(core)
    out = batch._metadata(_ctx(core, endpoint), item)
    fresh = StagingStore(core.vault).load(item["id"])
    assert out["status"] == "complete"
    assert out["proposed"] == {"language": "Python", "ecosystem": "Python", "interface_protocol": "CLI"}
    assert sorted(out["asked"]) == ["ecosystem", "interface_protocol"]
    assert fresh["fields"]["ecosystem"] == "Python" and fresh["fields"]["interface_protocol"] == "CLI"
    # The evidence a person sees: the quote, the records it came from, and their locators.
    cli = fresh["metadata_evidence"]["interface_protocol"]
    assert cli["records"] == ["entry_point:tool"] and cli["locators"] == ["pyproject.toml [project.scripts]"]
    assert cli["quote"] == "runs the command-line interface" and cli["task"] == "axis:interface_protocol"
    assert fresh["metadata_proposals"]["language"] == "from the Data records"      # as before
    assert fresh["metadata_proposals"]["ecosystem"].startswith("from the read's Data records, by the clerk")
    assert fresh["readiness"] == []                                  # Staging no longer lists them as missing
    # A record not examined is never offered as evidence.
    assert all("never read" not in p["user"] and "hidden" not in p["user"] for p in endpoint.payloads)


def test_an_answer_the_records_do_not_support_leaves_the_field_unknown(core):
    endpoint = _answers(**{
        # The quote is not in any examined record (only in the one not examined).
        "axis:interface_protocol": {"value": "Web_UI", "evidence": "Rust web dashboard", "confident": True},
        "axis:ecosystem": {"value": "Rust", "evidence": "language: Python", "confident": False}})
    item = _item(core)
    out = batch._metadata(_ctx(core, endpoint), item)
    fresh = StagingStore(core.vault).load(item["id"])
    assert out["status"] == "complete"
    assert "ecosystem" not in fresh["fields"] and "interface_protocol" not in fresh["fields"]
    assert {"ecosystem", "interface_protocol"} <= set(out["unknown"])
    assert "metadata_evidence" not in fresh


def test_a_field_already_set_is_not_asked_again_or_replaced(core):
    endpoint = _answers(**{"axis:interface_protocol": {"value": "CLI",
                                                       "evidence": "runs the command-line interface",
                                                       "confident": True}})
    item = _item(core, fields={**KNOWN, "ecosystem": "Mixed"})
    out = batch._metadata(_ctx(core, endpoint), item)
    fresh = StagingStore(core.vault).load(item["id"])
    assert [p["task"] for p in endpoint.payloads] == ["axis:interface_protocol"]
    assert out["asked"] == ["interface_protocol"]
    assert fresh["fields"]["ecosystem"] == "Mixed"


def test_no_need_or_project_reaches_the_task(core):
    endpoint = _answers()
    item = _item(core, found_for={"need": "NEED-ZEBRA a dashboard for the Owner's project"},
                 session="s-PROJECT-ZEBRA")
    batch._metadata(_ctx(core, endpoint), item)
    assert endpoint.payloads
    for payload in endpoint.payloads:
        assert "ZEBRA" not in payload["user"] and "ZEBRA" not in payload["system"]


def test_with_no_clerk_the_literal_facts_are_kept_and_coverage_is_untouched(core):
    # Waiting tasks are recorded, as capture records its own; the stage completes, because a stage
    # left `queued` would mark a fully read source partial, and metadata is not reading.
    item = _item(core)
    out = batch._metadata(_ctx(core), item)
    fresh = StagingStore(core.vault).load(item["id"])
    assert out["status"] == "complete"
    assert sorted(out["waiting_for_model"]) == ["ecosystem", "interface_protocol"]
    assert sorted(fresh["metadata_waiting"]) == ["ecosystem", "interface_protocol"]
    assert fresh["fields"]["language"] == "Python"                   # the deterministic part, as before
    assert fresh["metadata_proposals"] == {"language": "from the Data records"}
    assert "ecosystem" not in fresh["fields"]


def test_a_source_with_nothing_to_ask_behaves_as_before(core):
    # A document's content model has no axes the Clerk is asked; the stage is what it was.
    endpoint = _answers()
    item = _item(core, name="a-document", kind="document", fields={},
                 record={"kind": "document", "information": [], "data": [
                     {"id": "chapter:pp. 1-3", "kind": "chapter", "name": "Intro", "locator": "pp. 1-3",
                      "status": "observed", "coverage": "full", "claims": ["It measures joins."]}]})
    out = batch._metadata(_ctx(core, endpoint), item)
    assert out == {"status": "complete", **({"unknown": out["unknown"]} if "unknown" in out else {})}
    assert endpoint.payloads == []
    fresh = StagingStore(core.vault).load(item["id"])
    assert "metadata_proposals" not in fresh and fresh["readiness"] == ["ecosystem", "interface_protocol"]


def test_a_fully_read_source_stays_full_when_only_metadata_waits(core):
    # The batch's own bookkeeping, fed the stage's real result: a waiting metadata task must not make
    # the source `partial` or list metadata as not examined (it would claim less was read).
    from resource_librarian.workflows import RunStore
    item = _item(core, status="processing", batch="run-x")
    out = batch._metadata(_ctx(core), item)
    assert out["waiting_for_model"]
    results = {"validate": {"status": "complete"}, "read": {"status": "complete", "coverage": "full"},
               "metadata": out}
    core.writer.submit(lambda: batch._finish_item(StagingStore(core.vault), RunStore(core.vault),
                                                  "run-x", item["id"], results), caller="test")
    fresh = StagingStore(core.vault).load(item["id"])
    assert fresh["processing"]["coverage"] == "full"
    assert "not_examined" not in fresh["processing"]
