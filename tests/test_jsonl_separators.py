"""M0 (2026-10-01) found it: a web page's U+2028 inside a research round's event made the
session unloadable - `json.dumps(ensure_ascii=False)` writes the separator raw, and
`str.splitlines()` cut the event in two. Every JSON Lines reader splits on newlines only."""
import json

from resource_librarian.session import SessionStore, _last_hash
from resource_librarian.vault import jsonl_lines

SEPARATORS = "    \x85 \x0b \x0c \x1c \x1d \x1e"


def test_only_a_newline_ends_a_record():
    text = json.dumps({"a": SEPARATORS}, ensure_ascii=False) + "\r\n" + \
        json.dumps({"b": 1}) + "\n"
    rows = [json.loads(line) for line in jsonl_lines(text) if line.strip()]
    assert rows == [{"a": SEPARATORS}, {"b": 1}]


def test_a_session_holding_line_separators_loads_verifies_and_rewinds(vault):
    store = SessionStore(vault)
    session = store.new("explore", "", "what holds a separator")
    store.append(session.id, {"type": "message", "role": "user", "text": "first"})
    store.append(session.id, {"type": "round", "n": 1, "queries": [f"terms of service{SEPARATORS}"],
                              "new": [], "vocabulary": [SEPARATORS]})
    store.append(session.id, {"type": "message", "role": "assistant",
                              "text": f"page text{SEPARATORS}end"})
    store.append(session.id, {"type": "message", "role": "user", "text": "second"})
    loaded = store.load(session.id)
    assert [m["text"] for m in loaded.messages][:2] == ["first", f"page text{SEPARATORS}end"]
    assert store.verify() == []                         # the hash chain still holds
    last = jsonl_lines(store.path(session.id).read_text(encoding="utf-8"))
    last = [line for line in last if line.strip()][-1]
    assert _last_hash(store.path(session.id)) == json.loads(last)["h"]
    store.truncate_to(session.id, 1)                    # rewind through the separator line
    assert [m["text"] for m in store.load(session.id).messages] == \
        ["first", f"page text{SEPARATORS}end"]
    assert store.verify() == []
