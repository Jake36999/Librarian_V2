"""A captured PDF that names its own identifier is captured as the paper it is (M5; Owner, 27 November).

The content model's own definition: a paper is "a paper, preprint or book chapter with a bibliographic
identifier". The M5 acceptance run's arXiv preprints were captured as documents, with no identifier,
authors or year. Now capture looks the PDF's own arXiv id or DOI up with the existing fetchers and keeps
the record only when its title is the PDF's own; everything else stays as it was.
"""
from __future__ import annotations

from resource_librarian import intake
from resource_librarian.staging import StagingStore

from test_ingest_service import call, ctx, library, make_pdf  # noqa: F401  (fixture)
from test_intake import ATOM

TITLE = "Log-Based Change Capture at Scale"
BODY = ["We show that reading a database write-ahead log gives exactly-once change capture.",
        "Section one measures lag on three production systems, with numbers per system."]
CROSSREF_NO_ABSTRACT = {"message": {"title": ["Write-Ahead Logging Revisited"],
                                    "author": [{"given": "Grace", "family": "Hopper"}],
                                    "issued": {"date-parts": [[2019]]},
                                    "container-title": ["Journal of Logs"]}}


def staged(library, out):
    return StagingStore(library).load(out["item"])


def test_a_preprint_stamped_with_its_arxiv_id_is_captured_as_that_paper(library):
    make_pdf(library.root / "Inbox" / "change-capture.pdf",
             [["arXiv:2405.01234v2 [cs.DB] 3 May 2024", TITLE, *BODY], ["More of the paper."]])
    c = ctx(library)
    out = call(c, "ingest", ref="Inbox/change-capture.pdf")
    assert out["status"] == "staged", out
    item = staged(library, out)
    assert item["source_kind"] == "paper" and item["title"] == TITLE
    assert item["name"] == "change-capture"                    # the file's name: duplicate checks unchanged
    assert item["canonical_url"].startswith("file:")             # and its identity
    f = item["fields"]
    assert (f["identifier_kind"], f["identifier"], f["year"], f["paper_kind"]) == ("arxiv", "2405.01234", 2024, "preprint")
    assert f["authors"] == ["Ada Lovelace", "Alan Turing"]
    assert item["paper_check"]["found_in"] == "the PDF's text" and item["paper_check"]["was"] == "document"
    assert "looked up" in item["metadata_proposals"]["identifier"]
    assert item["sections"].get("Claim")                         # a paper's required section, from the abstract
    assert not set(intake.PAPER_FIELDS[:5]) & set(item["readiness"])
    assert any(e["kind"] == "metadata" for e in item["evidence"])


def test_an_id_in_the_file_name_counts_once_the_title_matches(library):
    make_pdf(library.root / "Inbox" / "EXT_2405.01234_Change_Capture.pdf", [[TITLE, *BODY]])
    out = call(ctx(library), "ingest", ref="Inbox/EXT_2405.01234_Change_Capture.pdf")
    item = staged(library, out)
    assert item["source_kind"] == "paper" and item["paper_check"]["found_in"] == "the file name"


def test_a_document_that_only_cites_a_doi_stays_a_document(library):
    # The DOI's record has another title: the PDF cites that paper, it is not it.
    make_pdf(library.root / "Inbox" / "notes.pdf",
             [["Meeting notes on our logging design", "See doi:10.1000/xyz for background.", *BODY]])
    c = ctx(library)
    out = call(c, "ingest", ref="Inbox/notes.pdf")
    item = staged(library, out)
    assert item["source_kind"] == "document" and "identifier" not in item["fields"]
    assert "paper_check" not in item and "metadata_proposals" not in item
    assert any("not this PDF's" in n for n in item.get("intake_notes", []))
    # The record that did not match leaves no evidence on this source.
    assert not any(e["kind"] == "metadata" for e in item["evidence"])


def test_a_lookup_that_fails_never_fails_the_capture(library):
    from resource_librarian.intake import FetchError
    make_pdf(library.root / "Inbox" / "offline.pdf", [["arXiv:2405.09999v1 [cs.DB]", TITLE, *BODY]])
    c = ctx(library, responses={"https://export.arxiv.org/api/query?id_list=2405.09999": FetchError("offline")})
    out = call(c, "ingest", ref="Inbox/offline.pdf")
    assert out["status"] == "staged"
    item = staged(library, out)
    assert item["source_kind"] == "document"
    assert any("not looked up" in n for n in item.get("intake_notes", []))


def test_a_pdf_with_no_identifier_is_captured_as_before_with_no_lookup(library):
    make_pdf(library.root / "Inbox" / "plain.pdf", [["A plain report on logging", *BODY]])
    c = ctx(library)
    out = call(c, "ingest", ref="Inbox/plain.pdf")
    assert staged(library, out)["source_kind"] == "document"
    assert not [u for u in c.extras["fetcher"].calls if "arxiv" in u or "crossref" in u]


def test_a_doi_record_without_an_abstract_takes_its_claim_from_the_pdfs_opening(library):
    make_pdf(library.root / "Inbox" / "wal.pdf",
             [["Journal of Logs 12 (2019) doi:10.1000/xyz", "Write-Ahead Logging Revisited", *BODY]])
    c = ctx(library, responses={"https://api.crossref.org/works/10.1000/xyz": CROSSREF_NO_ABSTRACT})
    out = call(c, "ingest", ref="Inbox/wal.pdf")
    item = staged(library, out)
    assert item["source_kind"] == "paper" and item["fields"]["identifier"] == "10.1000/xyz"
    assert item["fields"]["venue"] == "Journal of Logs" and item["paper_check"]["abstract"] == "PDF opening"
    assert item["sections"].get("Claim")
