"""Disposable browser fixture; no credentials and no model/network calls."""
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from walks import library
from resource_librarian.app import App, build
from resource_librarian.keys import KeyStore
from resource_librarian.folder_review import FolderReview

base = Path(tempfile.mkdtemp(prefix='folder-browser-'))
os.environ['LIBRARIAN_CONFIG_DIR'] = str(base / 'config')
for name in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'DEEPINFRA_API_KEY', 'OPENROUTER_API_KEY'):
    os.environ.pop(name, None)
vault = library(base / 'Wave L Fixture')
source = base / 'Attached Sources'
for name, text in [('src/processor.py', 'def process(value):\n    return value + 1\n'),
                   ('third_party_alpha/reference.py', 'def reference(value):\n    return value\n'),
                   ('third_party_beta/reference.py', 'def reference(value):\n    return value\n'),
                   ('docs/guide.md', '# Fixture guide\n'), ('Frank.env', 'synthetic refused fixture')]:
    path = source / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text)
config = dict(enabled=True, command=[os.environ['WAVE_L_WHEEL_PYTHON'], '-I', '-m', 'geographer'], wheel_version='0.2.0')
(vault.librarian / 'geographer.json').write_text(json.dumps(config))
cards = FolderReview(vault).survey(source)['cards']
# The screenshot demonstrates a staged draft, not a claim that a paid model was run.
from resource_librarian.staging import StagingStore
for card in cards:
    card['description'] = dict(state='model_draft', draft=True,
        text='Scripted QA draft: folder inventory for review (no model call).')
    StagingStore(vault).save(card)
app = App(vault, token='synthetic-qa-token', keys=KeyStore(use_keyring=False), provider_for=lambda _: None)
server = build(app, 0)
print(json.dumps(dict(url=f'http://127.0.0.1:{server.server_address[1]}/', source=str(source),
                     vault=str(vault.root))), flush=True)
server.serve_forever()
