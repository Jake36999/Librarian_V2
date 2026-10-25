"""ADAPT-06: chat-completions and embeddings URLs are built in one place.

A caller that concatenates its own endpoint path skips the approved
transport boundary (adapters/openai_chat.py); this static check fails the
build when one appears anywhere else in the package.
"""
import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "resource_librarian"
APPROVED = {PACKAGE / "adapters" / "openai_chat.py"}
PATHS = ("/chat/completions", "/embeddings")


def _fragments(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node
    # Docstrings name the endpoints in prose; only path-shaped literals count.


def test_no_endpoint_url_is_built_outside_the_approved_transport():
    offenders = []
    for path in PACKAGE.rglob("*.py"):
        if path in APPROVED:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in _fragments(tree):
            if node.value.rstrip("/").endswith(PATHS):
                offenders.append(f"{path.relative_to(PACKAGE)}:{node.lineno}: {node.value!r}")
    assert not offenders, "build endpoint URLs with adapters.openai_chat: " + "; ".join(offenders)
