"""Production code research uses the same route settings as its evaluations."""
import pytest
from resource_librarian.agent_runtime import AgentProfile, DEFAULT_PROFILES
from resource_librarian.loop import Loop
from resource_librarian.providers import Provider, Reply

class Capture(Provider):
    name='capture'
    def __init__(self):self.calls=[]
    def chat(self,system,messages,tools,max_tokens=4096,temperature=None):
        self.calls.append(dict(temperature=temperature,tools=tools))
        return Reply(text='Source-grounded answer.')

def test_code_research_profile_sends_production_temperature(vault):
    profile=DEFAULT_PROFILES['code-research'].validate()
    assert profile.role=='lead' and profile.route_policy['temperature']==0.2
    provider=Capture();loop=Loop(vault,provider,scribe=None,extras={'use_tool_bundles':False})
    loop.configure_profile(profile)
    assert loop.send('Explain the inspected code.').reply
    assert provider.calls[0]['temperature']==0.2

def test_other_profile_retains_provider_sampling_default(vault):
    provider=Capture();loop=Loop(vault,provider,scribe=None,extras={'use_tool_bundles':False})
    loop.configure_profile(DEFAULT_PROFILES['lead'])
    loop.send('hello')
    assert provider.calls[0]['temperature'] is None

@pytest.mark.parametrize('value',[True,-0.1,2.1,float('nan'),float('inf'),'0.2'])
def test_malformed_sampling_policy_is_refused(value):
    with pytest.raises(ValueError,match='temperature'):
        AgentProfile('bad','lead',route_policy={'temperature':value}).validate()
