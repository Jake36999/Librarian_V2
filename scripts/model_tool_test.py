"""DeepInfra model tool-calling and file-write reliability test.

For each candidate model, sends a single-turn chat with one tool defined:
  write_test_file(path, content) -> intercepts the call and writes the file.

Records: tool_called, correct_path, file_written, latency_s, error.
Outputs: model_tool_test_results.json + a Markdown table.

Usage:
  python scripts/model_tool_test.py [--models model1,model2,...] [--scratch /path]

Requires DEEPINFRA_API_KEY in the environment.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "https://api.deepinfra.com/v1/openai/chat/completions"

DEFAULT_MODELS = [
    "meta-llama/Llama-3.3-70B-Instruct",
    "meta-llama/Meta-Llama-3.1-8B-Instruct",
    "Qwen/Qwen2.5-72B-Instruct",
    "Qwen/Qwen2.5-7B-Instruct",
    "Qwen/QwQ-32B",
    "deepseek-ai/DeepSeek-V3",
    "deepseek-ai/DeepSeek-R1",
    "mistralai/Mistral-7B-Instruct-v0.3",
    "mistralai/Mistral-Small-3.1-24B-Instruct-2503",
    "google/gemma-3-27b-it",
    "microsoft/phi-4",
    "nvidia/Llama-3.1-Nemotron-70B-Instruct",
]

WRITE_TOOL = {
    "type": "function",
    "function": {
        "name": "write_test_file",
        "description": "Write text content to a file at the given absolute path. "
                       "Creates parent directories automatically.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string",
                         "description": "Absolute path to the file to write"},
                "content": {"type": "string",
                            "description": "The text to write into the file"},
            },
            "required": ["path", "content"],
        },
    },
}


def _chat(model: str, messages: list[dict], tools: list[dict], key: str) -> dict:
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "tools": tools,
        "tool_choice": "required",
        "max_tokens": 512,
        "temperature": 0,
    }).encode()
    req = urllib.request.Request(
        BASE_URL,
        data=payload,
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body[:300]}") from exc


def _slug(model: str) -> str:
    return model.replace("/", "__").replace(".", "_")


def test_model(model: str, scratch: Path, key: str) -> dict:
    model_dir = scratch / _slug(model)
    model_dir.mkdir(parents=True, exist_ok=True)
    target = model_dir / "result.txt"
    expected_content = f"hello from {model}"

    messages = [{
        "role": "user",
        "content": (
            f"Use the write_test_file tool to write the exact string "
            f"'{expected_content}' to the file at path "
            f"'{target}'. Do not write anything else — just call the tool."
        ),
    }]

    result = {
        "model": model,
        "tool_called": False,
        "correct_path": False,
        "file_written": False,
        "content_correct": False,
        "latency_s": 0.0,
        "error": "",
    }

    t0 = time.monotonic()
    try:
        resp = _chat(model, messages, [WRITE_TOOL], key)
    except Exception as exc:
        result["error"] = str(exc)
        result["latency_s"] = round(time.monotonic() - t0, 2)
        return result
    result["latency_s"] = round(time.monotonic() - t0, 2)

    choice = (resp.get("choices") or [{}])[0]
    msg = choice.get("message", {})
    tool_calls = msg.get("tool_calls") or []

    if not tool_calls:
        result["error"] = "no tool call in response"
        return result

    tc = tool_calls[0]
    fn = tc.get("function", {})
    result["tool_called"] = fn.get("name") == "write_test_file"
    if not result["tool_called"]:
        result["error"] = f"wrong tool called: {fn.get('name')}"
        return result

    try:
        args = json.loads(fn.get("arguments", "{}"))
    except json.JSONDecodeError:
        result["error"] = "could not parse tool arguments"
        return result

    called_path = args.get("path", "")
    content = args.get("content", "")

    result["correct_path"] = str(Path(called_path).resolve()) == str(target.resolve())

    # Write the file ourselves (the tool was "intercepted" by this harness)
    try:
        target.write_text(content, encoding="utf-8")
        result["file_written"] = target.exists()
        result["content_correct"] = content.strip() == expected_content
    except OSError as exc:
        result["error"] = f"write failed: {exc}"

    return result


def _md_table(results: list[dict]) -> str:
    cols = ["model", "tool_called", "correct_path", "file_written",
            "content_correct", "latency_s", "error"]
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    rows = []
    for r in results:
        def cell(k: str) -> str:
            v = r[k]
            if isinstance(v, bool):
                return "✓" if v else "✗"
            return str(v)
        rows.append("| " + " | ".join(cell(c) for c in cols) + " |")
    return "\n".join([header, sep, *rows])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", default="",
                        help="Comma-separated model ids (default: built-in list)")
    parser.add_argument("--scratch", default="",
                        help="Directory for test files (default: .librarian-app/model_tests)")
    args = parser.parse_args()

    key = os.environ.get("DEEPINFRA_API_KEY", "")
    if not key:
        sys.exit("DEEPINFRA_API_KEY not set in environment")

    models = [m.strip() for m in args.models.split(",") if m.strip()] or DEFAULT_MODELS

    if args.scratch:
        scratch = Path(args.scratch)
    else:
        # Locate the .librarian-app vault relative to the script or cwd
        here = Path(__file__).resolve().parent.parent
        scratch = here / ".librarian-app" / "model_tests"
    scratch.mkdir(parents=True, exist_ok=True)
    print(f"Scratch directory: {scratch}")
    print(f"Testing {len(models)} models…\n")

    results = []
    for model in models:
        print(f"  {model}… ", end="", flush=True)
        r = test_model(model, scratch, key)
        results.append(r)
        status = "✓" if r["file_written"] else ("⚠ " + r["error"][:60])
        print(f"{status}  ({r['latency_s']}s)")

    out_json = scratch / "model_tool_test_results.json"
    out_json.write_text(json.dumps(results, indent=2), encoding="utf-8")

    out_md = scratch / "model_tool_test_results.md"
    out_md.write_text("# Model Tool-Calling Test Results\n\n" + _md_table(results) + "\n",
                      encoding="utf-8")

    print(f"\nResults written to:\n  {out_json}\n  {out_md}")

    passed = sum(1 for r in results if r["file_written"])
    print(f"\n{passed}/{len(results)} models wrote the file successfully.")


if __name__ == "__main__":
    main()
