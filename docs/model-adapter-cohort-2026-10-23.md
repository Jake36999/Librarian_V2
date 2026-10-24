# Model-adapter cohort: research and implementation record

**Date:** 2026-10-23  
**Scope:** the curated V1 model register, V2's live role slots, and V2
service slots. This is an evidence record, not a provider-quality ranking.

## Outcome

The initial adapter layer is now based on primary invocation documentation and
the existing V2 validation artifact rather than inferred from catalogue tiles.
It has two deliberately separate parts:

- `model_invocation.py` handles chat/tool-loop protocol compatibility for
  Lead (position 1), Scribe (position 2), and Clerk (position 3).
- `service_adapters.py` handles OCR, TTS, STT, and embeddings, whose contracts
  are materially different from a chat turn.

The expectation packs contain identifiers, fixed request/response facts,
source URL/date, and a small capability state only. They cannot contain
prompts, templates, arbitrary provider parameters, code, or credentials.

## Evidence rules used

1. Provider-native API documentation establishes the transport shape.
2. An upstream official model card establishes a representation or template
   requirement only when the hosted endpoint does not override it.
3. Existing V2 live validation establishes a narrow observed result for that
   exact route and role; it does not establish a general reliability claim.
4. Absence of endpoint-specific evidence remains `unknown`, not `false` and
   not a recommendation.

DeepInfra itself documents two distinct API families: OpenAI-compatible chat
and embeddings at `/v1/openai`, and native model inference at
`/v1/inference/{model}`. That is why speech services are not implemented as
chat adapters. Source: [DeepInfra API introduction](https://github.com/deepinfra/docs/blob/main/api-reference/introduction.mdx).

## Positions 1–3: role-model cohort

The position selector is dynamic: it discovers whatever models a configured
host lists. It is *not* safe or useful to ship hundreds of guessed adapters.
The shipped cohort is the curated V1 register plus the two routes already
checked by V2.

| Cohort / role use | Exact DeepInfra model | Record state | What is enabled |
| --- | --- | --- | --- |
| Long-horizon Lead | `XiaomiMiMo/MiMo-V2.6-Flash` | reviewed | V2 L1 strict tool probe and focused Lead walks passed; tool use/results and system messages are recorded for this endpoint. |
| Long-horizon Lead | `deepseek-ai/DeepSeek-V4.1-Flash` | reviewed | Same narrow V2 L1 + focused Lead-walk evidence. |
| Long-horizon candidate | `deepseek-ai/DeepSeek-V4-Flash-0731` | draft | OpenAI-compatible transport only; endpoint L1 remains required. |
| Long-horizon candidate | `zai-org/GLM-5.3-Flash` | draft | OpenAI-compatible transport only; endpoint L1 remains required. |
| Coding candidate | `Qwen/Qwen3-Coder-480B-A35B-Instruct-Turbo` | draft | Provider-default operation only. Its upstream card describes a non-thinking instruct model; V2 does not inject a runtime flag until a DeepInfra probe proves one. |
| Coding candidate | `ByteDance/Seed-2.0-code` | draft, negative schema fact | Clerk skips the known unsupported strict `response_format` attempt, then relies on Librarian's prompted JSON validator and repair path. |
| Sub-agent candidate | `openai/gpt-oss-20b` | draft | Harmony/tool claims are upstream-contract evidence only; hosted mapping is unverified. |
| Sub-agent candidate | `openai/gpt-oss-120b` | draft | Same restriction. |
| Sub-agent candidate | `Qwen/Qwen3-32B` | draft | Hosted thinking and tool mapping are unverified. |
| Sub-agent candidate | `nvidia/Nemotron-3-Nano-30B-A3B` | draft | OpenAI-compatible transport only; endpoint L1 remains required. |

The two reviewed records are intentionally not `verified_local` or
`verified_release`; the V2 validation is documented as L1 plus focused walks,
not the L3 qualification threshold. The evidence is retained in
[`reports/2026-10-23-deepinfra-post-fix-validation.json`](../reports/2026-10-23-deepinfra-post-fix-validation.json).

Key sources for non-default behaviour:

- [Qwen3-Coder model card](https://huggingface.co/Qwen/Qwen3-Coder-480B-A35B-Instruct)
- [Qwen3-32B model card](https://huggingface.co/Qwen/Qwen3-32B)
- [OpenAI Harmony reference for gpt-oss](https://developers.openai.com/cookbook/articles/openai-harmony)
- the exact DeepInfra provider pages listed in each packed record.

## Service cohort

| Service | Typed adapter | Packed model contracts | Current rule |
| --- | --- | --- | --- |
| OCR | `openai_vision_chat_v1` | Qwen 3.5, Qwen3-VL 30B, Gemma 3 4B, Llama 4 Scout | Builds the documented image-url chat shape. An unreviewed legacy OCR selection remains usable but visible as unreviewed, preserving existing UX. |
| TTS | `deepinfra_inference_tts_v1` | Kokoro, Chatterbox Turbo, Chatterbox Multilingual, Audio8, Qwen3-TTS, HiggsAudio | Uses the record's exact `text` or `input` field. It no longer pays for a speculative alternate-field retry. Price evidence is required and can expire before the spend cap permits a request. |
| STT | `deepinfra_inference_stt_v1` | Qwen3-ASR 0.6B, Whisper Large V3 Turbo, Voxtral Mini 3B | New slot 7. Sends exactly one multipart `audio` field to the native inference endpoint; validates a bounded transcript response. It has an explicit connection/shape probe, not a synthetic reliability claim. |
| Embeddings | `openai_embeddings_v1` | BGE-M3, Qwen3-Embedding-8B, EmbeddingGemma 300M, local Nomic Embed Text v1.5 | Document/query representation rules are applied separately; reviewed DeepInfra calls request float vectors and validate declared dimensions. A representation hash is stored with vectors so changing a prefix forces a deliberate re-embed rather than mixing vector spaces. |

Important sources:

- [Kokoro native API](https://deepinfra.com/hexgrad/Kokoro-82M/api) documents
  native JSON `text` input and, on the research date, USD $0.99 per million
  characters. The older USD $0.62 figure is retained only as historical
  evidence and is not used for the spend cap.
- [Qwen3-ASR native API](https://deepinfra.com/Qwen/Qwen3-ASR-0.6B/api)
  documents `multipart/form-data` with an `audio` part and the transcript,
  segment, word, duration, and status response shape. The same pattern was
  checked for the packed Whisper and Voxtral DeepInfra routes.
- [Qwen3-Embedding-8B card](https://huggingface.co/Qwen/Qwen3-Embedding-8B)
  documents a 32K context, up-to-4096 dimensions, and instruction-aware
  retrieval representation.
- [BGE-M3 card](https://huggingface.co/BAAI/bge-m3),
  [EmbeddingGemma card](https://huggingface.co/google/embeddinggemma-300m),
  and [Nomic Embed v1.5 card](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5)
  are the sources for their respective representation rules.

## Runtime safeguards introduced

- `AdapterBackedProvider` preserves the existing `Provider.chat()` ABI; it
  does not attach unreviewed provider-native arguments.
- Invocation plans and traces contain only IDs, hashes, adapter metadata,
  timing, and typed failure state—not prompts, tokens, provider payloads,
  keys, or hidden reasoning.
- Adapter ABI, exact expectation fingerprint, endpoint fingerprint, model,
  tool schema, and protocol are part of the hard qualification fingerprint.
  A change queues required requalification rather than reusing old evidence.
- A prompt, macro, or UI wording change remains a soft/advisory dependency
  unless a deterministic check fails or a safety threshold is crossed.
- Clerk uses evidence-backed negative structured-output policy: a known
  unsupported schema contract is not retried with a guessed transport.
- OCR, TTS, STT, and embeddings cannot silently fall back to a selected chat
  model.

## Explicitly deferred work

- No native reasoning/thinking control is sent for a DeepInfra route merely
  because an upstream card documents one.
- No generic OpenAI-compatible model is marked tool-reliable from catalogue
  metadata alone.
- The historical fixed DeepInfra helper in `pdf_markdown.py` is a separate
  service-path migration; it is documented as an exception, not silently
  claimed by this cohort.
- A full model-card ingestion/review queue and signed globally-updatable pack
  channel remain follow-up work. The current pack is intentionally small,
  versioned, and auditable.

## Verification performed

Offline L0 tests cover exact pack loading, redaction, deterministic plan
construction, unknown-versus-false capability behaviour, role cohort matching,
legacy Clerk schema policy, request rendering, STT multipart generation, TTS
schema-drift handling, and embedding representation/re-index isolation. No
new paid provider calls were made while implementing this cohort.
