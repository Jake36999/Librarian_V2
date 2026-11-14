"""External local JSON references must preserve request object identity and shape."""
from resource_librarian.registry import REGISTRY,ToolSpec,Card,Context
import pytest


def spec(ref='#/$defs/Request', defs=None):
    return ToolSpec(name='mcp__refs__query', fn=lambda ctx,**args:args, tier='contribute',
        effect='read', card=Card('fixture'), needs_vault=False,external=True,
        schema={'type':'object','properties':{'request':{'$ref':ref}},'required':['request'],
                '$defs':defs or {'Request':{'type':'object','properties':{'query':{'type':'string'}}}}})


@pytest.mark.parametrize('value',[{'query':'clerk'},'{"query":"clerk"}'])
def test_referenced_object_is_an_object_on_the_wire(value):
    item=spec();REGISTRY.register(item)
    try:
        out=REGISTRY.call(item.name,{'request':value},Context(tier='contribute'))
        assert out['request']=={'query':'clerk'}
    finally:REGISTRY.unregister(item.name)


@pytest.mark.parametrize('ref,defs',[('https://example.com/schema',None),('#/$defs/Missing',None),
    ('#/$defs/A',{'A':{'$ref':'#/$defs/B'},'B':{'$ref':'#/$defs/A'}})])
def test_invalid_external_and_cyclic_refs_are_refused(ref,defs):
    item=spec(ref,defs);REGISTRY.register(item)
    try:
        out=REGISTRY.call(item.name,{'request':{'query':'clerk'}},Context(tier='contribute'))
        assert out.get('error') and 'SCHEMA_REF' in out.get('detail','')
    finally:REGISTRY.unregister(item.name)
