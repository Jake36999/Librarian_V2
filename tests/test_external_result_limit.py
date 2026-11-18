import json
from types import SimpleNamespace
import pytest
from resource_librarian.mcp_client import McpManager
from resource_librarian.registry import Context


@pytest.mark.parametrize('window,expected', [(None,24000),(131072,24000),(200000,24000),(1048576,125829),(10000000,160000)])
def test_formula(window, expected):
    from resource_librarian.mcp_client import external_result_limit
    assert external_result_limit(window) == expected


def manager_for(tmp_path, result):
    m = McpManager(tmp_path)
    m.set_server('geo',{'command':'fixture','args':[]})
    m.accept('geo')
    m._clients['geo'] = SimpleNamespace(call_tool=lambda *a: result)
    m._portal = SimpleNamespace(call=lambda fn,*a: fn(*a))
    return m


def test_structured_withholding_is_atomic_and_route_aware(tmp_path):
    result = SimpleNamespace(structuredContent={'text':'x'*9000},isError=False)
    m = manager_for(tmp_path, result)
    small = m.call_tool('geo','packet',{},limit_chars=8000)
    assert small['structured_result_withheld']
    assert json.loads(small['content'])['error']['limit_characters'] == 8000
    large = m.call_tool('geo','packet',{},limit_chars=125829)
    assert json.loads(large['content']) == result.structuredContent
    assert not large.get('truncated')


def test_text_clipped_and_registered_callable_uses_context_limit(tmp_path):
    m = manager_for(tmp_path, SimpleNamespace(content=[SimpleNamespace(type='text',text='x'*9000)],isError=False))
    assert m.call_tool('geo','text',{},limit_chars=8000)['truncated']
    fn = m._make_fn('geo','text')
    assert not fn(Context(extras={'external_result_limit':125829})).get('truncated')


def test_revoked_server_cannot_dispatch_even_before_sync(tmp_path):
    m=manager_for(tmp_path,SimpleNamespace(structuredContent={'secret':'old'},isError=False))
    m.set_server('geo',{'command':'fixture','args':[],'enabled':False})
    assert m.call_tool('geo','packet',{})['error']=='access_changed'


def test_revocation_during_call_withholds_the_returned_payload(tmp_path):
    m=manager_for(tmp_path,SimpleNamespace(structuredContent={'secret':'old'},isError=False))
    def call(fn,*args):
        m.set_server('geo',{'command':'fixture','args':[],'enabled':False})
        return fn(*args)
    m._portal=SimpleNamespace(call=call)
    out=m.call_tool('geo','packet',{})
    assert out['error']=='access_changed' and 'old' not in json.dumps(out)


def test_library_switch_during_call_withholds_result(tmp_path,monkeypatch):
    m=manager_for(tmp_path,SimpleNamespace(structuredContent={'secret':'old'},isError=False))
    current=[tmp_path/'a']
    monkeypatch.setattr(m,'_library_file',lambda:current[0])
    monkeypatch.setattr(m,'enabled_here',lambda _:True)
    def call(fn,*args):
        current[0]=tmp_path/'b'
        return fn(*args)
    m._portal=SimpleNamespace(call=call)
    assert m.call_tool('geo','packet',{})['error']=='access_changed'
