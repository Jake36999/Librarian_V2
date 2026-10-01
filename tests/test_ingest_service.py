"""Requirements Addendum R12 (2026-09-30), plan P3b: the ingest service.

Capture in any phase; a declared subflow per source kind with a quality branch (a scan
needs OCR, a mechanical PDF is cleaned, a script-built page is flagged, a paper's open-access
PDF is fetched, a dataset's access points are found); duplicates caught by content and
flagged by title; the fit record kept apart; and every result says the state it reached and
what comes next."""
import shutil
import types

import pytest

from resource_librarian import clerk, intake, notes, tools  # noqa: F401  (registers tools)
from resource_librarian.providers import ProviderError
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.staging import StagingStore

from conftest import add_source, pdf_bytes
from test_intake import RESPONSES, clerk_answers

HEADER = "Journal of Stream Systems 2024"
BODY = [["Change data capture reads the write-ahead infor-",
         "mation of a database and streams each row as it",
         "changes, so a consumer sees inserts and up-",
         "dates in order without polling the tables."]] * 3


@pytest.fixture
def library(vault):
    for i in range(4):
        add_source(vault.root, f"filler {i}", f"Draws pictures number {i}.")
    return vault


def make_pdf(path, pages):
    pytest.importorskip("pypdf")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pdf_bytes(pages))
    return path


def mechanical(path):
    return make_pdf(path, [[HEADER, *body, str(i)] for i, body in enumerate(BODY, 1)])


class Cleaner:
    """Stands in for DeepInfra's cleanup model: reflows the text, drops the header."""

    def __init__(self, fail=False):
        self.calls, self.fail = 0, fail

    def chat(self, system, messages, tools, max_tokens=0):
        self.calls += 1
        if self.fail:
            raise ProviderError("DEEPINFRA_API_KEY is not set")
        raw = messages[0]["content"].replace("-\n", "").replace(HEADER, "")
        return types.SimpleNamespace(text="## Change data capture\n\n" + " ".join(
            w for w in raw.split() if not w.isdigit()))


def ctx(vault, responses=None, tier="curate", **extras):
    return Context(tier=tier, vault=vault, extras={
        "clerk": clerk.Scripted(clerk_answers),
        "fetcher": intake.Replay({**RESPONSES, **(responses or {})}), **extras})


def call(c, name, **args):
    return REGISTRY.call(name, args, c)


def run_batch(c, item):
    call(c, "staging_decide", item_ids=[item], decision="approve")
    return call(c, "process_approved")["items"][0]


# ------------------------------------------------------------------ documents

def test_a_scanned_pdf_is_flagged_as_needing_ocr_and_its_note_says_so(library):
    make_pdf(library.root / "Inbox" / "scan.pdf", [[], []])
    c = ctx(library)
    out = call(c, "ingest", ref="Inbox/scan.pdf")
    assert out["status"] == "staged" and out["state"] == "staged"
    assert out["quality"]["verdict"] == "needs_ocr" and "Capture found: no page" in out["next"]
    item = StagingStore(library).load(out["item"])
    assert item["intake"]["stages"]["quality"] == "needs_ocr"
    done = run_batch(c, out["item"])
    assert done["status"] == "partial" and done["stages"]["parse"] == "partial"
    accepted = call(c, "staging_decide", item_ids=[out["item"]], decision="accept",
                    bottom_line="A scanned handout.", what_it_solves="Unknown until OCR.")
    fm = notes.load(library.root / accepted["results"][0]["promotion"]["path"]).frontmatter
    assert any("text layer" in n for n in fm["not_examined"])


def test_a_mechanical_pdf_is_cleaned_in_the_batch_and_read_from_the_clean_copy(library):
    mechanical(library.root / "Inbox" / "cdc.pdf")
    cleaner = Cleaner()
    c = ctx(library, pdf_endpoint=cleaner)
    out = call(c, "ingest", ref="Inbox/cdc.pdf")
    assert out["quality"]["verdict"] == "cleanup"
    assert any("broken across lines" in s for s in out["quality"]["signs"])
    assert cleaner.calls == 0                                 # capture never spends on it
    done = run_batch(c, out["item"])
    assert done["status"] == "enriched" and cleaner.calls == 1
    item = StagingStore(library).load(out["item"])
    assert item["clean_file"] == f".librarian/staging/files/{out['item']}.md"
    assert "information of a database" in (library.root / item["clean_file"]).read_text(
        encoding="utf-8")
    assert not (library.root / "Inbox" / "cdc.md").exists()     # never beside it, as a note
    accepted = call(c, "staging_decide", item_ids=[out["item"]], decision="accept")
    fm = notes.load(library.root / accepted["results"][0]["promotion"]["path"]).frontmatter
    assert fm["file"].endswith("files/cdc.pdf")
    assert fm["file_markdown"].endswith("files/cdc (clean text).md")
    assert fm["coverage"] == "full"


def test_without_the_cleanup_model_the_raw_text_is_read_and_says_so(library):
    mechanical(library.root / "Inbox" / "cdc.pdf")
    c = ctx(library, pdf_endpoint=Cleaner(fail=True))
    out = call(c, "ingest", ref="Inbox/cdc.pdf")
    done = run_batch(c, out["item"])
    assert done["status"] == "partial" and done["stages"]["parse"] == "partial"
    item = StagingStore(library).load(out["item"])
    assert any("cleanup not run" in n for n in item["processing"]["not_examined"])


def test_the_same_file_under_another_name_is_caught(library):
    first = mechanical(library.root / "Inbox" / "Welcome Week.pdf")
    shutil.copy(first, library.root / "Inbox" / "slides-final.pdf")
    c = ctx(library)
    staged = call(c, "ingest", ref="Inbox/Welcome Week.pdf")
    again = call(c, "ingest", ref="Inbox/slides-final.pdf")
    assert again["status"] == "already_held" and "the same content" in again["detail"]
    assert again["state"] == "waiting in staging" and staged["item"] in again["next"]


def test_a_similar_title_is_flagged_not_blocked(library):
    mechanical(library.root / "Inbox" / "Welcome Week.pdf")
    make_pdf(library.root / "Inbox" / "Welcome Week (1).pdf", [["A different deck."]])
    c = ctx(library)
    call(c, "ingest", ref="Inbox/Welcome Week.pdf")
    out = call(c, "ingest", ref="Inbox/Welcome Week (1).pdf")
    assert out["status"] == "staged"
    assert out["detail"]["possible_duplicate_of"] == "Welcome Week (staged)"


# ------------------------------------------------------------------ pages, papers, datasets

def test_a_script_built_page_is_flagged(library):
    shell = ("<html><head><title>The App</title><script src='a.js'></script>"
             "<script src='b.js'></script><script>boot()</script></head>"
             "<body><div id='root'></div></body></html>")
    out = call(ctx(library, {"https://app.example.org/": shell}), "ingest",
               ref="https://app.example.org/")
    assert out["quality"]["verdict"] == "js_shell" and "Playwright" in out["quality"]["next"]


def test_a_papers_open_access_pdf_is_fetched_by_the_batch(library, tmp_path):
    pdf = make_pdf(tmp_path / "paper.pdf", BODY)
    c = ctx(library, {"https://arxiv.org/pdf/2405.01234": pdf.read_bytes()})
    out = call(c, "ingest", ref="arXiv:2405.01234")
    assert out["quality"]["verdict"] == "metadata_only"
    assert out["quality"]["full_text_url"] == "https://arxiv.org/pdf/2405.01234"
    done = run_batch(c, out["item"])
    assert done["status"] == "enriched", done
    item = StagingStore(library).load(out["item"])
    assert item["full_text"]["pages"] == 3 and item["file"].startswith(".librarian/")
    accepted = call(c, "staging_decide", item_ids=[out["item"]], decision="accept")
    fm = notes.load(library.root / accepted["results"][0]["promotion"]["path"]).frontmatter
    assert fm["file"].startswith("Sources/paper/files/")          # the full text is kept


def test_a_dataset_is_captured_with_its_access_points(library):
    page = ("<html><head><title>Rows Benchmark</title></head><body><p>Row-change traces "
            "from ten databases.</p><a href='/records/7/files/rows.csv'>rows.csv</a>"
            "<a href='https://zenodo.org/api/records/7'>API</a></body></html>")
    out = call(ctx(library, {"https://zenodo.org/records/7": page}), "ingest",
               ref="https://zenodo.org/records/7")
    item = StagingStore(library).load(out["item"])
    assert item["source_kind"] == "dataset" and out["quality"]["verdict"] == "usable"
    assert item["fields"]["access_points"] == ["https://zenodo.org/records/7/files/rows.csv",
                                               "https://zenodo.org/api/records/7"]


# ------------------------------------------------------------------ any phase, any outcome

def test_capture_in_frame_stages_without_a_fit_claim(library):
    make_pdf(library.root / "Inbox" / "lab.pdf", [["Lab 1: install Thunkable."]])
    c = ctx(library, tier="contribute")
    call(c, "open_session", purpose="explore", question="first-year labs")
    out = call(c, "ingest", ref="Inbox/lab.pdf")
    assert out["status"] == "staged" and "screen" not in out
    item = StagingStore(library).load(out["item"])
    assert item["intake"]["stages"]["screen"] == "not framed" and "fit_screen" not in item
    assert call(c, "session_status")["phase"] == "frame"


def test_every_result_says_where_the_reference_went(library):
    c = ctx(library)
    failed = call(c, "ingest", ref="nobody/nothing")
    assert failed["state"] == "failed" and "queue_retry" in failed["next"]
    assert call(c, "queue_list")["failed"][0]["ref"] == "nobody/nothing"
    deferred = call(c, "ingest", ref="acme/rowstream", defer=True, note="for later")
    assert deferred["state"] == "queued" and "intake_run" in deferred["next"]
    captured = call(c, "intake_run")["results"][0]
    assert captured["state"] == "staged"
    again = call(c, "ingest", ref="acme/rowstream")
    assert again["state"] == "waiting in staging"
