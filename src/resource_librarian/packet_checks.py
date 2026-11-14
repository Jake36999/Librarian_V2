"""Verification logic for packet citation closure."""

from typing import Any, Dict, List, Literal, Union
import hashlib
import json


def content_sha256(value: Any) -> str:
    """Bind a citation check to exact packet/answer JSON rather than another task."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


CitationShape = Dict[str, Union[List[Dict[str, str]], List[str]]]
PacketShape = Dict[str, Any]
VerificationResult = Dict[str, Union[List[str], Literal["bounded", "none"]]]


def verify_citations(answer: CitationShape, packet: PacketShape) -> VerificationResult:
    """Verify citations in answer against packet handles.

    Validates answer structure and checks cite field memberships.
    """
    verified: List[str] = []
    unverified: List[str] = []

    # Validate answer schema
    required_keys = {"inputs", "outputs", "calls", "claims", "not_determinable"}
    if not isinstance(answer, dict) or set(answer.keys()) != required_keys:
        return {"verified": [], "unverified": [], "closure_strength": "none"}

    for key in ["inputs", "outputs", "calls", "claims"]:
        if not isinstance(answer[key], list):
            return {"verified": [], "unverified": [], "closure_strength": "none"}

    if not isinstance(answer["not_determinable"], list):
        return {"verified": [], "unverified": [], "closure_strength": "none"}

    # Validate nested structures
    for item_list, key_prefix in [(answer["inputs"], "inputs"),
                                  (answer["outputs"], "outputs")]:
        for i, item in enumerate(item_list):
            if not isinstance(item, dict) or set(item.keys()) != {"name", "cite"}:
                return {"verified": [], "unverified": [], "closure_strength": "none"}

    for i, call in enumerate(answer["calls"]):
        if not isinstance(call, dict) or set(call.keys()) != {"target", "cite"}:
            return {"verified": [], "unverified": [], "closure_strength": "none"}

    for i, claim in enumerate(answer["claims"]):
        if not isinstance(claim, dict) or set(claim.keys()) != {"text", "cite"}:
            return {"verified": [], "unverified": [], "closure_strength": "none"}
        if not isinstance(claim["text"], str) or len(claim["text"]) > 200:
            return {"verified": [], "unverified": [], "closure_strength": "none"}

    for nd_item in answer["not_determinable"]:
        if not isinstance(nd_item, str):
            return {"verified": [], "unverified": [], "closure_strength": "none"}

    for key in ('inputs', 'outputs', 'calls', 'claims'):
        if any(not all(isinstance(v, str) for v in item.values()) for item in answer[key]):
            return {"verified": [], "unverified": [], "closure_strength": "none"}

    # Extract all cite paths in deterministic order
    cite_paths = []

    for i, inp in enumerate(answer["inputs"]):
        cite_paths.append((f"inputs[{i}].cite", inp["cite"]))

    for i, out in enumerate(answer["outputs"]):
        cite_paths.append((f"outputs[{i}].cite", out["cite"]))

    for i, call in enumerate(answer["calls"]):
        cite_paths.append((f"calls[{i}].cite", call["cite"]))

    for i, claim in enumerate(answer["claims"]):
        cite_paths.append((f"claims[{i}].cite", claim["cite"]))

    # Check handle membership
    raw_handles = packet.get('handles') if isinstance(packet, dict) else None
    if not isinstance(raw_handles, list) or not all(isinstance(h, str) for h in raw_handles):
        return {"verified": [], "unverified": [], "closure_strength": "none"}
    handles = set(raw_handles)
    for path, cite_value in cite_paths:
        if cite_value in handles:
            verified.append(path)
        else:
            unverified.append(path)

    # Determine closure strength
    closure_strength: Literal["bounded", "none"] = "bounded"
    if unverified:
        closure_strength = "none"

    return {
        "verified": verified,
        "unverified": unverified,
        "closure_strength": closure_strength
    }
