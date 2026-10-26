"""BASE-02: the code under test and pip's install record must agree.

A stale editable install on the owner's machine (2026-10-24) pointed the
system interpreter at a sibling clone, so a bare `pytest` there described
different code.  These cases use injected paths: the real interpreter of a
test run may legitimately be either kind.
"""
import json
from pathlib import Path

from resource_librarian import doctor


def _editable(path: str) -> str:
    return json.dumps({"dir_info": {"editable": True}, "url": Path(path).resolve().as_uri()})


def test_an_editable_install_of_this_checkout_is_consistent(tmp_path):
    package = tmp_path / "checkout" / "src" / "resource_librarian" / "__init__.py"
    identity = doctor.source_identity(str(package), _editable(str(tmp_path / "checkout")))
    assert identity["consistent"] is True
    assert identity["project"] == str((tmp_path / "checkout").resolve())


def test_an_install_record_for_another_checkout_is_reported(tmp_path):
    package = tmp_path / "checkout" / "src" / "resource_librarian" / "__init__.py"
    identity = doctor.source_identity(str(package), _editable(str(tmp_path / "stale-clone")))
    assert identity["consistent"] is False
    assert identity["editable_install"] == str((tmp_path / "stale-clone").resolve())


def test_a_wheel_install_is_consistent_by_construction(tmp_path):
    package = tmp_path / "site-packages" / "resource_librarian" / "__init__.py"
    assert doctor.source_identity(str(package), "")["consistent"] is True
    assert doctor.source_identity(str(package), "not json")["consistent"] is True


def test_doctor_names_the_stale_record_and_the_fix(monkeypatch, tmp_path):
    stale = {"executable": "py", "base_executable": "py", "venv": False,
             "package": "D:/checkout/src/resource_librarian", "project": "D:/checkout",
             "editable_install": "D:/stale-clone", "consistent": False}
    monkeypatch.setattr(doctor, "source_identity", lambda: stale)
    check = {c.name: c for c in doctor.checks(None)}["source identity"]
    assert check.ok is False
    assert "D:/stale-clone" in check.detail and "pip install -e ." in check.detail


def test_this_test_run_imports_the_checkout_under_test():
    # The conftest guard would have stopped the run otherwise; keep it honest.
    import resource_librarian
    checkout_src = Path(__file__).resolve().parents[1] / "src"
    assert checkout_src in Path(resource_librarian.__file__).resolve().parents
