"""PDF cleanup (pdf_markdown.py) and the pdf_to_markdown tool: batching joins
back up whole, the model is always DeepInfra regardless of the vault's own
[clerk] route, and the tool writes a clean .md sibling."""
from __future__ import annotations

from dataclasses import dataclass

from resource_librarian import pdf_markdown, text, tools  # noqa: F401 (registers tools)
from resource_librarian.providers import Reply
from resource_librarian.registry import REGISTRY, Context


@dataclass
class FakeEndpoint:
    """Echoes back what it was asked to clean, tagged so a test can tell
    batches apart - never a real network call."""
    calls: list[dict] | None = None

    def __post_init__(self):
        if self.calls is None:
            self.calls = []

    def chat(self, system, messages, tools, max_tokens=4096, temperature=None):
        self.calls.append({"system": system, "user": messages[0]["content"],
                           "max_tokens": max_tokens})
        return Reply(text=f"CLEANED[{messages[0]['content']}]")


def test_batch_pages_groups_under_the_char_limit():
    pages = ["a" * 4000, "b" * 4000, "c" * 100]
    batches = pdf_markdown.batch_pages(pages, batch_chars=6000)
    assert batches == ["a" * 4000 + "\n\n" + "b" * 4000, "c" * 100]


def test_batch_pages_of_nothing_is_nothing():
    assert pdf_markdown.batch_pages([]) == []


def test_clean_document_batches_cleans_and_joins():
    fake = FakeEndpoint()
    pages = ["Page one raw text.", "Page two raw text."]
    markdown, batches = pdf_markdown.clean_document(pages, fake)
    assert batches == 1        # both pages fit in one 6000-char batch
    assert markdown == "CLEANED[Page one raw text.\n\nPage two raw text.]"
    assert fake.calls[0]["system"] == pdf_markdown.CLEANUP_SYSTEM


def test_clean_document_never_summarises_in_its_own_instruction():
    # The one thing this must never regress on porting: the system prompt
    # still tells the model not to add or shorten anything.
    assert "do not" in pdf_markdown.CLEANUP_SYSTEM.lower()
    assert "summar" in pdf_markdown.CLEANUP_SYSTEM.lower()


def test_endpoint_is_always_deepinfra_never_the_vaults_own_clerk():
    ep = pdf_markdown.endpoint()
    assert ep.name == "deepinfra"
    assert ep.model == pdf_markdown.MODEL == "deepseek-ai/DeepSeek-V4-Flash-0731"


def test_pdf_to_markdown_tool_writes_a_clean_sibling_file(vault, monkeypatch):
    pdf_path = vault.root / "Inbox" / "book.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"%PDF-1.4 not a real pdf, extraction is mocked below")

    monkeypatch.setattr(text, "extract",
                        lambda path, cache_dir: text.Extraction(pages=["Raw page one.",
                                                                       "Raw page two."]))
    fake = FakeEndpoint()
    monkeypatch.setattr(pdf_markdown, "endpoint", lambda: fake)

    ctx = Context(tier="contribute", vault=vault)
    result = REGISTRY.call("pdf_to_markdown", {"file": "Inbox/book.pdf"}, ctx)
    assert "error" not in result, result
    assert result["path"] == "Inbox/book.md"
    assert result["pages"] == 2 and result["batches"] == 1
    written = (vault.root / "Inbox" / "book.md").read_text(encoding="utf-8")
    assert written == "CLEANED[Raw page one.\n\nRaw page two.]"


def test_pdf_to_markdown_tool_refuses_a_non_pdf(vault):
    (vault.root / "Inbox").mkdir(exist_ok=True)
    (vault.root / "Inbox" / "notes.txt").write_text("hello")
    ctx = Context(tier="contribute", vault=vault)
    result = REGISTRY.call("pdf_to_markdown", {"file": "Inbox/notes.txt"}, ctx)
    assert "not a PDF" in result.get("detail", "")


def test_pdf_to_markdown_tool_refuses_outside_the_vault(vault):
    ctx = Context(tier="contribute", vault=vault)
    result = REGISTRY.call("pdf_to_markdown", {"file": "../../etc/passwd"}, ctx)
    assert "error" in result


def test_parts_are_cleaned_at_once_in_page_order_and_say_how_far_they_are():
    """Owner check O7 (2026-10-01): a 14-part report sat on 'parse' for minutes."""
    fake = FakeEndpoint()
    pages = [f"page {i} " + "x" * 6000 for i in range(5)]
    heard = []
    markdown, batches = pdf_markdown.clean_document(pages, fake, progress=heard.append)
    assert batches == 5 and len(fake.calls) == 5
    assert [markdown.index(f"page {i}") for i in range(5)] == sorted(
        markdown.index(f"page {i}") for i in range(5))
    assert heard[0] == "cleaning the PDF's text: 0 of 5 parts"
    assert heard[-1] == "cleaning the PDF's text: 5 of 5 parts" and len(heard) == 6


def test_the_batch_banner_shows_a_steps_progress(vault, monkeypatch):
    from resource_librarian import batch
    from resource_librarian.workflows import RunStore
    runs = RunStore(vault)
    runs.append("batch-x", {"type": "started", "items": ["a"]})
    runs.append("batch-x", {"type": "stage", "item": "a", "stage": "parse"})
    runs.append("batch-x", {"type": "progress", "item": "a", "stage": "parse",
                            "detail": "cleaning the PDF's text: 3 of 9 parts"})
    monkeypatch.setattr(batch, "live", lambda v: "batch-x")
    assert batch.status(vault, "batch-x")["current"] == {
        "item": "a", "stage": "parse", "detail": "cleaning the PDF's text: 3 of 9 parts"}
