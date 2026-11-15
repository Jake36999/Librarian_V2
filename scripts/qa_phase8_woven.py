"""Free S6 walkthrough: real text PDF, installed Geo wheel, native Core and browser.

All state is new QA state under the explicitly supplied G: output directory.
No provider is bound or called. Existing libraries and catalogs are untouched.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--wheel',type=Path,required=True)
    args=parser.parse_args()
    base=args.out.resolve()
    if base.exists() or not base.is_relative_to(Path('G:/Libraries/_qa').resolve()):
        raise SystemExit('Use a fresh explicit QA output under G:/Libraries/_qa')
    base.mkdir(parents=True)
    for key in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','DEEPINFRA_API_KEY','OPENROUTER_API_KEY'):
        os.environ.pop(key,None)
    os.environ['LIBRARIAN_CONFIG_DIR']=str(base/'config')
    os.environ['UV_OFFLINE']='true'
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
    from conftest import pdf_bytes
    from pypdf import PdfReader
    from resource_librarian import dik,notes,tools  # noqa: F401
    from resource_librarian.init import init
    from resource_librarian.vault import Vault
    from resource_librarian.folder_review import FolderReview
    from resource_librarian.conversions import ConversionStore,file_sha256
    from resource_librarian.batch import _parse
    from resource_librarian.registry import Context,REGISTRY
    from resource_librarian.session import SessionStore
    from resource_librarian.mcp_client import McpManager
    from resource_librarian.app import App,build
    from resource_librarian.keys import KeyStore
    from resource_librarian.search import search,Engine
    init(base/'Fixture Library',name='Phase 8 Woven Fixture')
    vault=Vault(base/'Fixture Library')
    own=base/'Owner Documents'; own.mkdir()
    (own/'Guide.md').write_text('# Own operations\n\n'+('Opening material.\n'*250)+'\nUltravioletflux procedure at the end.',encoding='utf-8')
    (own/'settings.py').write_text('SAFE_LIMIT = 42\n',encoding='utf-8')
    external=base/'Third Party Papers';external.mkdir()
    pdf=external/'Study.pdf'
    pdf.write_bytes(pdf_bytes([['Introduction','Opening context only.'],
        ['Method','The target fixture measurement is seven units.'],['Appendix','A late detail beyond the catalogue.']]))
    hashes={str(p):file_sha256(p) for root in (own,external) for p in root.iterdir()}
    command=['uvx','--from',str(args.wheel.resolve()),'geographer']
    (vault.librarian/'geographer.json').write_text(json.dumps(dict(enabled=True,command=command,wheel_version='0.2.0')))
    review=FolderReview(vault)
    accepted=[]
    for root,purpose,label in ((own,'own-docs','fixture-own'),(external,'research-docs','fixture-papers')):
        result=review.survey(root)
        card=next(c for c in result['cards'] if c['path']=='.')
        accepted.append(review.accept(card['id'],card['folder_fingerprint'],purpose=purpose,graph=label,
            person=True,description='Person-reviewed fixture inventory; content not examined.'))
    pages=[p.extract_text().strip() for p in PdfReader(pdf).pages]
    converted=ConversionStore(vault).save(ConversionStore(vault).request(pdf,'free-pypdf-text-layer:fixture-v1'),
        '\n\n'.join(f'[page {n}]\n# {text}' for n,text in enumerate(pages,1)),pages=len(pages))
    item=dict(name='Fixture Study',title='Fixture Study',source_kind='paper',file=str(pdf),clean_file=converted['path'])
    publication=_parse(Context(vault=vault,tier='contribute'),item)['paper_graph']
    assert publication['publication']['published'],publication
    source=vault.root/'Sources/paper/Fixture Study.md';source.parent.mkdir(parents=True,exist_ok=True)
    source.write_text(notes.render(dict(type='source',kind='paper',authorship='generated',title='Fixture Study',
        file=str(pdf),when_relevant='Locate the fixture measurement in its original pages.',graph_label='fixture-papers',
        status='active'), '# Fixture Study\n\n## Bottom Line\nA catalogue pointer; no full paper text.\n'),encoding='utf-8')
    dik.save(vault,dik.document(vault,'Fixture Study',pages,[],[],'fixture-full-conversion'))
    sid=SessionStore(vault).new('explore',question='Locate the fixture measurement.').id
    SessionStore(vault).append(sid,dict(type='use',source='Fixture Study',used_for='Locate an original measurement.'))
    manager=McpManager(base/'mcp')
    manager.set_server('fixture_geo',dict(command=command[0],args=[*command[1:],'serve-graphs',
        '--catalog',str(vault.librarian/'geographer/catalog.sqlite'),'--transport','stdio','--tools','papers',
        '--max-result-chars','7500'],env={'UV_OFFLINE':'true','UV_CACHE_DIR':os.environ['UV_CACHE_DIR']},
        provenance_authority='geographer',enabled=True))
    manager.accept('fixture_geo')
    manager.use_library(vault.librarian)
    manager.set_library_enabled('fixture_geo',True)
    status=manager.sync()
    assert status['fixture_geo']['connected'],status
    app=App(vault,token='phase8-woven-fixture-token',keys=KeyStore(use_keyring=False),
            provider_for=lambda _:None,mcp=manager,coordinate=True)
    server=None
    report=dict(model_calls=0,spend_usd=0,wheel=str(args.wheel.resolve()),wheel_sha256=file_sha256(args.wheel),
        vault=str(vault.root),own_root=str(own),third_party_root=str(external),accepted_cards=accepted,publication=publication)
    try:
        app.index_service.refresh()
        route=dict(model='scripted-no-dispatch',context_tokens=262144,prompt_tokens=1000,
                   visible_output_tokens=4096,reasoning_reserve_tokens=0)
        ctx=Context(vault=vault,tier='contribute',session=sid,extras=dict(index_service=app.index_service,
            vault_writer=app.writer,mcp=manager,read_route=route,agent_tier=1,helper_read_route=lambda tier:dict(route)))
        owned=app.index_service.run(lambda index:search(Engine(index),'Ultravioletflux','workspace').to_dict())
        assert owned['results'],owned
        raw=app.index_service.run(lambda index:search(Engine(index),'seven units','all').to_dict())
        assert not raw['results'],raw
        report['own_document']=owned['results'][0]['name']
        report['native_raw_third_party_hits']=len(raw['results'])
        report['catalogue']=REGISTRY.call('get_note',{'name':'Fixture Study'},ctx)
        def call(name,arguments):
            out=REGISTRY.call('mcp__fixture_geo__'+name,arguments,ctx)
            assert not out.get('error') and not out.get('is_error'),out
            return json.loads(out['content'])
        report['graph_list']=call('list_graphs',{})
        report['graph_search']=call('paper_search_documents',dict(graph_id='fixture-papers',request={'query':'fixture'}))
        report['graph_document']=call('paper_get_document',dict(graph_id='fixture-papers',request={'title':'doc:1','detail':'full'}))
        document=report['graph_document'].get('result',report['graph_document'])
        section=next(r for r in document['sections'] if 'Method' in r['heading'])
        report['graph_section']=call('paper_get_section',dict(graph_id='fixture-papers',request={
            'title':'doc:1','section_id':section['id'],'max_chars':500}))
        report['original_verification']=REGISTRY.call('verify_source_pages',dict(source=str(pdf),pages=[2],
            claim='The target fixture measurement is seven units.'),ctx)
        assert report['original_verification']['literal_quote_present'] is True,report['original_verification']
        report['source_plan']=REGISTRY.call('source_verification_plan',dict(source=str(pdf),
            claim='The target fixture measurement is seven units.',graph_id='fixture-papers',document='doc:1',
            section_id=section['id'],tier=2,server='fixture_geo'),ctx)
        report['source_plan_dry_run']=REGISTRY.call('dispatch_plan',dict(plan=report['source_plan']['plan'],dry_run=True),ctx)
        assert report['source_plan_dry_run']['dry_run'] is True,report['source_plan_dry_run']
        report['publication_refusal']=REGISTRY.call('write_note',dict(folder='Notes',name='Must Not Publish',
            body='Derived fixture prose.',mode='create'),ctx)
        assert report['publication_refusal'].get('refused')=='COMPOSITION_REFUSED',report['publication_refusal']
        assert not (vault.root/'Notes/Must Not Publish.md').exists()
        assert hashes=={str(p):file_sha256(p) for root in (own,external) for p in root.iterdir()}
        server=build(app,0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        report['url']=f'http://127.0.0.1:{server.server_address[1]}/'
        (base/'fixture-ready.json').write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
        script=Path(__file__).resolve().parents[1]/'ui/phase8-woven-smoke.mjs'
        done=subprocess.run(['node',str(script),str(base)],cwd=script.parent,capture_output=True,text=True)
        (base/'browser-first.txt').write_text(done.stdout+'\n'+done.stderr,encoding='utf-8')
        assert done.returncode==0,done.stdout+'\n'+done.stderr
        report['browser']=json.loads((base/'browser-result.json').read_text())
        report['source_bytes_unchanged']=True
        (base/'result.json').write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
        print(json.dumps(dict(passed=True,model_calls=0,out=str(base),browser=report['browser'])),flush=True)
    finally:
        if server:
            server.shutdown();server.server_close()
        app.close_runtime()
        manager.stop()


if __name__=='__main__':
    main()
