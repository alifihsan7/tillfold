export interface TransactionHighlightSnapshot { scope: string; maxId: number }

export function trackNewTransactions(
  previous: TransactionHighlightSnapshot | null,
  rows: readonly { id: number }[],
  scope: string,
) {
  const ids = Array.from(new Set(rows.map((row) => row.id)));
  const baseline = previous?.scope === scope ? previous : null;
  const maxId = Math.max(baseline ? baseline.maxId : 0, ...ids, 0);
  return {
    snapshot: { scope, maxId },
    newIds: baseline ? ids.filter((id) => id > baseline.maxId) : [],
  };
}
