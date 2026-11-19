#!/usr/bin/env python
"""Area F stress test: Backend API security & boundaries, path traversal, Windows reserved names,
symlinks, Origin/Host/Token checks, oversized bodies, init/adopt/attach awkward folders,
Tool Reference / Rules / Skill Registry injection, NOT_CHAT_* regex audit against shipped models,
stale lease & permission timeout recovery.
"""
from __future__ import annotations

import http.client
import json
import os
import re
import shutil
import sys
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Any

ROOT = Path(r"D:\Librarian_V2")
sys.path.insert(0, str(ROOT / "src"))
for key in ("TAVILY_API_KEY", "BRAVE_API_KEY", "APIFY_TOKEN", "DEEPINFRA_API_KEY",
            "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"):
    os.environ.pop(key, None)

SCRATCH = Path(r"C:\Users\jakem\.gemini\antigravity\brain\3960e172-6f69-4375-a20c-32da8ab417ab\scratch\librarian-stress-20261119\area_f")
if SCRATCH.exists():
    shutil.rmtree(SCRATCH, ignore_errors=True)
SCRATCH.mkdir(parents=True, exist_ok=True)
os.environ["LIBRARIAN_CONFIG_DIR"] = str(SCRATCH / "config")

from http.server import ThreadingHTTPServer
from resource_librarian import content_roots, reference, rules, skill_registry, tools  # noqa: F401
from resource_librarian.app import App, make_handler
from resource_librarian.broker import Broker
from resource_librarian.init import init
from resource_librarian.keys import KeyStore
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.rules import Refusal
from resource_librarian.session import SessionStore
from resource_librarian.vault import Vault


def http_req(port: int, method: str, path: str, headers: dict[str, str] | None = None,
             body: bytes | None = None) -> tuple[int, str, dict[str, str]]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request(method, path, body=body, headers=headers or {})
        resp = conn.getresponse()
        hdrs = {k.lower(): v for k, v in resp.getheaders()}
        data = resp.read().decode("utf-8", errors="replace")
        return resp.status, data[:300], hdrs
    except Exception as exc:
        return -1, f"CONN_ERROR:{type(exc).__name__}: {exc}", {}
    finally:
        conn.close()


def test_api_security_and_boundaries():
    vroot = SCRATCH / "api_vault"
    init(vroot, name="API Stress")
    v = Vault(vroot)
    # Create an outside secret file to verify traversal cannot read it
    outside = SCRATCH / "secret_outside.txt"
    outside.write_text("TOP_SECRET_OUTSIDE_VAULT_CONTENT", encoding="utf-8")

    # Create a note named "..." and weird unicode names if OS allows
    weird_dir = vroot / "Notes"
    weird_dir.mkdir(exist_ok=True)
    for fname in ("café_日本語.md", "has]]hash#tick`note.md"):
        (weird_dir / fname).write_text(f"# {fname}\nBody\n", encoding="utf-8")
    # Try symlink pointing outside vault
    symlink_created = False
    try:
        os.symlink(str(outside), str(weird_dir / "escape_link.md"))
        symlink_created = True
    except OSError as exc:
        symlink_err = str(exc)
    else:
        symlink_err = ""

    app = App(v, coordinate=True, keys=KeyStore(use_keyring=False), broker_timeout=2)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    port = server.server_address[1]
    token = app.token
    th = threading.Thread(target=server.serve_forever, daemon=True)
    th.start()
    report: dict[str, Any] = {"port": port, "symlink_created": symlink_created, "symlink_err": symlink_err}
    try:
        auth = {"X-Librarian-Token": token}
        # 1. Missing / wrong token across key GET & POST routes
        token_checks = {}
        for method, path in [
            ("GET", "/api/state"),
            ("GET", "/api/skills"),
            ("GET", "/api/meta"),
            ("GET", "/api/file?path=About/Rules.md"),
            ("GET", "/api/files?dir="),
            ("GET", "/api/checkpoints?pending=1"),
            ("POST", "/api/mode"),
            ("POST", "/api/actions"),
            ("POST", "/api/attach?name=x.txt"),
            ("POST", "/api/tool/search"),
            ("POST", "/api/mcp/call"),
            ("POST", "/api/host/stop"),
        ]:
            body = b"{}" if method == "POST" else None
            st_no, d_no, _ = http_req(port, method, path, {"Content-Type": "application/json"}, body)
            st_bad, d_bad, _ = http_req(port, method, path, {"X-Librarian-Token": "wrong-token", "Content-Type": "application/json"}, body)
            token_checks[f"{method} {path}"] = {"no_token": st_no, "wrong_token": st_bad}
        report["token_checks"] = token_checks

        # 2. Wrong Origin & DNS-rebinding Host header checks (GET, POST, OPTIONS)
        origin_host = {}
        for label, method, path, hdrs, body in [
            ("evil_origin_get", "GET", "/api/state", {**auth, "Origin": "https://evil.example"}, None),
            ("evil_origin_options", "OPTIONS", "/api/state", {"Origin": "https://evil.example"}, None),
            ("evil_origin_post", "POST", "/api/mode", {**auth, "Origin": "https://evil.example", "Content-Type": "application/json"}, b'{"mode":"ask"}'),
            ("prefix_spoof_origin_post", "POST", "/api/mode", {**auth, "Origin": "http://127.0.0.1.evil.com", "Content-Type": "application/json"}, b'{"mode":"ask"}'),
            ("null_origin_post", "POST", "/api/mode", {**auth, "Origin": "null", "Content-Type": "application/json"}, b'{"mode":"ask"}'),
            ("wrong_host_get", "GET", "/api/state", {**auth, "Host": "evil.example:80"}, None),
            ("wrong_host_post", "POST", "/api/mode", {**auth, "Host": "evil.example:80", "Content-Type": "application/json"}, b'{"mode":"ask"}'),
            ("valid_loopback_origin_post", "POST", "/api/mode", {**auth, "Origin": f"http://127.0.0.1:{port}", "Content-Type": "application/json"}, b'{"mode":"ask"}'),
        ]:
            st, data, rh = http_req(port, method, path, hdrs, body)
            origin_host[label] = {
                "status": st, "acao": rh.get("access-control-allow-origin"), "body": data[:120],
            }
        report["origin_and_host"] = origin_host

        # 3. Oversized body (>MAX_BODY) & malformed JSON
        big_body = b'{"x":"' + (b'A' * (12 * 1024 * 1024)) + b'"}'
        st_big, d_big, _ = http_req(port, "POST", "/api/mode", {**auth, "Content-Type": "application/json"}, big_body)
        st_badjson, d_badjson, _ = http_req(port, "POST", "/api/mode", {**auth, "Content-Type": "application/json"}, b"{not json")
        report["body_limits"] = {
            "12mb_mode_post": {"status": st_big, "body": d_big[:140]},
            "malformed_json": {"status": st_badjson, "body": d_badjson[:140]},
        }

        # 4. Path traversal on /api/file?path= and /api/files?dir=
        trav = {}
        for p in [
            "../secret_outside.txt",
            "..\\secret_outside.txt",
            "Notes/../../secret_outside.txt",
            str(outside),
            "C:/Windows/win.ini",
            ".librarian/config.toml",
            ".librarian/checkpoints.json",
            "Notes/escape_link.md",
            "escape_link",
            "...",
            "Notes/...",
            "CON.md",
            "NUL",
            "Notes/has]]hash#tick`note.md",
            "Notes/café_日本語.md",
        ]:
            q = urllib.parse.quote(p, safe="")
            st_f, d_f, _ = http_req(port, "GET", f"/api/file?path={q}", auth)
            st_d, d_d, _ = http_req(port, "GET", f"/api/files?dir={q}", auth)
            trav[p] = {
                "file_status": st_f, "leaked_outside": "TOP_SECRET_OUTSIDE_VAULT_CONTENT" in d_f,
                "file_preview": d_f[:100],
                "dir_status": st_d, "dir_preview": d_d[:100],
            }
        report["path_traversal"] = trav

        # 5. /api/attach raw bytes with ?name=<fname>&dir=<dir>: traversal, reserved Windows names, Unicode, dots, long names
        attach_res = {}
        raw_payload = b"hello attachment bytes"
        for fname, folder in [
            ("../escaped.txt", "Inbox"),
            ("..\\escaped2.txt", "Inbox"),
            ("C:\\Temp\\abs.txt", "Inbox"),
            ("ok.txt", "../outside_dir"),
            ("ok.txt", ".librarian"),
            ("CON", "Inbox"),
            ("CON.txt", "Inbox"),
            ("NUL.md", "Inbox"),
            ("AUX.pdf", "Inbox"),
            ("PRN.txt", "Inbox"),
            ("...", "Inbox"),
            ("..", "Inbox"),
            (".hidden", "Inbox"),
            ("café_日本語.txt", "Inbox"),
            ("bad]]pipe|hash#tick`file.md", "Inbox"),
            ("a" * 300 + ".txt", "Inbox"),
        ]:
            qn = urllib.parse.quote(fname, safe="")
            qd = urllib.parse.quote(folder, safe="")
            st, data, _ = http_req(
                port, "POST", f"/api/attach?name={qn}&dir={qd}",
                {**auth, "Content-Type": "application/octet-stream"}, raw_payload,
            )
            key = f"{folder}/{fname[:35]}"
            attach_res[key] = {"status": st, "body": data[:160]}
        report["attach_filenames"] = attach_res
        report["escaped_files_created"] = {
            "escaped.txt": (SCRATCH / "escaped.txt").exists(),
            "escaped2.txt": (SCRATCH / "escaped2.txt").exists(),
            "outside_dir": (SCRATCH / "outside_dir").exists(),
            "inbox_files": sorted(p.name for p in (vroot / "Inbox").iterdir()) if (vroot / "Inbox").exists() else [],
        }

        # 6. Skill registry injection & edge cases
        adv_servers = [
            {"name": "evil` | on | 99 | <img src=x onerror=alert(1)>", "enabled": True,
             "tool_names": ["a"], "docs": "javascript:alert(1)"},
            {"name": "data-srv", "enabled": True, "tool_names": ["b"],
             "docs": "data:text/html,<script>alert(1)</script>"},
            {"name": "md-inject", "enabled": True, "tool_names": [],
             "docs": "https://ok.example> [CLICK ME](https://phish.example) | [[About/Rules]]\n\n## Injected Heading"},
            {"name": "long-srv-" + ("x" * 300), "enabled": False, "tool_names": [],
             "docs": "https://example.com/" + ("a" * 500)},
        ]
        md_rendered = skill_registry.render_markdown(adv_servers)
        report["skill_registry_injection"] = {
            "contains_raw_newline_injected_heading": "\n## Injected Heading" in md_rendered,
            "contains_unescaped_pipe_break": "| `evil` | on | 99 |" in md_rendered,
            "contains_raw_markdown_link": "[CLICK ME](https://phish.example)" in md_rendered,
            "contains_angle_brackets_around_url": "<https://ok.example>" in md_rendered or "<javascript:alert(1)>" in md_rendered,
            "snippet": md_rendered[md_rendered.find("## Installed servers"):][:900],
        }
        # Also live /api/skills when mcp is absent or failing
        st_sk, d_sk, _ = http_req(port, "GET", "/api/skills", auth)
        report["live_api_skills_no_mcp_or_empty"] = {"status": st_sk, "len": len(d_sk)}

        # 7. SSE reconnect + stale lease check
        st_sse_bad, d_sse_bad, _ = http_req(port, "GET", "/api/events?since=-1", auth)
        st_sse_nan, d_sse_nan, _ = http_req(port, "GET", "/api/events?since=abc", auth)
        report["sse_param_validation"] = {
            "since_neg1": {"status": st_sse_bad, "body": d_sse_bad[:120]},
            "since_abc": {"status": st_sse_nan, "body": d_sse_nan[:120]},
        }

    finally:
        server.shutdown()
        server.server_close()
        app.close_runtime()
    return report


def test_init_adopt_and_tool_ref():
    out: dict[str, Any] = {}
    # 1. init into folder that ALREADY has files + pre-existing guide note!
    pre = SCRATCH / "init_existing"
    pre.mkdir(parents=True, exist_ok=True)
    (pre / "MyExistingNote.md").write_text("# Keep me\nDo not overwrite.\n", encoding="utf-8")
    (pre / "About the Librarian and how to use it.md").write_text("# Custom user guide\nKeep custom.\n", encoding="utf-8")
    r_init = init(pre, name="PreExisting")
    out["init_existing_folder"] = {
        "existing_note_preserved": (pre / "MyExistingNote.md").read_text(encoding="utf-8").startswith("# Keep me"),
        "existing_guide_preserved": "Custom user guide" in (pre / "About the Librarian and how to use it.md").read_text(encoding="utf-8"),
        "tool_ref_created": (pre / "About" / "Tool Reference.md").exists(),
        "rules_created": (pre / "About" / "Rules.md").exists(),
    }

    # 2. adopt & attach into existing folders: do adopt/attach create the guide & Tool Reference?
    ad = SCRATCH / "adopt_existing"
    ad.mkdir(parents=True, exist_ok=True)
    (ad / "ExistingResearch.md").write_text("# Research\nNotes.\n", encoding="utf-8")
    plan_ad = content_roots.plan_adopt(ad, name="AdoptedVault")
    r_adopt = content_roots.apply_adopt(ad, plan_ad["survey_fingerprint"], name="AdoptedVault")
    # Also attach a read-only folder to AdoptedVault
    att_dir = SCRATCH / "attached_src"
    att_dir.mkdir(parents=True, exist_ok=True)
    (att_dir / "Paper.md").write_text("# Paper\nContent.\n", encoding="utf-8")
    ad_vault = Vault(ad)
    plan_att = content_roots.plan_attach(ad_vault, att_dir)
    r_attach = content_roots.apply_attach(ad_vault, att_dir, plan_att["survey_fingerprint"])
    out["adopt_and_attach"] = {
        "adopt_has_guide": (ad / "About the Librarian and how to use it.md").exists(),
        "adopt_has_tool_ref": (ad / "About" / "Tool Reference.md").exists(),
        "adopt_has_rules": (ad / "About" / "Rules.md").exists(),
        "adopt_files_in_root": sorted(p.name for p in ad.iterdir()),
        "adopt_files_in_about": sorted(p.name for p in (ad / "About").iterdir()) if (ad / "About").exists() else [],
        "attach_has_guide_inside_attached": (att_dir / "About the Librarian and how to use it.md").exists(),
        "attach_applied": bool(r_attach),
    }

    # 3. Tool Reference & Rules markdown escaping check
    tr_md = reference.render_markdown()
    rl_md = rules.render_markdown()
    out["generated_reference_checks"] = {
        "tool_ref_len": len(tr_md),
        "tool_ref_raw_wikilinks": re.findall(r"(?<!\\)\[\[[^\]]+\]\]", tr_md),
        "rules_len": len(rl_md),
        "all_tools_in_ref": sum(1 for n in REGISTRY.names() if f"`{n}`" in tr_md),
        "total_registered_tools": len(REGISTRY.names()),
    }
    return out


def test_not_chat_regex_audit():
    """Test NOT_CHAT_MODALITY & NOT_CHAT_NAME from ui/src/panels.ts against the real DeepInfra
    model catalog AND adversarial edge-case model names."""
    not_chat_modality = re.compile(
        r"Embedding|Speech|Audio|Text_To_Image|Text_To_Video|Image_To_Image|Image_To_Video|Video", re.I
    )
    not_chat_name = re.compile(
        r"(^|\/)(bge|embed|e5-|gte-|nomic|minilm|mpnet|jina|arctic)|bria\/|pixverse|lightricks|"
        r"seedream|seedance|[-_\/](t2v|i2v|t2i)([-_.\/]|$)|image-max|p-image|p-video|asr|whisper|"
        r"voxtral|transcrib|tts|kokoro|chatterbox|orpheus|higgs", re.I
    )

    cat_path = ROOT / "src/resource_librarian/standard/model_catalog/deepinfra.json"
    cat = json.loads(cat_path.read_text(encoding="utf-8"))
    models = cat.get("models") if isinstance(cat, dict) else cat
    hidden_from_catalog = []
    leaked_non_chat_in_catalog = []
    for m in models:
        mid = str(m.get("id") or m.get("model") or m.get("name") or "")
        mod = str(m.get("modality") or "")
        is_chat = (not not_chat_modality.search(mod)) if mod else (not not_chat_name.search(mid))
        if not is_chat and mod in ("Text_Generation", "Image_To_Text"):
            hidden_from_catalog.append({"id": mid, "modality": mod})
        if is_chat and (mod not in ("", "Text_Generation", "Image_To_Text") or
                        re.search(r"flux|sdxl|diffusion|rerank|imagen|recraft|ideogram|dall-e|moderation|guard|clip|sam", mid, re.I)):
            leaked_non_chat_in_catalog.append({"id": mid, "modality": mod})

    # Also test synthetic unprofiled model names (no profile.modality -> falls back to NOT_CHAT_NAME!)
    synthetic_legit_chat = [
        "Snowflake/arctic-instruct",
        "bosonai/higgs-llama-3-70b",
        "org/watts-llm-7b",
        "org/potts-chat-8b",
        "org/gasr-chat-7b",
        "mistralai/Voxtral-Small-24B-2507",
        "nvidia/Llama-3.1-Nemotron-70B-Instruct",
        "Qwen/Qwen3-32B",
    ]
    synthetic_non_chat = [
        "black-forest-labs/FLUX-1-schnell",
        "black-forest-labs/FLUX-1.1-pro",
        "stabilityai/sdxl-turbo",
        "Qwen/Qwen3-Reranker-8B",
        "Qwen/Qwen3-Embedding-8B",
        "ByteDance/SDXL-Lightning",
        "meta-llama/Llama-Guard-4-12B",
        "google/imagen-3",
    ]
    false_positives_unprofiled = [m for m in synthetic_legit_chat if not_chat_name.search(m)]
    false_negatives_unprofiled = [m for m in synthetic_non_chat if not not_chat_name.search(m)]

    return {
        "catalog_count": len(models),
        "catalog_false_positives_hidden": hidden_from_catalog,
        "catalog_potential_leaks": leaked_non_chat_in_catalog,
        "unprofiled_legit_chat_hidden_by_NOT_CHAT_NAME": false_positives_unprofiled,
        "unprofiled_non_chat_leaking_past_NOT_CHAT_NAME": false_negatives_unprofiled,
    }


def test_permission_timeout_parks_session():
    vroot = SCRATCH / "timeout_vault"
    init(vroot, name="Timeout Test")
    v = Vault(vroot)
    sid = REGISTRY.call("open_session", {"purpose": "explore", "question": "Timeout test"},
                        Context(tier="curate", vault=v, extras={}))["opened"]
    b = Broker(mode="ask", timeout=0.15)
    ctx = Context(tier="contribute", vault=v, session=sid, extras={"broker": b})
    try:
        b.check(REGISTRY.get("write_note"), {"folder": "Notes", "name": "x", "body": "y"}, ctx)
        outcome = "unexpectedly_allowed"
    except Refusal as r:
        outcome = r.code
    s = SessionStore(v).load(sid)
    return {"refusal_code": outcome, "session_status_after_timeout": s.status}


def main():
    out = {
        "api_security_and_boundaries": test_api_security_and_boundaries(),
        "init_adopt_and_tool_ref": test_init_adopt_and_tool_ref(),
        "not_chat_regex_audit": test_not_chat_regex_audit(),
        "permission_timeout": test_permission_timeout_parks_session(),
    }
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
