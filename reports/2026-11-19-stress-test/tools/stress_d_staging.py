#!/usr/bin/env python
"""Area D stress test: Staging pager (0, 1, 50, 51, 500), status filters, stale revisions
(Draft then Accept, two tabs, external edit), Clerk refusal reasons (route unqualified,
key missing, host disabled, endpoint changed), Folders (Waiting/Accepted/re-survey/accept-policy),
Batch (interrupt, resume, cancel, failing stage, no text layer, extensionless file, 200 items).
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(r"D:\Librarian_V2")
sys.path.insert(0, str(ROOT / "src"))
for key in ("TAVILY_API_KEY", "BRAVE_API_KEY", "APIFY_TOKEN", "DEEPINFRA_API_KEY",
            "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"):
    os.environ.pop(key, None)

SCRATCH = Path(r"C:\Users\jakem\.gemini\antigravity\brain\3960e172-6f69-4375-a20c-32da8ab417ab\scratch\librarian-stress-20261119\area_d")
if SCRATCH.exists():
    shutil.rmtree(SCRATCH, ignore_errors=True)
SCRATCH.mkdir(parents=True, exist_ok=True)
os.environ["LIBRARIAN_CONFIG_DIR"] = str(SCRATCH / "config")

from resource_librarian import batch, clerk, folder_review, staging, tools  # noqa: F401
from resource_librarian.app import App
from resource_librarian.init import init
from resource_librarian.keys import KeyStore
from resource_librarian.registry import Context
from resource_librarian.role_routes import RoleRouteBinding
from resource_librarian.staging import StagingStore
from resource_librarian.vault import Vault


def bind_clerk(app: App, host_id: str, model_id: str, *, protocol: str = "", fingerprint: str = "") -> None:
    host = app.hosts.get(host_id)
    rows = dict(app.role_routes.raw())
    rows["clerk"] = RoleRouteBinding(
        role="clerk",
        host_id=host_id,
        model_id=model_id,
        protocol=protocol or host.protocol,
        endpoint_fingerprint=fingerprint or host.endpoint_fingerprint,
        source="explicit",
    )
    app.role_routes.save(rows)


def make_app(name: str) -> tuple[Vault, App]:
    root = SCRATCH / name
    init(root, name=name)
    v = Vault(root)
    app = App(v, coordinate=True, keys=KeyStore(use_keyring=False), broker_timeout=5)
    return v, app


def test_staging_pager_and_filters():
    results = {}
    for count in (0, 1, 50, 51, 500):
        v, app = make_app(f"pager_{count}")
        try:
            store = StagingStore(v)
            for i in range(count):
                store.add({
                    "id": f"item-{i:04d}", "kind": "source", "name": f"Source {i:04d}",
                    "status": "staged", "source_kind": "document",
                    "evidence_text": f"Text {i}",
                })
            page1 = app.person_call("staging_list", {"kind": "source", "status": "staged", "limit": 50})
            page_more = app.person_call("staging_list", {"kind": "source", "status": "staged", "limit": 100})
            page_all = app.person_call("staging_list", {"kind": "source", "status": "staged", "limit": 600})
            results[str(count)] = {
                "limit50_len": len(page1.get("items") or []),
                "limit50_total": page1.get("total"),
                "limit100_len": len(page_more.get("items") or []),
                "limit600_len": len(page_all.get("items") or []),
                "limit600_total": page_all.get("total"),
                "counts_source_staged": (page1.get("counts") or {}).get("source", {}).get("staged"),
            }
        finally:
            app.close_runtime()
    return results


def test_stale_revisions_and_clerk_reasons():
    out: dict[str, Any] = {}

    # 1. Draft (queued) -> Accept with old staged_revision vs refreshed staged_revision
    v, app = make_app("stale_rev")
    try:
        store = StagingStore(v)
        store.add({
            "id": "src-stale-1", "kind": "source", "name": "Stale Check Note",
            "status": "staged", "source_kind": "document",
            "evidence_text": "This document explains how SQLite write-ahead logging works in detail.",
        })
        before = app.person_call("staging_show", {"item_id": "src-stale-1"})
        old_rev = before.get("staged_revision")
        rev_out = app.person_call("staging_review", {"item_id": "src-stale-1"})
        after = app.person_call("staging_show", {"item_id": "src-stale-1"})
        new_rev = after.get("staged_revision")

        # Try accepting with OLD revision (simulating two tabs / stale client!)
        stale_dec = app.person_call("staging_decide", {
            "item_ids": ["src-stale-1"], "decision": "approve",
            "staged_revision": old_rev,
        })
        # Now with NEW revision (what reloaded UI sends!)
        fresh_dec = app.person_call("staging_decide", {
            "item_ids": ["src-stale-1"], "decision": "approve",
            "staged_revision": new_rev,
        })
        # External edit on disk (actual staged source file path is .librarian/staging/source/<id>.json)
        store.add({
            "id": "src-ext-1", "kind": "source", "name": "External Edit Note",
            "status": "staged", "source_kind": "document", "evidence_text": "Initial text",
        })
        ext_before = app.person_call("staging_show", {"item_id": "src-ext-1"})
        ext_rev = ext_before.get("staged_revision")
        p = v.librarian / "staging" / "source" / "src-ext-1.json"
        ext_file_found = p.exists()
        if ext_file_found:
            raw = json.loads(p.read_text(encoding="utf-8"))
            raw["evidence_text"] = "Modified externally on disk!"
            p.write_text(json.dumps(raw), encoding="utf-8")
        ext_dec = app.person_call("staging_decide", {
            "item_ids": ["src-ext-1"], "decision": "approve",
            "staged_revision": ext_rev,
        })
        out["stale_revisions"] = {
            "old_rev": old_rev, "new_rev": new_rev, "rev_changed_on_queued_draft": old_rev != new_rev,
            "queued_draft_status": (rev_out.get("draft") or {}).get("status"),
            "queued_draft_reason": (rev_out.get("draft") or {}).get("reason"),
            "stale_tab_decision": stale_dec,
            "fresh_reloaded_decision": fresh_dec,
            "external_disk_file_found": ext_file_found,
            "external_disk_edit_decision": ext_dec,
        }
    finally:
        app.close_runtime()

    # 2. Clerk refusal reason text for EVERY failure kind!
    clerk_cases = {}
    # Case A: No clerk model assigned
    vA, appA = make_app("clerk_none")
    try:
        StagingStore(vA).add({"id": "c1", "kind": "source", "name": "C1", "status": "staged", "evidence_text": "Hello world test."})
        r = appA.person_call("staging_review", {"item_id": "c1"})
        clerk_cases["no_model_configured"] = r.get("draft")
    finally:
        appA.close_runtime()

    # Case B: Key missing (assign deepinfra model with no API key)
    vB, appB = make_app("clerk_nokey")
    try:
        bind_clerk(appB, "preset-deepinfra", "Qwen/Qwen3-32B")
        StagingStore(vB).add({"id": "c2", "kind": "source", "name": "C2", "status": "staged", "evidence_text": "Hello world test."})
        r = appB.person_call("staging_review", {"item_id": "c2"})
        clerk_cases["key_missing"] = r.get("draft")
    finally:
        appB.close_runtime()

    # Case C: Host disabled (Note: HostRegistry is shared via LIBRARIAN_CONFIG_DIR! Re-enable after test!)
    vC, appC = make_app("clerk_disabled_host")
    try:
        bind_clerk(appC, "preset-deepinfra", "Qwen/Qwen3-32B")
        appC.hosts.update_controls({"host_id": "preset-deepinfra", "enabled": False})
        StagingStore(vC).add({"id": "c3", "kind": "source", "name": "C3", "status": "staged", "evidence_text": "Hello world test."})
        r = appC.person_call("staging_review", {"item_id": "c3"})
        clerk_cases["host_disabled"] = r.get("draft")
    finally:
        appC.hosts.update_controls({"host_id": "preset-deepinfra", "enabled": True})
        appC.close_runtime()

    # Case D: Host endpoint fingerprint changed
    vD, appD = make_app("clerk_endpoint_changed")
    try:
        bind_clerk(appD, "preset-deepinfra", "Qwen/Qwen3-32B", fingerprint="stale-fingerprint-0000")
        StagingStore(vD).add({"id": "c4", "kind": "source", "name": "C4", "status": "staged", "evidence_text": "Hello world test."})
        r = appD.person_call("staging_review", {"item_id": "c4"})
        clerk_cases["endpoint_changed"] = r.get("draft")
    finally:
        appD.close_runtime()

    # Case E: Route unqualified (key IS present via env var, host enabled, fingerprint matches, model is experimental)
    vE, appE = make_app("clerk_unqualified")
    prev_di = os.environ.get("DEEPINFRA_API_KEY")
    os.environ["DEEPINFRA_API_KEY"] = "sk-dummy-not-called-because-gate-refuses-first"
    try:
        bind_clerk(appE, "preset-deepinfra", "Qwen/Qwen3-32B")
        StagingStore(vE).add({"id": "c5", "kind": "source", "name": "C5", "status": "staged", "evidence_text": "Hello world test."})
        r = appE.person_call("staging_review", {"item_id": "c5"})
        clerk_cases["route_unqualified"] = r.get("draft")
    finally:
        if prev_di is None:
            os.environ.pop("DEEPINFRA_API_KEY", None)
        else:
            os.environ["DEEPINFRA_API_KEY"] = prev_di
        appE.close_runtime()

    out["clerk_refusal_reasons"] = clerk_cases
    return out


def test_folder_review_filters():
    """Test Folders Waiting vs Accepted filter after survey, accept, re-survey, and accept-policy."""
    v, app = make_app("folders_filter")
    try:
        src_root = SCRATCH / "folder_survey_root"
        (src_root / "alpha_refs").mkdir(parents=True, exist_ok=True)
        (src_root / "alpha_refs" / "guide.md").write_text("# Guide\nReference documentation.\n", encoding="utf-8")
        (src_root / "beta_notes").mkdir(parents=True, exist_ok=True)
        (src_root / "beta_notes" / "notes.md").write_text("# Notes\nMore notes.\n", encoding="utf-8")

        app.survey_folders(str(src_root))
        ov1 = app.folders()
        cards1 = ov1.get("cards") or ov1.get("folders") or []
        by_name1 = {c.get("name"): {"id": c.get("id"), "status": c.get("status"), "fp": c.get("folder_fingerprint")} for c in cards1}

        # Accept alpha_refs
        alpha = next((c for c in cards1 if c.get("name") == "alpha_refs"), None)
        accept_out = None
        if alpha:
            accept_out = app.accept_folder({
                "id": alpha["id"], "folder_fingerprint": alpha["folder_fingerprint"],
                "purpose": "reference", "graph": "",
            })
        ov2 = app.folders()
        cards2 = ov2.get("cards") or ov2.get("folders") or []
        by_name2 = {c.get("name"): {"status": c.get("status"), "decision_by": (c.get("decision") or {}).get("by")} for c in cards2}

        # Re-survey after adding a new file in alpha_refs
        (src_root / "alpha_refs" / "extra.md").write_text("# Extra\nAdded later.\n", encoding="utf-8")
        app.survey_folders(str(src_root))
        ov3 = app.folders()
        cards3 = ov3.get("cards") or ov3.get("folders") or []
        by_name3 = {c.get("name"): {"status": c.get("status"), "stale": c.get("stale")} for c in cards3}

        # Try accept-policy under default promotion.mode=person (must refuse 409!)
        policy_person_err = None
        try:
            app.accept_folders_by_policy({"root": str(src_root)})
        except Exception as exc:
            policy_person_err = f"{type(exc).__name__}: {exc}"

        return {
            "ov1_keys": sorted(ov1.keys()),
            "after_survey": by_name1,
            "accept_alpha_ok": bool(accept_out and not accept_out.get("error")),
            "after_accept_alpha": by_name2,
            "after_resurvey": by_name3,
            "accept_policy_under_person_mode": policy_person_err,
        }
    finally:
        app.close_runtime()


def test_batch_edge_cases():
    """Batch: no-text-layer PDF, extensionless file, cancel mid-batch, failing stage, 200 items."""
    v, app = make_app("batch_edges")
    report: dict[str, Any] = {}
    try:
        store = StagingStore(v)
        files_dir = v.root / "Inbox"
        files_dir.mkdir(parents=True, exist_ok=True)

        # 1. Extensionless file
        extless = files_dir / "README_NO_EXT"
        extless.write_text("Plain text with no file extension at all.\n", encoding="utf-8")
        store.add({
            "id": "b-extless", "kind": "source", "name": "Extensionless Doc",
            "status": "approved", "source_kind": "document",
            "file": str(extless), "evidence_text": "",
            "intake": {"stages": {"capture": "complete", "fetch": "complete"}},
        })

        # 2. Blank/no-text-layer PDF (minimal valid 1-page PDF with no text)
        blank_pdf = files_dir / "scan_no_text.pdf"
        blank_pdf.write_bytes(
            b"%PDF-1.4\n1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
            b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n"
            b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>endobj\n"
            b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n"
            b"trailer<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF\n"
        )
        store.add({
            "id": "b-notextpdf", "kind": "source", "name": "Blank Scanned PDF",
            "status": "approved", "source_kind": "document",
            "file": str(blank_pdf), "evidence_text": "",
            "intake": {"stages": {"capture": "complete", "fetch": "complete"}},
        })

        # 3. Missing file (failing stage)
        store.add({
            "id": "b-missing", "kind": "source", "name": "Missing File Doc",
            "status": "approved", "source_kind": "document",
            "file": str(files_dir / "does_not_exist.pdf"), "evidence_text": "",
            "intake": {"stages": {"capture": "complete", "fetch": "complete"}},
        })

        res = app.person_call("process_approved", {"background": False})
        items_after = {i["id"]: {"status": i.get("status"), "failure": i.get("failure"),
                                 "processing": i.get("processing")}
                       for i in store.items(kind="source")}
        report["edge_items_batch"] = {"run_out": res, "items": items_after}

        if "--fast" not in sys.argv:
            # 4. 200-item batch + cancel/resume check
            v200, app200 = make_app("batch_200")
            try:
                st200 = StagingStore(v200)
                d200 = SCRATCH / "files_200"
                d200.mkdir(parents=True, exist_ok=True)
                for i in range(200):
                    p = d200 / f"doc_{i:03d}.md"
                    p.write_text(f"# Doc {i}\nBody content for document {i}.\n", encoding="utf-8")
                    st200.add({
                        "id": f"m-{i:03d}", "kind": "source", "name": f"Doc {i:03d}",
                        "status": "approved", "source_kind": "document",
                        "file": str(p), "clean_file": str(p),
                        "evidence_text": f"Body content for document {i}.",
                        "intake": {"stages": {"capture": "complete", "fetch": "complete"}},
                    })
                t0 = time.monotonic()
                started = app200.person_call("process_approved", {"background": True})
                time.sleep(0.25)
                cancel_res = app200.person_call("batch_cancel", {})
                deadline = time.monotonic() + 15
                st_poll = {}
                while time.monotonic() < deadline:
                    st_poll = app200.person_call("batch_status", {})
                    if st_poll.get("status") != "running":
                        break
                    time.sleep(0.1)
                # Now resume it to completion!
                resume_res = app200.person_call("process_approved", {"resume": started.get("run", ""), "background": False})
                final_poll = app200.person_call("batch_status", {})
                counts = {}
                for it in st200.items(kind="source"):
                    counts[it.get("status")] = counts.get(it.get("status"), 0) + 1
                report["batch_200_cancel_resume"] = {
                    "started": started, "cancel_res": cancel_res,
                    "after_cancel_status": {k: st_poll.get(k) for k in ("status", "processed", "total", "waiting", "run")},
                    "resume_res": {k: resume_res.get(k) for k in ("status", "processed", "total", "run", "error", "refused")} if isinstance(resume_res, dict) else resume_res,
                    "final_status": {k: final_poll.get(k) for k in ("status", "processed", "total", "waiting", "waiting_on_model")},
                    "final_item_counts": counts,
                    "elapsed_s": round(time.monotonic() - t0, 2),
                }
            finally:
                app200.close_runtime()
    finally:
        app.close_runtime()
    return report


def main():
    out = {
        "pager_and_filters": test_staging_pager_and_filters(),
        "stale_revisions_and_clerk": test_stale_revisions_and_clerk_reasons(),
        "folder_review_filters": test_folder_review_filters(),
        "batch_edges": test_batch_edge_cases(),
    }
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
