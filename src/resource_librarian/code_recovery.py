"""Bounded code-research workflows driven only by delivered structured evidence."""
from __future__ import annotations
from collections import Counter
from copy import deepcopy
import json
import re
import uuid

PATTERNS=frozenset('FP'+str(n) for n in range(1,9))
STOP=frozenset('a an and are as at be by can cite code constant defines documented does for from function how identifier implementation in is it method named of on or please sets source that the this to what when where which why with you your'.split())


def words(text):
    text=re.sub(r'(?<=[a-z0-9])(?=[A-Z])|[_./]+',' ',text)
    return {x for x in re.findall(r'\w+',text.casefold()) if len(x)>2 and x not in STOP and not x.isdigit()}


def body_of(result):
    if not isinstance(result,dict):return {}
    text=result.get('content')
    if isinstance(text,str):
        try:value=json.loads(text)
        except (ValueError,TypeError):return {}
        return value if isinstance(value,dict) else {}
    return result


def rows(value,limit):return value[:limit] if isinstance(value,list) else []


def mapping(value):return value if isinstance(value,dict) else {}


class RecoveryEpisode:
    def __init__(self,question,*,self_check=False):
        if not isinstance(question,str) or not question.strip():raise ValueError('A code-research question is required')
        self.question=question[:10000];self.self_check=self_check;self.episode_id=uuid.uuid4().hex
        self.records={};self.steps={};self.model_steps=set();self.extra_steps=0;self.extra_model_calls=0
        self.candidates=[];self.opened={};self.pending=[];self.handles=set();self.ids=set();self.ranges=[]
        self.tool_counts=Counter();self.errors=Counter();self.revision_done=False;self.revision_rejected=''
        self.first_attempt={};self.mode='defer';self.adjacencies=[]

    @property
    def remaining(self):return 3-self.extra_steps

    def begin(self,pattern,trigger_value,action):
        if pattern not in PATTERNS or pattern in self.records:return False
        self.records[pattern]=dict(pattern=pattern,trigger_value=deepcopy(trigger_value),action=action,outcome='unresolved',step_ids=[])
        return True

    def claim(self,step_id,*,patterns=(),model=False):
        if step_id in self.steps or self.remaining<=0 or model and self.extra_model_calls>=2:return False
        if any(p not in self.records for p in patterns):return False
        self.steps[step_id]=list(patterns);self.extra_steps+=1
        if model:self.model_steps.add(step_id);self.extra_model_calls+=1
        for p in patterns:self.records[p]['step_ids'].append(step_id)
        return True

    def finish(self,patterns,resolved):
        for p in patterns:
            if p in self.records:self.records[p]['outcome']='resolved' if resolved else 'unresolved'

    def metadata(self):
        return {'geographer/recovery':dict(episode_id=self.episode_id,question=self.question,mode=self.mode,
            remaining_steps=self.remaining,used_patterns=sorted(self.records))}

    def external(self,name,body):
        rows=body.get('recoveries',[])
        if not isinstance(rows,list):return
        server=name.rsplit('__',1)[0]
        grouped={}
        for row in rows[:8]:
            if not isinstance(row,dict) or not isinstance(row.get('pattern'),str) or row.get('pattern') not in {'FP1','FP2','FP6'} or not isinstance(row.get('outcome'),str) or row.get('outcome') not in {'resolved','unresolved'}:continue
            p=row['pattern'];action=row.get('action');trigger=row.get('trigger_value')
            if not isinstance(action,str) or not isinstance(trigger,dict) or len(json.dumps(trigger,default=str))>2000:continue
            step=str(row.get('step_id',''))[:100]
            charged=row.get('extra_steps',0 if p=='FP6' else 1)
            if charged not in (0,1):continue
            global_step='external:'+server+':'+step
            if charged and p in self.records and self.records[p]['step_ids'] and global_step not in self.steps:
                raise ValueError('External recovery repeated an episode pattern')
            if p not in self.records:self.begin(p,trigger,action[:100])
            self.records[p]['outcome']=row['outcome']
            if charged and step:grouped.setdefault(global_step,[]).append(p)
        for step,patterns in grouped.items():
            if step not in self.steps and not self.claim(step,patterns=patterns):
                raise ValueError('External recovery exceeded the shared three-step budget')

    def observe(self,name,arguments,result):
        self.tool_counts[name.rsplit('__',1)[-1]]+=1
        body=body_of(result);self.external(name,body)
        error=body.get('error')
        if error:
            self.errors[str(error.get('code','error') if isinstance(error,dict) else error)[:80]]+=1
            return
        data=body.get('result',{}).get('data',{}) if isinstance(body.get('result',{}),dict) else {}
        if not isinstance(data,dict):return
        nodes={n['entity_id']:n for n in rows(data.get('nodes'),50) if isinstance(n,dict) and isinstance(n.get('entity_id'),str)}
        refs={n['entity_id']:n for n in rows(body.get('entities'),50) if isinstance(n,dict) and isinstance(n.get('entity_id'),str)}
        for eid,node in nodes.items():
            self.ids.add(eid)
            for row in (node,refs.get(eid,{})):
                if isinstance(row.get('cite_as'),str):self.handles.add(row['cite_as'])
        graph=body.get('graph_id',arguments.get('graph_id',''));server=name.rsplit('__',1)[0]
        if not isinstance(graph,str):return
        if name.endswith('__search_entities'):
            for rank,hit in enumerate(rows(data.get('hits'),3),1):
                node=nodes.get(hit.get('entity_id')) if isinstance(hit,dict) else None
                if node:
                    self.candidates.append(dict(node={**node,**refs.get(node['entity_id'],{})},server=server,graph=graph,
                        arguments={'graph_id':arguments.get('graph_id',graph),'entity_id':node['entity_id']},tool=server+'__get_entity_content',rank=rank,sequence=self.tool_counts['search_entities']))
            pending=body.get('recovery_pending',[])
            if isinstance(pending,list) and any(isinstance(r,dict) and r.get('pattern') in {'FP1','FP2'} for r in pending):
                self.pending.append(dict(tool=name,arguments=deepcopy(arguments),patterns=[r['pattern'] for r in pending if isinstance(r,dict) and r.get('pattern') in {'FP1','FP2'}]))
        if name.endswith('__get_entity_content'):
            for coverage in rows(body.get('coverage'),16):
                if not isinstance(coverage,dict):continue
                eid=coverage.get('entity_id');a=coverage.get('start_line');b=coverage.get('end_line');node=nodes.get(eid)
                if not node or type(a) is not int or type(b) is not int or not 0<a<=b:continue
                source=mapping(node.get('source'));line=source.get('start_line')
                self.ranges.append((source.get('rel_path',''),a,b))
                if type(line) is int and a<=line<=b:self.opened[(server,graph,eid)]=node
            focus=nodes.get(data.get('entity_id'),{})
            for card in rows(data.get('calls_constants'),8):
                if isinstance(card,dict) and focus.get('qualified_name') and card.get('qualified_name'):
                    self.adjacencies.append((focus['qualified_name'],card['qualified_name']))
            for chunk in rows(data.get('chunks'),16):
                if isinstance(chunk,dict) and chunk.get('enclosing_function') and focus.get('kind')=='constant':
                    self.adjacencies.append((chunk['enclosing_function'],focus.get('qualified_name','')))

    def overlap(self,node):
        summary=mapping(node.get('summary'))
        return len(words(self.question)&words(str(summary.get('doc_gist') or '')+' '+str(summary.get('why') or '')))

    @staticmethod
    def named(answer,name):
        if not isinstance(name,str):return False
        short=name.rsplit('.',1)[-1]
        return bool(short and re.search(r'(?<![\w])'+re.escape(short)+r'(?![\w])',answer))

    def cited(self,answer,node):
        source=mapping(node.get('source'))
        refs=[node.get('cite_as'),node.get('entity_id')]
        if source.get('rel_path') and source.get('start_line'):refs.append(f"{source['rel_path']}:{source['start_line']}")
        return any(isinstance(ref,str) and ref and ref in answer for ref in refs)

    def candidate(self,answer,offered):
        relevant=[c for c in self.candidates if self.overlap(c['node'])>=2]
        if any(self.cited(answer,c['node']) for c in relevant):return None
        if not relevant:return None
        chosen=min(relevant,key=lambda c:(-c['sequence'],c['rank'],c['node']['entity_id']))
        if (chosen['server'],chosen['graph'],chosen['node']['entity_id']) in self.opened or chosen['tool'] not in offered:return None
        return chosen

    def missing_definitions(self,answer):
        return [n for n in self.opened.values() if self.overlap(n)>=2 and not self.named(answer,n.get('qualified_name',''))]

    def granularity_gaps(self,answer):
        ask_constant=bool(re.search(r'\bconstant\b',self.question,re.I))
        ask_function=bool(re.search(r'\b(function|method|implementation)\b',self.question,re.I))
        return [dict(function=f,constant=c) for f,c in self.adjacencies if
            ask_constant and self.named(answer,f) and not self.named(answer,c) or
            ask_function and self.named(answer,c) and not self.named(answer,f)]

    def validate_revision(self,answer):
        if not isinstance(answer,str) or not answer.strip():return False
        remainder=answer
        for handle in sorted(self.handles,key=len,reverse=True):
            remainder=re.sub(r'(?<![\w./-])'+re.escape(handle)+r'(?![\w])','',remainder)
        if re.search(r'[\w.-]+/entity:(?:entity:)?[A-Za-z0-9_-]+',remainder):return False
        for eid in sorted(self.ids,key=len,reverse=True):remainder=remainder.replace(eid,'')
        if re.search(r'entity:[A-Za-z0-9_-]+',remainder):return False
        for path,line in re.findall(r'((?:[\w.-]+[/\\])*[\w.-]+\.(?:py|js|ts|tsx|jsx|md|sql|yaml|yml)):(\d+)',answer):
            if not any((path==p or p.endswith('/'+path)) and a<=int(line)<=b for p,a,b in self.ranges):return False
        return True

    def checkpoint(self,answer):
        if answer.strip() and not self.first_attempt:self.first_attempt=dict(answer=answer,status='produced_after_early_recovery' if self.records else 'unrecovered_draft')

    def receipts(self):return deepcopy(list(self.records.values()))
