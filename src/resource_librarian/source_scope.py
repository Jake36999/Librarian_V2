"""Deterministic source-scope checks. No model calls or guessed ownership."""
import json
import re


def collect(value, known, inherited=False):
    if isinstance(value, dict):
        external = inherited or value.get('provenance') == 'third_party'
        if external and isinstance(value.get('cite_as'), str) and len(known) < 512:
            known[value['cite_as']] = 'third_party'
        for key, child in value.items():
            if key == 'content' and isinstance(child, str) and len(child) <= 160000:
                try: collect(json.loads(child), known, external)
                except (ValueError, TypeError): pass
            else: collect(child, known, external)
    elif isinstance(value, list):
        for child in value: collect(child, known, inherited)


def warnings(text, known):
    problems = []
    for paragraph in text.split('\n\n'):
        if not re.search(r'\b(?:our|this)\s+(?:current\s+)?(?:system|implementation|codebase)\b', paragraph, re.I): continue
        cited = [cite for cite, role in known.items() if role == 'third_party' and cite in paragraph]
        if cited:
            problems.extend(dict(code='THIRD_PARTY_AS_CURRENT_SYSTEM', cite_as=cite,
                                 expected_scope='external_reference') for cite in sorted(cited))
    return problems


def annotate(text, known, on_event):
    problems = warnings(text, known)
    if not problems: return text
    on_event(dict(type='source_scope_warning', problems=problems))
    return text + '\n\nSource scope warning: the cited third-party material is external reference; it does not establish the current state of your system.'
