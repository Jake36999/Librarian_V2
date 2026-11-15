// Model picker ordering (owner, 2026-11-14). Recommendation only: nothing is selected.
//
// 1. Models whose profile suggests the slot's tier come first.
// 2. Within those, an evidence `recommendation_rank` (lower first) leads; unranked follow.
// 3. Otherwise the catalogue's own order is kept. A rank never lifts a model outside its tier.

export function orderModels<T extends { profile?: any }>(models: T[], slot: number): T[] {
  const recommended = (m: T) => slot > 0 && String(m.profile?.suggested_tier ?? "") === `Tier_${slot}`;
  const rank = (m: T) => {
    const r = m.profile?.recommendation_rank;
    return recommended(m) && Number.isInteger(r) && r > 0 ? r : Number.POSITIVE_INFINITY;
  };
  return models
    .map((m, i) => ({ m, i }))
    .sort((a, b) => Number(recommended(b.m)) - Number(recommended(a.m))
      || rank(a.m) - rank(b.m) || a.i - b.i)
    .map(({ m }) => m);
}
