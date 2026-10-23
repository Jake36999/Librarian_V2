"""Validation fixtures must fail locally before an evaluator can spend tokens."""
from __future__ import annotations

import pytest

from resource_librarian.index import IndexService
from resource_librarian.validation_fixtures import (
    FixturePreflightError,
    SourceFixture,
    preflight_validation_source_fixture,
    validate_validation_source_fixture,
    write_validation_source_fixture,
)


def test_source_fixture_uses_vault_kind_and_core_owned_index(vault):
    fixture = write_validation_source_fixture(vault, kind="page")
    service = IndexService(vault)
    try:
        result = preflight_validation_source_fixture(vault, fixture, service)
    finally:
        service.close()

    assert result == {"status": "ready", "path": "Sources/page/Validation Evidence.md",
                      "kind": "page", "name": "Validation Evidence",
                      "index_discoverable": True}


def test_invalid_fixture_kind_fails_before_creating_a_retired_source_folder(vault):
    with pytest.raises(FixturePreflightError, match="not one of"):
        write_validation_source_fixture(vault, kind="article")

    assert not (vault.root / "Sources" / "article").exists()


def test_fixture_preflight_rejects_kind_folder_disagreement(vault):
    fixture = write_validation_source_fixture(vault, kind="page")
    wrong = SourceFixture(path=vault.source_folder("paper") / fixture.path.name,
                          kind="page", name=fixture.name, marker=fixture.marker)
    with pytest.raises(FixturePreflightError, match="must be under"):
        validate_validation_source_fixture(vault, wrong)
