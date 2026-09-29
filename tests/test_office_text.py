"""Office documents and web pages as source text (2026-09-28): a lab sheet (.docx), a
lecture deck (.pptx, a page per slide) and a saved page (.html), read with the standard
library only."""
import zipfile

from resource_librarian import text

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"


def docx(path, paragraphs):
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", f'<w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>')


def pptx(path, slides):
    with zipfile.ZipFile(path, "w") as z:
        for n, lines in enumerate(slides, 1):
            paras = "".join(f"<a:p><a:r><a:t>{t}</a:t></a:r></a:p>" for t in lines)
            z.writestr(f"ppt/slides/slide{n}.xml",
                       f'<p:sld xmlns:p="p" xmlns:a="{A}"><p:txBody>{paras}</p:txBody></p:sld>')


def test_a_word_document_reads_as_one_page_of_paragraphs(tmp_path):
    path = tmp_path / "Lab Sheet.docx"
    docx(path, ["Lab 1: a first app", "Install Thunkable on your phone."])
    got = text.extract(path, tmp_path / "cache")
    assert not got.error and got.pages == ["Lab 1: a first app\nInstall Thunkable on your phone."]


def test_a_deck_reads_a_page_per_slide_in_slide_order(tmp_path):
    path = tmp_path / "Welcome.pptx"
    pptx(path, [["Welcome week"], ["Modules"], ["Agile"], ["4"], ["5"], ["6"], ["7"], ["8"],
                ["9"], ["10: last slide"]])
    got = text.extract(path, tmp_path / "cache")
    assert got.pages[0] == "Welcome week" and got.pages[9] == "10: last slide"   # 10 after 9, not 1


def test_a_saved_page_loses_its_markup_and_scripts(tmp_path):
    path = tmp_path / "page.html"
    path.write_text("<html><script>var x=1;</script><body><h1>Agile</h1><p>Sprints &amp; "
                    "stand-ups.</p></body></html>", encoding="utf-8")
    got = text.extract(path, tmp_path / "cache")
    assert got.pages == ["Agile\nSprints & stand-ups."]


def test_a_broken_office_file_is_an_error_not_a_crash(tmp_path):
    path = tmp_path / "broken.docx"
    path.write_bytes(b"not a zip")
    assert "not a readable .docx" in text.extract(path, tmp_path / "cache").error
