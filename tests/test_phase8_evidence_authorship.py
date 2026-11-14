from resource_librarian.evidence import EvidenceStore
from resource_librarian import dik


def test_authorship_is_where_from_metadata_not_framing_and_is_identity_bound(vault):
    store = EvidenceStore(vault)
    own = store.put('readme', 'fixture-source', {'text': 'same'},
                    fetched_at='2026-11-14', authorship='owner_created')
    third = store.put('readme', 'fixture-source', {'text': 'same'},
                      fetched_at='2026-11-14', authorship='third_party')
    assert own.id != third.id
    assert store.get(own.id).to_dict()['authorship'] == 'owner_created'
    assert store.get(third.id).to_dict()['authorship'] == 'third_party'
    assert store.verify() == []


def test_dik_data_keeps_source_authorship_and_model_generation_distinct(vault):
    record = {'source': 'fixture', 'authorship': 'third_party', 'data': [
        {'id': 'a', 'origin': 'source-stated'}, {'id': 'b', 'origin': 'model-produced'}]}
    dik.save(vault, record)
    saved = dik.load(vault, 'fixture')
    assert saved['data'][0]['authorship'] == 'third_party'
    assert saved['data'][1]['authorship'] == 'generated'
    assert saved['data'][1]['source_authorship'] == 'third_party'


def test_read_evidence_uses_identity_bound_authorship_not_a_name_guess(vault):
    from resource_librarian import tools
    from resource_librarian.registry import REGISTRY, Context
    record = EvidenceStore(vault).put('readme', 'owned fixture', {'text': 'own bytes'},
                                      authorship='owner_created')
    out = REGISTRY.call('read_evidence', {'evidence_id': record.id}, Context(vault=vault))
    assert out['access']['sources'] == [{'handle': 'evidence:' + record.id, 'authorship': 'owner_created'}]
    assert not out['access']['taint_sources']
