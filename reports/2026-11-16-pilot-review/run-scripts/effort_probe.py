"""Measure what reasoning_effort does to one model's tokens and cost. Never prints the key."""
import json, os, sys, time, urllib.request

KEY_FILE = r"D:\Resource-Library\.utility\.env"
for line in open(KEY_FILE, encoding="utf-8"):
    name, _, value = line.strip().partition("=")
    if name.strip() == "DEEPINFRA_API_KEY":
        os.environ["DEEPINFRA_API_KEY"] = value.strip().strip('"').strip("'")
key = os.environ.get("DEEPINFRA_API_KEY", "")
assert key, "key missing"

model = sys.argv[1]
efforts = sys.argv[2].split(",")
reps = int(sys.argv[3]) if len(sys.argv) > 3 else 2
extra = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}   # extra body fields, e.g. chat_template_kwargs

SYSTEM = ("You are a careful library clerk. Read the passage and return JSON only: "
          '{"points": [up to 4 short factual points], "limits": [up to 2 stated limitations]}.')
PASSAGE = (
    "The batch pipeline runs validate, parse, read, lenses, data, relate, metadata, review and publish "
    "in order. Each stage's key chains only the stages before it, so adding a final stage leaves earlier "
    "keys unchanged. A cleanup conversion that loses its page anchors is kept aside and the PDF's text "
    "layer is read instead; this costs nothing but loses headings. Spend is checked between items "
    "against a ceiling in dollars, so a single large item can overshoot the ceiling by its own cost. "
    "Measured on 52 documents, the median fidelity of sampled passages against the original was 1.0, "
    "but nine documents failed the page-locator check.")

out = []
for effort in efforts:
    for i in range(reps):
        body = {"model": model, "max_tokens": 4096, "temperature": 0,
                "messages": [{"role": "system", "content": SYSTEM},
                             {"role": "user", "content": PASSAGE}]}
        body.update(extra)
        if effort != "unset":
            body["reasoning_effort"] = effort
        req = urllib.request.Request(
            "https://api.deepinfra.com/v1/openai/chat/completions",
            data=json.dumps(body).encode(), method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
        t = time.time()
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                d = json.load(r)
        except urllib.error.HTTPError as e:
            out.append({"effort": effort, "error": e.code, "body": e.read().decode()[:300]})
            continue
        msg = d["choices"][0]["message"]
        u = d.get("usage", {})
        out.append({"effort": effort, "secs": round(time.time() - t, 1),
                    "prompt": u.get("prompt_tokens"), "completion": u.get("completion_tokens"),
                    "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                    "usd": u.get("estimated_cost"),
                    "reasoning_chars": len(msg.get("reasoning_content") or msg.get("reasoning") or ""),
                    "content_chars": len(msg.get("content") or ""),
                    "json_ok": _ok if (_ok := True) else None,
                    "finish": d["choices"][0].get("finish_reason"),
                    "content_head": (msg.get("content") or "")[:160]})
        try:
            txt = (msg.get("content") or "").strip().strip("`")
            txt = txt[txt.find("{"): txt.rfind("}") + 1]
            json.loads(txt); out[-1]["json_ok"] = True
        except Exception:
            out[-1]["json_ok"] = False
for row in out:
    print(json.dumps(row))
