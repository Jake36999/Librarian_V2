"""OCR one real PDF page with Qwen3.5-27B through the Core's own VisionChat, once at the
model's default (thinking) and once at the shipped "none". Never prints the key.

usage: ocr_effort_probe.py PDF PAGE_INDEX [MODEL]
"""
import os, sys, time
sys.path.insert(0, r"D:\Librarian_V2\src")
for line in open(r"D:\Resource-Library\.utility\.env", encoding="utf-8"):
    name, _, value = line.strip().partition("=")
    if name.strip() == "DEEPINFRA_API_KEY":
        os.environ["DEEPINFRA_API_KEY"] = value.strip().strip('"').strip("'")

import pypdfium2
from resource_librarian import ocr

pdf, index = sys.argv[1], int(sys.argv[2])
model = sys.argv[3] if len(sys.argv) > 3 else "Qwen/Qwen3.5-27B"
page = pypdfium2.PdfDocument(pdf)[index]
import io
buf = io.BytesIO(); page.render(scale=ocr.SCALE).to_pil().save(buf, format="PNG"); png = buf.getvalue()
layer = page.get_textpage().get_text_range()

def words(s):
    return [w for w in "".join(c.lower() if c.isalnum() else " " for c in s).split() if len(w) > 2]

ref = set(words(layer))
for effort in ("", "none"):
    reader = ocr.VisionChat("deepinfra", model)
    reader.reasoning_effort = lambda e=effort: e
    t = time.time()
    text = reader.page_text(png)
    u = reader.last_response.get("usage", {})
    got = set(words(text))
    recall = len(ref & got) / max(1, len(ref))
    print({"effort": effort or "unset", "secs": round(time.time() - t, 1),
           "prompt": u.get("prompt_tokens"), "completion": u.get("completion_tokens"),
           "usd": u.get("estimated_cost"), "chars": len(text),
           "text_layer_word_recall": round(recall, 3), "head": text[:120].replace("\n", " | ")})
