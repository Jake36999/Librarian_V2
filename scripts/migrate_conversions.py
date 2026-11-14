"""Person-run conversion migration; dry-run by default, never calls a model."""
import argparse
import json
from pathlib import Path

from resource_librarian.conversions import migrate_inventory
from resource_librarian.vault import Vault


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('vault', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    vault = Vault.find(args.vault)
    if vault.root.resolve() != args.vault.resolve():
        parser.error('Name the exact library vault, not a child or code repository')
    print(json.dumps(migrate_inventory(vault, apply=args.apply), indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
