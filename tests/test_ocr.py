"""Requirements Addendum R17, slot 4 (2026-09-30): OCR for PDF pages with no text layer.

The library's own OCR model reads only the image-only pages; the note says its text came
from OCR and from which model; with no model chosen the scan stays a stated gap and is never
handed to a chat model; the choice is kept per library, and Test makes one real call."""
import json
import urllib.request

import pytest

from resource_librarian import clerk, intake, notes, ocr, tools  # noqa: F401
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.staging import StagingStore
from resource_librarian.vault import Vault

from conftest import add_source, pdf_bytes
from test_app import served  # noqa: F401  (fixture)
from test_intake import clerk_answers

pytest.importorskip("pypdfium2")


class Reader:
    """Stands in for the OCR model: says which page image it was shown."""
    name = "fake:ocr"

    def __init__(self):
        self.calls = 0

    def page_text(self, png: bytes) -> str:
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        self.calls += 1
        return f"Change data capture streams row changes, page image {self.calls}."


@pytest.fixture
def library(vault):
    for i in range(4):
        add_source(vault.root, f"filler {i}", f"Draws pictures number {i}.")
    (vault.root / "Inbox").mkdir(exist_ok=True)
    (vault.root / "Inbox" / "scan.pdf").write_bytes(
        pdf_bytes([[], ["A page that has its own text layer."], []]))
    return vault


def ctx(vault, **extras):
    return Context(tier="curate", vault=vault,
                   extras={"clerk": clerk.Scripted(clerk_answers), **extras})


def call(c, name, **args):
    return REGISTRY.call(name, args, c)


def test_only_the_image_only_pages_are_read(library):
    reader = Reader()
    got = ocr.read_pdf(library, library.root / "Inbox" / "scan.pdf", reader)
    assert reader.calls == 2 and (got["needed"], got["read"], got["pages"]) == (2, 2, 3)
    assert "[page 2]\nA page that has its own text layer." in got["markdown"]
    assert "[page 3]\nChange data capture" in got["markdown"]


def test_the_batch_reads_a_scan_by_ocr_and_the_note_says_so(library):
    reader = Reader()
    c = ctx(library, ocr_endpoint=reader)
    item = call(c, "ingest", ref="Inbox/scan.pdf")["item"]
    call(c, "staging_decide", item_ids=[item], decision="approve")
    done = call(c, "process_approved")["items"][0]
    assert done["status"] == "enriched", done
    staged = StagingStore(library).load(item)
    assert staged["ocr"] == {"model": "fake:ocr", "pages": 3, "needed": 2, "read": 2, "recipe": "visual-v3"}
    accepted = call(c, "staging_decide", item_ids=[item], decision="accept")
    fm = notes.load(library.root / accepted["results"][0]["promotion"]["path"]).frontmatter
    assert fm["coverage"] == "full (text by OCR)"
    assert fm["text_origin"] == "OCR by fake:ocr: 2 of 2 image-only pages"


def test_with_no_ocr_model_the_scan_is_a_stated_gap(library):
    library.set_setting("services", "ocr", "")
    c = ctx(library)
    item = call(c, "ingest", ref="Inbox/scan.pdf")["item"]
    call(c, "staging_decide", item_ids=[item], decision="approve")
    call(c, "process_approved")
    staged = StagingStore(library).load(item)
    assert staged["status"] == "partial" and "ocr" not in staged
    assert any("no OCR model is chosen" in n for n in staged["processing"]["not_examined"])
    assert call(c, "ocr_pdf", file="Inbox/scan.pdf")["error"] == "invalid_arguments"


def test_the_default_model_without_a_key_makes_no_call_and_says_why(library):
    assert ocr.choice(library) == {"provider": "deepinfra", "model": "Qwen/Qwen3.5-397B-A17B",
                                   "format": "vision_chat"}
    c = ctx(library)
    item = call(c, "ingest", ref="Inbox/scan.pdf")["item"]
    call(c, "staging_decide", item_ids=[item], decision="approve")
    call(c, "process_approved")
    staged = StagingStore(library).load(item)
    assert any("DEEPINFRA_API_KEY is not set" in n for n in staged["processing"]["not_examined"])


def test_the_vision_chat_request_carries_the_page_image(monkeypatch):
    monkeypatch.setenv("DEEPINFRA_API_KEY", "test-key")
    sent = {}

    class Reply:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": "The librarian reads "
                                                                   "this page."}}]}).encode()

    def fake_urlopen(request, timeout=0):
        sent["url"], sent["auth"] = request.full_url, request.get_header("Authorization")
        sent["body"] = json.loads(request.data)
        return Reply()
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    reader = ocr.VisionChat("deepinfra", "Qwen/Qwen3.5-397B-A17B")
    assert reader.page_text(ocr.sample_png()) == "The librarian reads this page."
    assert sent["url"].endswith("/chat/completions") and sent["auth"] == "Bearer test-key"
    content = sent["body"]["messages"][0]["content"]
    assert sent["body"]["model"] == "Qwen/Qwen3.5-397B-A17B"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_the_slot_is_chosen_per_library_and_tested(served, tmp_path, monkeypatch):
    app, client, _ = served
    slots = {s["slot"]: s for s in client.get("/api/services")[1]["slots"]}
    assert slots["ocr"]["model"] == "Qwen/Qwen3.5-397B-A17B" and slots["ocr"]["default"]
    assert slots["tts"]["built"] and slots["embeddings"]["built"]       # 5: 2026-10-01; 6: P5.4
    out = client.post("/api/services", {"slot": "ocr", "provider": "deepinfra",
                                        "model": "Qwen/Qwen3-VL-30B-A3B-Instruct"})[1]
    ocr_slot = next(s for s in out["slots"] if s["slot"] == "ocr")
    assert ocr_slot["model"] == "Qwen/Qwen3-VL-30B-A3B-Instruct" and not ocr_slot["default"]
    assert Vault(app.vault.root).setting("services", "ocr") == \
        "deepinfra:Qwen/Qwen3-VL-30B-A3B-Instruct"                     # survives a restart
    from resource_librarian.init import init
    init(tmp_path / "other", name="Other")
    assert ocr.choice(Vault(tmp_path / "other"))["model"] == "Qwen/Qwen3.5-397B-A17B"
    assert client.post("/api/services", {"slot": "tts", "provider": "deepinfra",
                                         "model": "x"})[0] == 400
    monkeypatch.setattr(ocr.VisionChat, "page_text",
                        lambda self, png: "The librarian reads this page.")
    tested = client.post("/api/services/test", {"slot": "ocr"})[1]
    assert tested["ok"] and tested["model"] == "deepinfra:Qwen/Qwen3-VL-30B-A3B-Instruct"


def test_optical_all_pages_includes_existing_text(library):
    reader = Reader()
    result = ocr.read_pdf(library, library.root / "Inbox/scan.pdf", reader, all_pages=True)
    assert reader.calls == 3
    assert result["needed"] == result["read"] == 3


def test_partial_ocr_is_not_complete_parse(library):
    from resource_librarian import batch
    class Failing(Reader):
        def page_text(self, png):
            self.calls += 1
            if self.calls > 1:
                raise ocr.OcrError("temporary provider failure")
            return "One page captured."
    c = ctx(library, ocr_endpoint=Failing(), optical_all_pages=True)
    ident = call(c, "ingest", ref="Inbox/scan.pdf")["item"]
    item = StagingStore(library).load(ident)
    item["intake"] = {"quality": {"verdict": "cleanup"}}
    StagingStore(library).save(item)
    result = batch._parse(c, item)
    assert result["status"] == "partial"


def test_optical_retry_reuses_completed_pages(library):
    saved = {}
    reader = Reader()
    first = ocr.read_pdf(library, library.root / "Inbox/scan.pdf", reader, 1,
                         all_pages=True, cached_pages=saved, on_page=saved.__setitem__)
    assert first["read"] == 1
    second = ocr.read_pdf(library, library.root / "Inbox/scan.pdf", reader,
                          all_pages=True, cached_pages=saved, on_page=saved.__setitem__)
    assert second["read"] == 3
    assert reader.calls == 3


def test_parse_retries_existing_incomplete_optical_conversion(library):
    from resource_librarian import batch
    c = ctx(library, ocr_endpoint=Reader(), optical_all_pages=True)
    ident = call(c, "ingest", ref="Inbox/scan.pdf")["item"]
    item = StagingStore(library).load(ident)
    item.update(clean_file="existing-partial.md", ocr={"read": 1, "needed": 3})
    StagingStore(library).save(item)
    result = batch._parse(c, item)
    assert result["status"] == "complete"
    assert StagingStore(library).load(ident)["ocr"]["read"] == 3


def test_truncated_vision_response_is_not_success(monkeypatch):
    from resource_librarian import providers
    monkeypatch.setenv("DEEPINFRA_API_KEY", "test-key")
    monkeypatch.setattr(providers, "_request", lambda *a, **kw: {
        "choices": [{"finish_reason": "length", "message": {"content": "partial equation"}}]})
    with pytest.raises(ocr.OcrError, match="truncated"):
        ocr.VisionChat("deepinfra", "Qwen/Qwen3.5-397B-A17B").page_text(b"image")


def test_optical_pages_use_declared_concurrency_and_commit_on_caller(library):
    import threading
    barrier = threading.Barrier(3)
    caller = threading.get_ident()
    saved = []
    class ParallelReader:
        name = "parallel-fixture"
        concurrency = 3
        def page_text(self, png):
            barrier.wait(timeout=2)
            return "Captured page"
    def save(i, value):
        assert threading.get_ident() == caller
        saved.append(i)
    got = ocr.read_pdf(library, library.root / "Inbox/scan.pdf", ParallelReader(),
                       all_pages=True, on_page=save)
    assert got["read"] == 3
    assert sorted(saved) == [0, 1, 2]


def test_source_change_during_ocr_cannot_bind_output_to_old_bytes(library):
    path = library.root / "Inbox/scan.pdf"
    class ChangingReader(Reader):
        def page_text(self, png):
            path.write_bytes(pdf_bytes([["A replacement source."]]))
            return "Text from an obsolete source image."
    out = call(ctx(library, ocr_endpoint=ChangingReader()), "ocr_pdf",
               file="Inbox/scan.pdf", all_pages=True, max_pages=1)
    assert out.get("refused") == "EVIDENCE_IS_NEVER_EDITED", out
    assert "Original PDF changed" in out["detail"]


@pytest.mark.parametrize("context,cap,expected", [(7000,8000,5800), (20000,16000,16000)])
def test_truncated_page_can_retry_once_with_measured_window_budget(monkeypatch, context, cap, expected):
    from resource_librarian import providers
    monkeypatch.setenv("DEEPINFRA_API_KEY", "test-key")
    budgets = []
    def request(*args, **kwargs):
        budgets.append(args[3]["max_tokens"])
        return {"choices": [{"finish_reason": "length" if len(budgets) == 1 else "stop",
                             "message": {"content": "partial" if len(budgets) == 1 else "complete"}}],
                "usage": {"prompt_tokens": 1200, "completion_tokens": 4000 if len(budgets) == 1 else 500,
                          "estimated_cost": 0.01}}
    monkeypatch.setattr(providers, "_request", request)
    reader = ocr.VisionChat("deepinfra", "Qwen/Qwen3.5-27B")
    reader.context_tokens = context
    reader.max_output_tokens = cap
    assert reader.page_text(b"image") == "complete"
    assert budgets == [4000, expected]
    assert reader.last_response["usage"]["estimated_cost"] == pytest.approx(0.02)
