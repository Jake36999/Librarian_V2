"""C0 is a review inventory gate, not an implementation of S1/S4 policy."""
import importlib.util
from dataclasses import replace
import json
from pathlib import Path

import pytest

from resource_librarian.registry import Card, REGISTRY, Registry, ToolSpec
import resource_librarian.tools  # noqa: F401 - discover every shipped registration

ROOT = Path(__file__).resolve().parents[1]


def auditor():
    spec = importlib.util.spec_from_file_location('access_audit', ROOT / 'scripts/audit_tool_access.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_every_registered_tool_has_an_explicit_access_review():
    review = json.loads((ROOT / 'docs/tool-access-declarations.json').read_text(encoding='utf-8'))
    assert auditor().validate(review['tools'], REGISTRY._tools.values()) == []


def test_new_content_tool_cannot_inherit_a_wildcard_or_default_declaration():
    tool = ToolSpec('new_content_reader', lambda ctx: {'text':'synthetic'}, 'consult', 'read', Card('Read content'), external=True, needs_vault=False)
    registry = Registry(); registry.register(tool)
    assert auditor().validate([], registry._tools.values()) == ['UNDECLARED_ACCESS: new_content_reader']


def test_changed_reader_cannot_keep_an_outdated_declaration():
    tool = ToolSpec('new_content_reader', lambda ctx: {'text':'synthetic'}, 'consult', 'read', Card('Read content'))
    module = auditor(); row = module.declaration(tool, content=True, status='diverges', fixes=['S1'])
    row['minimum_tier'] = 'curate'
    assert any('STALE_ACCESS' in problem for problem in module.validate([row], [tool]))


def test_content_body_change_requires_a_new_review_even_if_the_name_and_tier_stay_the_same():
    tool = ToolSpec('reader', lambda ctx: {'count':1}, 'consult', 'read', Card('Read metadata'))
    module = auditor(); row = module.declaration(tool, content=False, status='n/a', fixes=[])
    def changed_reader(ctx):
        return {'text':'new synthetic source body'}
    changed = replace(tool, fn=changed_reader)
    assert module.validate([row], [changed]) == ['STALE_ACCESS: reader']
