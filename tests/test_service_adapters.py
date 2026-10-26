"""L0 tests for the non-chat model service adapter registry."""
from __future__ import annotations

from datetime import date

import pytest

from resource_librarian.service_adapters import (ServiceAdapterRegistry,
                                                  ServiceContractError, binding,
                                                  embedding_input, embedding_namespace,
                                                  ocr_request, registry, tts_request)


def test_bundled_service_cohort_covers_each_configurable_service_kind():
    records = registry().records
    assert {row.service for row in records} == {"ocr", "tts", "stt", "embeddings"}
    assert binding("ocr", "deepinfra", "Qwen/Qwen3.5-397B-A17B").reviewed
    assert binding("stt", "deepinfra", "Qwen/Qwen3-ASR-0.6B").reviewed
    assert binding("embeddings", "deepinfra", "BAAI/bge-m3").reviewed


def test_tts_contract_is_exact_and_its_price_is_time_bounded():
    body, selected = tts_request("deepinfra", "hexgrad/Kokoro-82M", "Hello")
    assert body == {"text": "Hello", "output_format": "mp3", "preset_voice": "af_bella"}
    assert selected.expectation and selected.expectation.price_is_current(date(2026, 10, 23))
    assert not selected.expectation.price_is_current(date(2027, 1, 22))


def test_malformed_price_expiry_fails_closed():
    packed = ServiceAdapterRegistry.from_payload({
        "schema_version": 1,
        "records": [{
            "id": "bad-expiry", "service": "tts", "provider": "deepinfra", "model_id": "x",
            "adapter_id": "deepinfra_inference_tts_v1", "adapter_abi": 1,
            "request_shape": "json", "response_shape": "audio", "input_field": "text",
            "price_per_million": 1, "price_expires_on": "not-a-date",
        }],
    })
    assert packed.records and not packed.records[0].price_is_current(date(2026, 10, 23))


def test_embedding_prefixes_keep_document_and_query_spaces_and_force_namespace_change():
    document, selected = embedding_input("deepinfra", "google/embeddinggemma-300m",
                                         "a corpus passage", kind="document")
    query, _ = embedding_input("deepinfra", "google/embeddinggemma-300m",
                               "find evidence", kind="query")
    namespace, same = embedding_namespace("api:deepinfra:google/embeddinggemma-300m",
                                          "deepinfra", "google/embeddinggemma-300m")
    assert selected.expectation and same.expectation
    assert document == "title: none | text: a corpus passage"
    assert query == "task: search result | query: find evidence"
    assert namespace.startswith("api:deepinfra:google/embeddinggemma-300m#repr-")


def test_ocr_request_uses_only_the_known_vision_content_shape_without_prompt_in_pack():
    body, selected = ocr_request("deepinfra", "Qwen/Qwen3.5-397B-A17B",
                                 "transcribe safely", "data:image/png;base64,AAAA")
    assert selected.expectation and selected.expectation.source_url.endswith("/api")
    content = body["messages"][0]["content"]
    assert content == [
        {"type": "text", "text": "transcribe safely"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
    ]


def test_service_pack_rejects_executable_or_unknown_fields():
    with pytest.raises(ServiceContractError, match="unsupported service expectation field"):
        ServiceAdapterRegistry.from_payload({
            "schema_version": 1,
            "records": [{
                "id": "unsafe", "service": "tts", "provider": "deepinfra", "model_id": "x",
                "adapter_id": "deepinfra_inference_tts_v1", "adapter_abi": 1,
                "request_shape": "json", "response_shape": "audio", "prompt": "do unsafe work",
            }],
        })
