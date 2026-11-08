"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { trackNewTransactions, TransactionHighlightSnapshot } from "./newTransactionHighlight";

export function useTransactionHighlights() {
  const previous = useRef<TransactionHighlightSnapshot | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [newIds, setNewIds] = useState<ReadonlySet<number>>(new Set());

  const observe = useCallback((rows: readonly { id: number }[], scope: string) => {
    const changedScope = previous.current?.scope !== scope;
    const next = trackNewTransactions(previous.current, rows, scope);
    previous.current = next.snapshot;
    if (!changedScope && next.newIds.length === 0) return;
    if (timer.current !== null) clearTimeout(timer.current);
    setNewIds(new Set(next.newIds));
    if (next.newIds.length > 0) {
      timer.current = setTimeout(() => { setNewIds(new Set()); timer.current = null; }, 2400);
    } else timer.current = null;
  }, []);

  useEffect(() => () => { if (timer.current !== null) clearTimeout(timer.current); }, []);
  return { newIds, observe };
}
