"""Path-only credential refusal: secret stores by name, never ordinary code or papers (2026-11-16)."""
import pytest

from resource_librarian.credentials import credential_path


@pytest.mark.parametrize("path", [
    ".env", "config/.env.txt", "keys/id_rsa", "tls/server.pem",
    "archive/_03a1-code_database.sqlite.cursor-secret",       # found in an archived QA folder
    "app/client.secret", "deploy/secrets/token.txt", "secrets.json", "ops/credentials.json", ".netrc",
])
def test_secret_stores_are_refused(path):
    assert credential_path(path)


@pytest.mark.parametrize("path", [
    "src/resource_librarian/credentials.py", "docs/secret-sharing-schemes.pdf",
    "papers/Secret Sharing and Its Applications.pdf", "notes/secretary.md", "tests/test_secrets_rule.py",
])
def test_ordinary_files_that_mention_secrets_are_not(path):
    assert not credential_path(path)
