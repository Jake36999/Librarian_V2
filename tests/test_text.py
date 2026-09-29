from pathlib import Path

import pytest

from resource_librarian.index import Index
from resource_librarian.search import Engine, search
from resource_librarian.text import extract, sync_documents

from conftest import add_source


def test_text_file_indexed_and_searchable(vault):
    doc = vault.root / "Sources" / "document" / "files" / "manual.txt"
    doc.parent.mkdir(parents=True)
    doc.write_text("The calibration procedure uses a reference thermistor at 25 degrees. " * 5)
    add_source(vault.root, "Manual", "A device manual.", kind_folder="document",
               extra_fm="file: Sources/document/files/manual.txt")
    with Index(vault) as ix:
        ix.refresh()
        report = sync_documents(ix)
        assert report["indexed"][0]["chunks"] == 1
        assert sync_documents(ix)["unchanged"] == 1
        engine = Engine(ix, vault.config()["heuristics"])
        assert search(engine, "thermistor calibration").results == []   # notes only
        hits = search(engine, "thermistor calibration", "in_text").results
        assert hits[0].fields["note"] == "Manual" and hits[0].fields["page"] == "p. 1"


def test_problems_are_reported(vault):
    add_source(vault.root, "Gone", "x", extra_fm="file: ../../etc/passwd")
    with Index(vault) as ix:
        ix.refresh()
        problems = sync_documents(ix)["problems"]
        assert problems and "inside this vault" in problems[0]["problem"]


def test_cache_by_content(tmp_path: Path):
    doc = tmp_path / "a.txt"
    doc.write_text("hello world " * 5)
    assert not extract(doc, tmp_path / "cache").cached
    assert extract(doc, tmp_path / "cache").cached
    assert "not supported" in extract(tmp_path / "x.xlsx", tmp_path / "cache").error


def test_pdf(tmp_path: Path):
    canvas = pytest.importorskip("reportlab.pdfgen.canvas")
    pytest.importorskip("pypdf")
    path = tmp_path / "p.pdf"
    c = canvas.Canvas(str(path))
    c.drawString(72, 720, "Workflow patterns for control flow")
    c.showPage()
    c.showPage()
    c.save()
    result = extract(path, tmp_path / "cache")
    assert "Workflow patterns" in result.pages[0] and result.empty_pages == 1
