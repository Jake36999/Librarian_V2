import { h } from './dom';

/** Catalogue navigation contains generated summaries, never the conversion file. */
export function renderCatalogue(data: any, openOriginal: (source: string, filename: string) => Promise<unknown>): HTMLElement {
  const status = h('p', {role:'status'});
  const original = data.original ?? {};
  const use = data.use_rollup ?? {};
  return h('section', {class:'catalogue-navigation', 'aria-label':'Source navigator'},
    h('h2', {}, 'Source navigator'),
    h('h3', {}, "When it’s relevant"), h('p', {}, data.when_relevant || 'Not recorded.'),
    h('h3', {}, 'How it’s been used'),
    h('p', {}, `${use.log_use_count ?? 0} recorded uses; ${use.application_count ?? 0} applications. Recorded history, not proof of efficacy.`),
    ...(use.recent_uses ?? []).map((row: any) => h('p', {}, String(row.used_for ?? ''))),
    ...(use.applications ?? []).map((row: any) => h('p', {}, `${row.name}: ${row.outcome || 'outcome not recorded'}`)),
    original.available ? h('button', {class: 'ghost', onclick: async () => {
      status.textContent = 'Opening the original…';
      try {await openOriginal(original.download_source, original.name); status.textContent = 'Original download requested.';}
      catch (error) {status.textContent = (error as Error).message;}
    }}, 'Open original') : h('p', {}, 'Original unavailable; catalogue only.'), status,
    h('h3', {}, 'Chapter summaries'),
    ...(data.chapters ?? []).map((chapter: any) => h('details', {},
      h('summary', {}, `${chapter.title} · ${chapter.locator ?? ''}`),
      h('p', {}, chapter.status === 'not examined' ? 'Not examined; no summary.' : `Reading coverage: ${chapter.coverage ?? 'not recorded'}. Generated summary; verify original pages.`),
      ...(chapter.summary ?? []).map((text: string) => h('p', {}, text)),
      chapter.summary_truncated ? h('p', {}, 'Summary excerpt; use the graph to locate further evidence.') : null)),
    data.chapters_truncated ? h('p', {}, `Showing ${(data.chapters ?? []).length} of ${data.chapters_total} chapters.`) : null);
}
