"""Synthetic usage only: demonstrate that G5 checks its cap after a multi-call turn."""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from g5_measure import run_task
from resource_librarian.init import init
from resource_librarian.providers import Reply, Scripted, ToolCall

with tempfile.TemporaryDirectory(prefix='librarian-budget-review-') as temporary:
    root = Path(temporary)
    os.environ['LIBRARIAN_CONFIG_DIR'] = str(root / 'config')
    init(root / 'library', name='Synthetic budget fixture')
    calls = [0]

    def response(system, messages, tools):
        calls[0] += 1
        usage = {'input_tokens': 1000000, 'output_tokens': 1}
        if calls[0] <= 2:
            return Reply(tool_calls=[ToolCall(f'c{calls[0]}', 'audit_projection', {})], usage=usage)
        return Reply(text='Finished this turn.', usage=usage)

    row = run_task({'id': 'budget', 'question': 'Inspect the session', 'requirements': [
        {'requirement_id': 'R1', 'text': 'A person reviews the result', 'closure': 'human_judgment'}]},
        library=root / 'library', run_dir=root / 'run',
        route={'provider': 'deepinfra', 'model': 'scripted-lead'},
        provider_for=lambda choice: Scripted(response),
        card={'input_per_1m': 1.0, 'output_per_1m': 0.0}, budget_usd=0.1, max_turns=1)
    assert row['spend']['calls'] == 3, row
    assert row['spend']['usd'] == 3.0 and row['stopped'] == 'budget', row
    print(json.dumps({'synthetic_only': True, 'real_spend': 0,
                      'requested_cap': 0.1, 'simulated_spend': row['spend']['usd'],
                      'calls_before_stop': row['spend']['calls']}))
