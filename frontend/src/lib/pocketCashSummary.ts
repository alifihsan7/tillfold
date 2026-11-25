import type { PocketItem } from "./api";

/** The summary's allocation_amount is computed funding, not the stored allocation.
 * Use the server's cash classification; retain the old slug convention only for older APIs. */
export function summarizePocketCash(pockets: PocketItem[]) {
  const freePocket = pockets.find((pocket) => pocket.uses_unallocated_cash === true)
    ?? pockets.find((pocket) => pocket.uses_unallocated_cash == null && (pocket.role ?? "operasional") === "operasional" && (pocket.slug === "utama" || pocket.slug.startsWith("utama-")));
  const allocatedPockets = pockets.filter((pocket) => pocket !== freePocket);
  return {
    freePocket,
    freeBalance: freePocket?.balance ?? freePocket?.remaining_amount ?? 0,
    allocatedPockets,
    allocatedBalance: allocatedPockets.reduce((total, pocket) => total + (pocket.balance ?? pocket.remaining_amount ?? 0), 0),
  };
}
