export type PocketTone = "safe" | "warning" | "danger" | "neutral";

export interface PocketStatusResult {
  label: string;
  tone: PocketTone;
  percentage: number | null;
}

/**
 * Logika status kantong berbasis Saldo Kas Riil (Sub-Account) & Kecukupan Saldo.
 *
 * @param balance - Saldo kas riil saat ini
 * @param target - Target komitmen tagihan / sinking fund (0 jika kantong bebas)
 * @param isFreePocket - True jika kantong merupakan unallocated pool / kas bebas (cth: Kantong Utama)
 */
export function getPocketStatus(
  balance: number,
  target: number = 0,
  isFreePocket: boolean | number = false
): PocketStatusResult {
  // Dukungan backward compatibility jika dipanggil dengan tanda tangan lama (target, spent, remaining)
  let actualBalance = balance;
  let actualTarget = target;
  let isFree = false;

  if (typeof isFreePocket === "number") {
    // Dipanggil sebagai (target, spent, remaining)
    actualTarget = balance;
    actualBalance = isFreePocket;
    isFree = actualTarget <= 0;
  } else {
    isFree = Boolean(isFreePocket) || actualTarget <= 0;
  }

  // 1. Saldo negatif (anomali kas)
  if (actualBalance < 0) {
    return {
      label: "Saldo Negatif",
      tone: "danger",
      percentage: null,
    };
  }

  // 2. Kantong bebas / unallocated pool tanpa komitmen target
  if (isFree) {
    if (actualBalance > 0) {
      return {
        label: "Kas Siap Pakai",
        tone: "safe",
        percentage: null,
      };
    }
    return {
      label: "Saldo Kosong",
      tone: "neutral",
      percentage: null,
    };
  }

  // 3. Kantong bertarget (tagihan rutin / sinking fund)
  const percentage = Math.min(100, Math.max(0, Math.round((actualBalance / actualTarget) * 100)));

  if (actualBalance >= actualTarget) {
    return {
      label: "Target Terpenuhi",
      tone: "safe",
      percentage,
    };
  }

  if (actualBalance > 0) {
    return {
      label: "Mengisi",
      tone: "warning",
      percentage,
    };
  }

  return {
    label: "Belum Terisi",
    tone: "neutral",
    percentage: 0,
  };
}
