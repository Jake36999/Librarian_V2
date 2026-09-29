import pytest

from resource_librarian import rules
from resource_librarian.rules import RULES, Refusal


def test_refusal_names_its_rule():
    refusal = Refusal("TIER_REFUSED", "nope")
    assert refusal.to_dict() == {"refused": "TIER_REFUSED",
                                 "rule": RULES["TIER_REFUSED"].statement, "detail": "nope"}


def test_unknown_code_is_a_programming_error():
    with pytest.raises(KeyError):
        Refusal("NOT_A_RULE", "x")


def test_rules_page_lists_every_code():
    page = rules.render_markdown()
    for code in RULES:
        assert f"`{code}`" in page


def test_codes_are_unique_and_upper_snake():
    assert len(RULES) == len(rules._RULES)
    assert all(code == code.upper() and " " not in code for code in RULES)
