"""The text-to-speech pipeline from the command line, in its two modes (owner, 2026-10-01).

    python scripts/tts_pipeline.py message --vault D:/Libraries/Software --text "Read this aloud."
    python scripts/tts_pipeline.py document --vault D:/Libraries/Software --path "Notes/Study Plan"

Mode A (`message`) reads a piece of text; mode B (`document`) a note in the library. Both go
through `resource_librarian.tts` - the same chunks, cache, prices and $2.00 cap as the app's
speaker buttons - and write one MP3 per chunk plus a playlist (`reading.m3u`) to `--out`.
The DeepInfra key is read in Python from the environment or `.utility/.env`, never printed.
"""
from __future__ import annotations

import argparse
import base64
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".v2" / "src"))
from resource_librarian import tts  # noqa: E402
from resource_librarian.vault import Vault  # noqa: E402


def load_key() -> None:
    if os.environ.get("DEEPINFRA_API_KEY"):
        return
    env = ROOT / ".utility" / ".env"
    for line in env.read_text(encoding="utf-8").splitlines() if env.is_file() else []:
        name, sep, value = line.strip().partition("=")
        if sep and name.strip() == "DEEPINFRA_API_KEY" and value.strip():
            os.environ["DEEPINFRA_API_KEY"] = value.strip().strip('"').strip("'")
            return


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("mode", choices=("message", "document"))
    ap.add_argument("--vault", required=True)
    ap.add_argument("--text", default="")
    ap.add_argument("--path", default="", help="a note in the library, e.g. Notes/Plan")
    ap.add_argument("--out", default="tts-out")
    args = ap.parse_args()
    vault = Vault(Path(args.vault))
    if args.mode == "message":
        text = args.text
    else:
        rel = args.path if args.path.lower().endswith(".md") else f"{args.path}.md"
        text = (vault.root / rel).read_text(encoding="utf-8")
    planned = tts.plan(text, tts.choice(vault).get("model", ""))
    print(f"{len(planned['chunks'])} chunk(s), {planned['chars']} characters, at most "
          f"${planned['estimate_usd']} - spent so far ${planned['spent_usd']:.4f} of "
          f"${planned['cap_usd']:.2f}")
    load_key()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    names = []
    for i, part in enumerate(planned["chunks"], 1):
        try:
            said = tts.speak(vault, part, args.mode)
        except tts.TtsError as exc:
            print(f"stopped at chunk {i}: {exc}")
            break
        name = f"{i:03d}.mp3"
        (out / name).write_bytes(base64.b64decode(said["audio"].split(",", 1)[1]))
        names.append(name)
        print(f"  {name}: ${said['cost_usd']:.6f}{' (cached)' if said['cached'] else ''}")
    (out / "reading.m3u").write_text("\n".join(names) + "\n", encoding="utf-8")
    print(f"wrote {len(names)} file(s) and reading.m3u to {out}")


if __name__ == "__main__":
    main()
