"""WS0: compare the runner's embedded rate cards with DeepInfra's live public model listing.

The listing endpoint needs no credential and no request body. Output: data/deepinfra_live_check.json
(tags each card verified / stale / not_listed with the retrieval time).
"""
from __future__ import annotations

import ast
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, REPO, to_iso, write_json  # noqa: E402

URL = "https://api.deepinfra.com/v1/openai/models"


def cards() -> dict:
    tree = ast.parse((REPO / "scripts" / "delegate_deepinfra.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "RATE_CARDS":
            return ast.literal_eval(node.value)
    raise SystemExit("RATE_CARDS not found")


def main() -> int:
    request = urllib.request.Request(URL, headers={"User-Agent": "librarian-sprint-check/1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        body = json.loads(response.read().decode("utf-8"))
    retrieved = to_iso(datetime.now(timezone.utc))
    items = body.get("data", body if isinstance(body, list) else [])
    by_id = {it.get("id"): it for it in items}
    result = {"url": URL, "retrieved_at": retrieved, "listing_count": len(items), "models": {}}
    for model, card in cards().items():
        item = by_id.get(model)
        if item is None:
            result["models"][model] = {"status": "not_listed", "card": card}
            continue
        meta = item.get("metadata") or {}
        pricing = meta.get("pricing") or {}
        live_in = pricing.get("input_tokens")
        live_out = pricing.get("output_tokens")
        ok = None
        if live_in is not None and live_out is not None:
            ok = abs(live_in - card["input_per_1m"]) <= 0.01 * card["input_per_1m"] + 1e-9 and abs(live_out - card["output_per_1m"]) <= 0.01 * card["output_per_1m"] + 1e-9
        result["models"][model] = {
            "status": "verified" if ok else ("stale" if ok is False else "listed_no_pricing"),
            "card_in_out_per_1m": [card["input_per_1m"], card["output_per_1m"]],
            "live_in_out_per_1m": [live_in, live_out], "cache_read_per_1m": pricing.get("cache_read_tokens"),
            "context_length": meta.get("context_length"), "max_tokens": meta.get("max_tokens"),
            "tags": meta.get("tags"), "pricing_keys": sorted(pricing.keys()),
        }
    write_json(DATA / "deepinfra_live_check.json", result)
    print("listing", len(items), "retrieved", retrieved)
    for model, r in result["models"].items():
        print(f"{r['status']:>18}  {model:48} card={r.get('card_in_out_per_1m')} live={r.get('live_in_out_per_1m')} ctx={r.get('context_length')} maxtok={r.get('max_tokens')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
