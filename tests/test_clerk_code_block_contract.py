import json
import pytest
from resource_librarian import clerk


def packet():
    return dict(packet_version='task-packet-v1', instruction='Describe ports.', snapshot_id='s1',
        anchors=[dict(ref='entity:f',cite_as='code/entity:f',text='def f(x): return x')], boundary=[],
        handles=['code/entity:f'], upstream=[dict(task_id='t0',ref='entity:f',cite='code/entity:f',
            inputs=[dict(name='x',cite='code/entity:f')],outputs=[],origin='model_produced_citation_verified')])


def answer(cite='code/entity:f'):
    return dict(inputs=[dict(name='x',cite=cite)],outputs=[],calls=[],claims=[],not_determinable=[])


def test_payload_stays_unframed_with_exact_upstream_rows():
    p = packet(); p.update(session='secret session', brief='secret brief')
    task = clerk.code_block_contract(p)
    payload = task.payload()
    assert set(payload) == clerk.PAYLOAD_KEYS
    assert 'secret' not in json.dumps(payload)
    rows = json.loads(task.chunk)
    assert set(rows) == {'anchors','boundary','upstream'}
    assert rows['upstream'] == [{k:v for k,v in p['upstream'][0].items() if k != 'task_id'}]
    assert task.question == p['instruction']
    assert task.kind.schema['additionalProperties'] is False


def test_citation_verification_is_bounded_not_semantic():
    from resource_librarian.packet_checks import verify_citations
    from resource_librarian.closure import VERIFIERS
    assert verify_citations(answer(), packet()) == dict(verified=['inputs[0].cite'],unverified=[],closure_strength='bounded')
    bad = verify_citations(answer('elsewhere/ghost'), packet())
    assert bad['unverified'] == ['inputs[0].cite'] and bad['closure_strength'] == 'none'
    assert VERIFIERS['packet.citation_resolves'].max_strength == 'bounded'


@pytest.mark.parametrize('bad',[None, {}, {'inputs':'wrong'},
    dict(inputs=[dict(name=5,cite='code/entity:f')],outputs=[],calls=[],claims=[],not_determinable=[]),
    dict(inputs=[dict(name='x',cite={})],outputs=[],calls=[],claims=[],not_determinable=[]),
    dict(inputs=[],outputs=[],calls=[],claims=[],not_determinable='wrong')])
def test_malformed_answer_cannot_close(bad):
    from resource_librarian.packet_checks import verify_citations
    assert verify_citations(bad,packet())['closure_strength'] == 'none'


def test_clerk_only_accepts_task_packets():
    with pytest.raises(ValueError):
        clerk.code_block_contract({'instruction':'x'})


def test_registered_grain_has_a_bound_check_and_rejects_substitution():
    from resource_librarian import closure,research_grains
    from resource_librarian.packet_checks import content_sha256
    p,a=packet(),answer()
    params=dict(packet=p,answer=a,packet_sha256=content_sha256(p),answer_sha256=content_sha256(a))
    check=research_grains.run('packet.citation_resolves',None,params)
    assert check.outcome=='pass' and check.strength=='bounded'
    assert not closure.unbound_subject('packet.citation_resolves',params,params)
    params['answer']=answer('elsewhere/ghost')
    assert research_grains.run('packet.citation_resolves',None,params).outcome=='fail'
    assert closure.unbound_subject('packet.citation_resolves',{'packet_sha256':'different'},params)
