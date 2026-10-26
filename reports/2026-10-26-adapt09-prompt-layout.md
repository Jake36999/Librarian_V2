# ADAPT-09 prompt-layout measurement

**Date:** 2026-10-26. **Status:** route-neutral layout implemented; no
route-specific layout enabled.

ADAPT-09 moves text obtained from the library or the thread out of the system
instruction channel. The Core-authored system prompt is now a cache-stable
prefix followed by a small state-dependent suffix. Working context, desk
titles, adopted lenses, reply-review claims/note names/counterquotes, and
unverifiable assumptions travel in a delimited user-role context message
immediately before the current user turn. Prior conversation stays ahead of
that volatile message and remains eligible for prefix caching.

## Cache and input-size measurement

This is a deterministic, provider-neutral measurement using the same
conservative four-characters-per-token estimator as the profile budget guard.
The representative request has an 8,000-character working context, short
replies, one 32-character user request, no session, and no tools. “Before”
reconstructs the prior prompt ordering from the pre-ADAPT-09 implementation;
“after” uses `Loop.system_prompt()` and `Loop.context_message()`.

| Measurement | Before | After |
| --- | ---: | ---: |
| System characters | 13,934 | 6,252 |
| Delimited context-message characters | — | 8,252 |
| Estimated total input tokens | 3,528 | 3,679 |
| Cacheable leading instruction characters | 5,756 | 6,252 |
| Context A/B changes the system/prefix hash | yes | **no** |

The boundary and its system-level handling policy cost about 151 estimated
input tokens in an uncached request. In return, the full 6,252-character
instruction prefix is byte-identical across the two 8,000-character context
variants (`b11da98779304afd` in both cases). The old full system prompt changed
hash whenever the context changed. This measures cache eligibility, not a
provider's billed cache hit: provider tokenizers and cache accounting remain a
qualification concern.

## Injection and behavior measurement

The focused command was:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests/test_prompt_layout.py tests/test_openai_chat_adapter.py tests/test_anthropic_messages_adapter.py tests/test_loop.py tests/test_arguments.py tests/test_assumptions.py tests/test_d_items.py tests/test_lens_use.py -p no:cacheprovider
```

Result: **93 passed in 17.75 seconds**.

The new fixtures establish that:

- dynamic library fields are absent from system instructions and present in a
  user-role context message;
- opening and closing `library_context` lookalikes are escaped
  case-insensitively, leaving exactly one Core-authored boundary pair;
- reviewed claims, note names, reasons, and counterquotes cannot enter the
  system channel;
- library context is placed after cacheable prior history and immediately
  before the current request without mutating stored history;
- changing vault text, session purpose, phase-related state, or a refusal does
  not change the stable-prefix bytes; and
- the OpenAI and Anthropic golden adapter suites retain their existing wire
  behavior.

These are structural and scripted behavior results. No claim is made that a
particular model will always resist prompt injection, and no expectation pack
or route selects a special prompt layout from this measurement.

The final repository-wide command was:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

Result: **1,383 passed, 2 skipped, 1 deselected in 505.73 seconds**.
