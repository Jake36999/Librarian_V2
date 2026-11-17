"""Generic file names take their folder's name (2026-11-17: project READMEs were refused as
duplicates of the library's own README)."""
from pathlib import Path

from resource_librarian.intake import file_title


def test_generic_file_names_take_their_folder():
    assert file_title(Path("F:/x/mitmproxy-main/README.md")) == "mitmproxy-main - README"
    assert file_title(Path("docs/runbooks/Index.md")) == "runbooks - Index"
    assert file_title(Path("docs/dual_receiver_plan.md")) == "dual_receiver_plan"
