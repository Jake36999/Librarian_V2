import type { Api } from './api';
import { clear, h } from './dom';

const purposes = ['own-current', 'own-legacy', 'own-docs', 'research-docs', 'third-party',
  'data', 'logs/transcripts', 'exclude'];

/** The person's second trust tier. Suggestions and drafts never accept themselves. */
export async function folderReview(api: Api, container: HTMLElement): Promise<void> {
  const out = await api.get('/api/folders');
  const status = h('p', {role:'status'});
  const source = h('input', {type:'text', 'aria-label':'Folder to survey', placeholder:'Full path to an attached source folder'}) as HTMLInputElement;
  const scan = h('button', {type:'button', disabled:!out.enabled, onclick: async () => {
    (scan as HTMLButtonElement).disabled = true; status.textContent = 'Surveying metadata…';
    try { await api.post('/api/folders/survey', {path:source.value}); await folderReview(api, container); }
    catch (e) { status.textContent = (e as Error).message; }
    finally { (scan as HTMLButtonElement).disabled = false; }
  }}, 'Survey folders');
  const refused = out.credential_refusals ?? {count:0, paths:[]};
  const selected = new Set<string>();
  const approveBatch = h('button', {type:'button', onclick: async () => {
    if (!selected.size) { status.textContent='Select folder cards first.'; return; }
    try {
      await api.post('/api/folders/approve-batch', {items:[...selected]});
      status.textContent='Exact set approved. Start the approved processing batch in Staging. Acceptance remains separate.';
    } catch(e) { status.textContent=(e as Error).message; }
  }}, 'Approve selected for processing');
  // Agent-mode orchestration: accept every unambiguous, sensitivity-checked card as suggested.
  const acceptPolicy = h('button', {type:'button', title:'Library promotion mode must be agent. Sensitive, unchecked, data and log folders stay for you.',
    onclick: async () => {
      if (!source.value.trim()) { status.textContent = 'Enter the surveyed folder first.'; return; }
      status.textContent = 'Accepting unambiguous folders…';
      try {
        const out = await api.post('/api/folders/accept-policy', {root: source.value.trim()});
        status.textContent = `Accepted ${out.accepted.length} as suggested; ${out.held.length} held for you.`;
      } catch (e) { status.textContent = (e as Error).message; }
    }}, 'Accept unambiguous folders');
  clear(container, h('h2', {}, 'Folder purposes'),
    h('p', {class:'note'}, 'Suggestions are not decisions. Accept each folder to assign its graph and access. Attached sources always remain read-only.'),
    !out.enabled ? h('p', {class:'note'}, 'Geo-Grapher is disabled. An operator can enable the pinned installed wheel for this library.') : null,
    h('div', {class:'view-head'}, source, scan, approveBatch, acceptPolicy), status,
    h('details', {}, h('summary', {}, `${refused.count} credential-like paths refused — names only`),
      h('ul', {}, (refused.paths as string[]).map(path => h('li', {}, path)))));
  const cards = h('div', {class:'folder-cards'}); container.append(cards);
  // Subfolders whose suggestion is inherited from a parent are covered by that parent's
  // decision: shown collapsed, and still individually acceptable to override one.
  const all = (out.cards ?? []) as any[];
  const covered = all.filter(c => c.inherited && c.status !== 'accepted' && !c.decision);
  const inheritedCards = h('div', {class:'folder-cards'});
  if (covered.length) container.append(h('details', {class:'inherited-folders'},
    h('summary', {}, `${covered.length} subfolders inherit their parent's suggestion — covered by the parent's decision; open to override one`),
    inheritedCards));
  for (const card of out.cards ?? []) {
    const accepted = card.status === 'accepted';
    const article = h('article', {class:'folder-card', 'aria-label':card.path});
    const include = h('input', {type:'checkbox', 'aria-label':`Include ${card.path} in processing batch`,
      disabled:accepted || card.sensitivity?.sensitivity==='review_required',
      onchange:(event:Event)=>{if((event.target as HTMLInputElement).checked)selected.add(card.id);else selected.delete(card.id);}});
    const purpose = h('select', {'aria-label':'Purpose'}, purposes.map(p => h('option', {value:p}, p))) as HTMLSelectElement;
    purpose.value = card.decision?.purpose ?? card.suggested_purpose;
    const authorship = h('select', {'aria-label':'Authorship'},
      h('option', {value:''}, 'Choose authorship'),
      ...['owner_created', 'generated', 'third_party'].map(value => h('option', {value}, value))) as HTMLSelectElement;
    const derived: Record<string, string> = {'own-current':'owner_created', 'own-legacy':'owner_created',
      'own-docs':'owner_created', 'research-docs':'third_party', 'third-party':'third_party'};
    const updateAuthorship = () => {
      authorship.value = derived[purpose.value] ?? '';
      authorship.disabled = accepted || purpose.value === 'exclude' || !!derived[purpose.value];
    };
    updateAuthorship();
    if (!derived[purpose.value] && card.decision?.authorship) authorship.value = card.decision.authorship;
    purpose.addEventListener('change', updateAuthorship);
    const graph = h('input', {type:'text', 'aria-label':'Graph', maxlength:120}) as HTMLInputElement;
    graph.value = card.decision?.graph ?? card.suggested_graph;
    const description = h('textarea', {'aria-label':'Brief description', rows:2, maxlength:400}) as HTMLTextAreaElement;
    description.value = card.decision?.description ?? card.description.text;
    const outcome = h('p', {role:'status'}, accepted ? 'Accepted by person' : card.status === 'failed' ? 'Application failed — review and retry' : 'Waiting for a person');
    const accept = h('button', {type:'button', class:'primary', disabled:accepted, onclick: async () => {
      (accept as HTMLButtonElement).disabled = true; outcome.textContent = 'Applying the reviewed decision…';
      try {
        await api.post('/api/folders/accept', {id:card.id, folder_fingerprint:card.folder_fingerprint,
          purpose:purpose.value, graph:graph.value, description:description.value,
          authorship:authorship.value || null});
        outcome.textContent = 'Accepted by person';
      } catch (e) { outcome.textContent = (e as Error).message; (accept as HTMLButtonElement).disabled = false; }
    }}, 'Accept folder decision');
    const draftStatus = h('p', {class:'note'}, accepted ? 'Person-reviewed description' :
      card.description.state === 'model_draft' ? 'Draft — not accepted' : 'Awaiting a model draft — no model called');
    const approval = h('input', {type:'checkbox', 'aria-label':'Approve one paid folder draft'}) as HTMLInputElement;
    const draft = h('button', {type:'button', disabled:accepted || !out.drafting_available, onclick: async () => {
      if (!approval.checked) { outcome.textContent = 'Approve the bounded model call first.'; return; }
      (draft as HTMLButtonElement).disabled = true;
      try {
        const updated = await api.post('/api/folders/draft', {id:card.id, approve_spend:true});
        description.value = updated.description.text; draftStatus.textContent = 'Draft — not accepted';
        outcome.textContent = 'Draft staged for your review'; approval.checked = false;
      } catch (e) { outcome.textContent = (e as Error).message; }
      finally { (draft as HTMLButtonElement).disabled = accepted || !out.drafting_available; }
    }}, 'Draft from inventory metadata');
    article.append(h('h3', {}, card.path), h('label', {}, include, ' Include in processing batch'),
      h('p', {class:'dim'}, card.source_root),
      h('p', {class:'note'}, 'Inventory metadata observed; content not examined.'),
      h('p', {}, `${card.bytes.toLocaleString()} bytes · ` + Object.entries(card.file_counts).map(([kind, n]) => `${kind}: ${n}`).join(' · ')),
      h('p', {class:'note'}, (card.reasons as string[]).join('; ')),
      h('label', {}, 'Purpose ', purpose), h('label', {}, 'Authorship ', authorship),
      h('label', {}, 'Graph ', graph), draftStatus,
      h('label', {}, 'Brief description ', description),
      h('details', {}, h('summary', {}, 'Optional model draft'),
        h('p', {}, 'Production drafting is disabled pending owner approval of a qualified Clerk. Drafting checks inventory arithmetic and sensitivity; source text is never sent.'),
        h('label', {}, approval, ' Approve one paid folder draft'), draft), outcome, accept);
    (covered.includes(card) ? inheritedCards : cards).append(article);
  }
  if (!(out.cards ?? []).length) container.append(h('p', {class:'dim'}, 'No folder cards yet. Survey an attached content root to stage its suggestions.'));
}
