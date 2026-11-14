"""Evidence-ranked model recommendations (owner, 2026-11-14).

The picker listed every model whose profile suggests the slot's tier first, in catalogue
order, so the most expensive Tier_1 entries led.  A catalogue entry may now carry a
``recommendation_rank`` (lower first) drawn from recorded evidence - here the 2026-09-29
DeepInfra reliability benchmark, where MiMo-V2.6-Flash and -Pro passed all four probes.
Nothing is selected or bound: ordering only.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from resource_librarian import providers
from resource_librarian.app import App
from resource_librarian.init import init
from resource_librarian.keys import KeyStore
from resource_librarian.providers import Reply
from resource_librarian.vault import Vault

ROOT = Path(__file__).resolve().parents[1]
FLASH, PRO, FABLE = "XiaomiMiMo/MiMo-V2.6-Flash", "XiaomiMiMo/MiMo-V2.6-Pro", "anthropic/claude-fable-5"


def _app(root, listed):
    init(root, name=root.name)
    provider = providers.Scripted(lambda s, m, t: Reply(text="ok"))
    provider.models = lambda: listed
    return App(Vault(root), token="t", keys=KeyStore(use_keyring=False),
               provider_for=lambda choice: provider)


def test_shipped_profiles_carry_the_evidence_rank(tmp_path):
    app = _app(tmp_path / "Lib", [FABLE, PRO, FLASH])
    by_id = {m["id"]: m["profile"] for m in app.models("deepinfra")["models"]}
    assert by_id[FLASH]["recommendation_rank"] == 1
    assert by_id[PRO]["recommendation_rank"] == 2
    assert by_id[FABLE]["recommendation_rank"] is None
    assert app.settings.data.get("tiers") in (None, [])          # nothing was selected


def test_catalogue_ranks_are_unique_positive_integers():
    rows = json.loads((ROOT / "src/resource_librarian/standard/model_catalog/deepinfra.json")
                      .read_text(encoding="utf-8"))
    ranks = [r["fields"]["recommendation_rank"] for r in rows if "recommendation_rank" in r["fields"]]
    assert ranks and all(type(x) is int and x > 0 for x in ranks) and len(ranks) == len(set(ranks))


ESBUILD = ROOT / "ui" / "node_modules" / ".bin" / ("esbuild.cmd" if shutil.which("cmd") else "esbuild")


@pytest.mark.skipif(not shutil.which("node") or not ESBUILD.exists(), reason="needs node and ui esbuild")
def test_picker_orders_recommended_by_rank_then_catalogue_order(tmp_path):
    out = tmp_path / "order.mjs"
    subprocess.run([str(ESBUILD), str(ROOT / "ui/src/model_order.ts"), "--format=esm",
                    f"--outfile={out}"], check=True, capture_output=True, shell=False)
    probe = tmp_path / "probe.mjs"
    probe.write_text(
        f"import {{ orderModels }} from {json.dumps(out.as_uri())};\n"
        "const m = (id, tier, rank) => ({ id, profile: { suggested_tier: tier, recommendation_rank: rank } });\n"
        "const list = [m('fable','Tier_1',null), m('small','Tier_3',null), m('pro','Tier_1',2),\n"
        "  m('opus','Tier_1',undefined), m('flash','Tier_1',1), m('bare', undefined, 7)];\n"
        "console.log(JSON.stringify([orderModels(list, 1).map(x => x.id), orderModels(list, 3).map(x => x.id),\n"
        "  orderModels(list, 0).map(x => x.id)]));\n", encoding="utf-8")
    result = subprocess.run(["node", str(probe)], check=True, capture_output=True, text=True)
    lead, small, none = json.loads(result.stdout)
    assert lead == ["flash", "pro", "fable", "opus", "small", "bare"]     # rank only inside the tier
    assert small == ["small", "fable", "pro", "opus", "flash", "bare"]    # no rank leak across tiers
    assert none == ["fable", "small", "pro", "opus", "flash", "bare"]     # no slot: catalogue order
