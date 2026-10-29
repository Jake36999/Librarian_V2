"""Measure the share of research grains closed by Tier A in a vault's audited
sessions (HARNESS-06). Reads the session logs only; changes nothing.

    python scripts/tier_a_share.py <vault root>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from resource_librarian.research_grains import tier_a_share
from resource_librarian.vault import Vault


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print(__doc__)
        return 2
    print(json.dumps(tier_a_share(Vault(Path(args[0]))), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
