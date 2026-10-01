"""Actions on the vault's own git repository: the building blocks of
workflows like `sync-vault`. Commands are fixed argument lists built here,
never text from a model (`NO_ARBITRARY_SHELL`), and they act on the vault
alone, never on a project (`OBSERVER_WITHOUT_ACTUATION`)."""
from __future__ import annotations

import fnmatch
import re
import subprocess
from pathlib import Path

from ..registry import Card, Context, tool
from ..rules import Refusal

SECRET_PATTERNS = (".env", ".env.*", "*.pem", "*.key", "*.token", "*.p12", "id_rsa*")
PATTERN = re.compile(r"^[A-Za-z0-9_.*/\-\[\] ]{1,200}$")


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                            timeout=120)
    if check and result.returncode != 0:
        raise RuntimeError(f"git {args[0]}: {(result.stderr or result.stdout).strip()[:400]}")
    return result


def _repo(ctx: Context) -> Path:
    try:
        top = _git(ctx.vault.root, "rev-parse", "--show-toplevel").stdout.strip()
    except (RuntimeError, FileNotFoundError) as exc:
        raise Refusal("VAULT_REQUIRED", f"the vault is not in a git repository: {exc}") from exc
    return Path(top).resolve()


@tool("gitignore_ensure", tier="contribute", effect="vault_write", scope="library", returns=("added", "present"),
      card=Card("Make sure the vault's .gitignore holds these patterns",
                "before committing, so derived files and secrets stay out of history",
                "Adds only what is missing; never adds a `!` exception"))
def gitignore_ensure(ctx: Context, patterns: list[str]) -> dict:
    bad = [p for p in patterns if p.startswith("!") or not PATTERN.match(p)]
    if bad:
        raise TypeError(f"not a plain ignore pattern: {bad} (no `!` exceptions, no newlines)")
    path = ctx.vault.root / ".gitignore"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    present = {ln.strip() for ln in lines}
    added = [p for p in dict.fromkeys(patterns) if p not in present]
    if added:
        text = "\n".join(lines).rstrip("\n")
        path.write_text((text + "\n" if text else "") + "\n".join(added) + "\n",
                        encoding="utf-8")
    return {"added": added, "present": sorted(present & set(patterns))}


@tool("vault_commit", tier="contribute", effect="vault_write", scope="library",
      returns=("committed", "commit", "files"),
      card=Card("Commit every change in the vault", "after a batch of work",
                "Refuses when a file that looks like a secret would be committed"))
def vault_commit(ctx: Context, message: str) -> dict:
    repo = _repo(ctx)
    scope = str(ctx.vault.root)
    message = "".join(c for c in message if c >= " ")[:200].strip() or "librarian: update"
    status = _git(repo, "status", "--porcelain", "--untracked-files=all", "--", scope).stdout
    changed = [line[3:].strip().strip('"') for line in status.splitlines() if line.strip()]
    if not changed:
        return {"committed": False, "commit": "", "files": 0}
    secrets = [c for c in changed if any(fnmatch.fnmatch(Path(c).name, pat)
                                         for pat in SECRET_PATTERNS)]
    if secrets:
        raise Refusal("NO_ARBITRARY_SHELL", f"refusing to commit what looks like a secret: "
                                            f"{secrets[:5]}; add it to .gitignore first")
    _git(repo, "add", "-A", "--", scope)
    _git(repo, "commit", "-m", message, "--", scope)
    sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    return {"committed": True, "commit": sha[:12], "files": len(changed)}


@tool("vault_push", tier="contribute", effect="vault_write", scope="library", open_world=True,
      returns=("pushed", "branch", "remote"),
      card=Card("Push the vault's commits to its remote",
                "after committing, to back the vault up",
                "Outward-facing: a person pushes unless the vault sets vault.agent_push = true"))
def vault_push(ctx: Context) -> dict:
    allowed = bool((ctx.vault.config().get("vault") or {}).get("agent_push"))
    if ctx.tier != "curate" and not allowed:
        raise Refusal("PERSON_CONFIRMS", "pushing publishes the vault's history; a person "
                                         "pushes, unless vault.agent_push = true")
    repo = _repo(ctx)
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    remote = _git(repo, "remote", check=False).stdout.split()
    if not remote:
        raise Refusal("VAULT_REQUIRED", "the vault's repository has no remote to push to")
    _git(repo, "push", "-u", remote[0], branch)
    return {"pushed": True, "branch": branch, "remote": remote[0]}
