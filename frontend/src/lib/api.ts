export interface UserProfile {
  id: number;
  username: string;
  email: string | null;
  full_name: string;
  telegram_chat_id: number | null;
  telegram_bot_username?: string | null;
  telegram_mode?: "shared" | "custom" | null;
  google_spreadsheet_id?: string | null;
  avatar_url?: string | null;
  is_active: boolean;
  is_onboarded: boolean;
  created_at?: string;
}

export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("ai7_token");
}

export function setAuthToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) {
    localStorage.setItem("ai7_token", token);
  } else {
    localStorage.removeItem("ai7_token");
  }
}

export function getStoredUser(): UserProfile | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem("ai7_user");
  if (!raw) return null;
  try {
    return JSON.parse(raw) as UserProfile;
  } catch {
    return null;
  }
}

export function setStoredUser(user: UserProfile | null) {
  if (typeof window === "undefined") return;
  if (user) {
    localStorage.setItem("ai7_user", JSON.stringify(user));
  } else {
    localStorage.removeItem("ai7_user");
  }
}

export async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const token = getAuthToken();
  const headers = new Headers(options.headers || {});
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(url, {
    ...options,
    headers,
  });
  if (response.headers.get("content-type")?.toLowerCase().includes("text/html")) {
    throw new Error("Layanan data belum tersedia. Muat ulang halaman atau coba lagi nanti.");
  }
  return response;
}

// ---------------------------------------------------------------------------
// Account Pockets (Universal Sub-Pocket Vanguard) — /api/v1/pockets
// ---------------------------------------------------------------------------

export interface PocketItem {
  id: number;
  user_id: number;
  account_id?: number | null;
  account_name?: string | null;
  role?: string;
  subscription_id?: number | null;
  subscription_name?: string | null;
  subscription_status?: "active" | "inactive" | "missing" | "account_mismatch" | null;
  subscription_billing_cycle?: string | null;
  name: string;
  slug: string;
  balance?: number;
  current_balance?: number;
  target_amount: number;
  spent_amount: number;
  remaining_amount: number;
  percentage_spent: number;
  percentage: number;
  is_active: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}
export type JagoPocketItem = PocketItem;

export interface PocketsSummaryResponse {
  account_id?: number | null;
  account_name?: string | null;
  total_balance?: number;
  total_pocket_balance?: number;
  total_jago_balance?: number;
  total_target_amount: number;
  total_spent_amount: number;
  total_remaining_amount: number;
  cycle_start?: string | null;
  cycle_end?: string | null;
  pockets: PocketItem[];
  items: PocketItem[];
}
export type JagoPocketsSummaryResponse = PocketsSummaryResponse;

export interface PocketTransferPayload {
  account_id?: number;
  from_pocket_id?: number;
  from_pocket_slug?: string;
  to_pocket_id?: number;
  to_pocket_slug?: string;
  amount: number;
  note?: string;
}

export interface PocketTransferResponse {
  status: string;
  account_id?: number;
  from_pocket_id: number;
  from_pocket_name: string;
  from_pocket_balance: number;
  to_pocket_id: number;
  to_pocket_name: string;
  to_pocket_balance: number;
  amount: number;
  note?: string;
  created_at: string;
  pockets?: PocketItem[];
}

export interface PocketTargetUpdate {
  id?: number;
  slug?: string;
  name?: string;
  target_amount: number;
  is_active?: boolean;
}
export type JagoPocketTargetUpdate = PocketTargetUpdate;

async function parsePocketResponse(res: Response, action: string): Promise<PocketsSummaryResponse> {
  if (!res.ok) {
    let detail = `Gagal ${action} kantong rekening`;
    try {
      const data = await res.json();
      if (data && typeof data.detail === "string" && data.detail.trim()) {
        detail = data.detail;
      }
    } catch {
      // Fall through to default message when body is not JSON.
    }
    throw new Error(detail);
  }
  return (await res.json()) as PocketsSummaryResponse;
}
export const parseJagoResponse = parsePocketResponse;

export async function getPockets(accountId?: number, cycleStart?: string, cycleEnd?: string): Promise<PocketsSummaryResponse> {
  const query = new URLSearchParams();
  if (accountId) query.set("account_id", String(accountId));
  if (cycleStart && cycleEnd) {
    query.set("cycle_start", cycleStart);
    query.set("cycle_end", cycleEnd);
  }
  const res = await authFetch(`/api/v1/pockets${query.size ? `?${query}` : ""}`);
  return parsePocketResponse(res, "memuat");
}
export const getJagoPockets = getPockets;

export async function updatePockets(
  payload: PocketTargetUpdate[],
  accountId?: number
): Promise<PocketsSummaryResponse> {
  const res = await authFetch(`/api/v1/pockets${accountId ? `?account_id=${accountId}` : ""}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parsePocketResponse(res, "memperbarui");
}
export const updateJagoPockets = updatePockets;

export interface PocketBill {
  id: number;
  name: string;
  account: string;
  amount: number;
  is_active: boolean;
  billing_cycle: string;
  billing_type?: string;
}

export async function getPocketBills(): Promise<PocketBill[]> {
  const res = await authFetch("/api/v1/subscriptions");
  if (!res.ok) throw new Error("Gagal memuat tagihan. Coba lagi.");
  const body = await res.json();
  return body.items;
}

export async function linkPocketBill(pocketId: number, subscriptionId: number | null): Promise<PocketsSummaryResponse> {
  const res = await authFetch(`/api/v1/pockets/${pocketId}/subscription`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ subscription_id: subscriptionId }),
  });
  return parsePocketResponse(res, "menghubungkan tagihan ke");
}

export async function createAccountPocket(payload: { account_id: number; name: string; role: string; target_amount: number }): Promise<PocketItem> {
  const res = await authFetch("/api/v1/pockets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : "Gagal menambah kantong. Periksa isian lalu coba lagi.");
  }
  return res.json();
}

export async function transferPocketBalance(payload: PocketTransferPayload): Promise<PocketTransferResponse> {
  const res = await authFetch("/api/v1/pockets/transfer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let detail = "Gagal memindahkan saldo kantong.";
    try {
      const body = await res.json();
      if (body && typeof body.detail === "string" && body.detail.trim()) {
        detail = body.detail;
      }
    } catch {
      // Fall through to default detail
    }
    throw new Error(detail);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Google Sheets Multi-Tenant Sync — /api/v1/analytics/sync-sheets
// ---------------------------------------------------------------------------

export interface SheetsSyncResponse {
  success: boolean;
  sheet_title: string;
  spreadsheet_id: string;
  spreadsheet_url: string;
  synced_at: string;
  cycle_range: string;
  transaction_count: number;
  envelopes_count: number;
  pocket_spent: number;
  pocket_remaining: number;
  total_balance: number;
}

export async function syncGoogleSheets(cycleStart?: string): Promise<SheetsSyncResponse> {
  const query = cycleStart ? `?cycle_start=${encodeURIComponent(cycleStart)}` : "";
  const res = await authFetch(`/api/v1/analytics/sync-sheets${query}`, {
    method: "POST",
  });
  if (!res.ok) {
    let detail = "Gagal menyinkronkan data ke Google Sheets.";
    try {
      const data = await res.json();
      if (data && typeof data.detail === "string" && data.detail.trim()) {
        detail = data.detail;
      }
    } catch {
      // Fall through to default message
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function updateGoogleSpreadsheet(urlOrId: string | null): Promise<UserProfile> {
  const res = await authFetch("/api/v1/auth/me", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ google_sheet_url: urlOrId }),
  });
  if (!res.ok) {
    let detail = "Gagal memperbarui link Google Sheets.";
    try {
      const data = await res.json();
      if (data && typeof data.detail === "string" && data.detail.trim()) {
        detail = data.detail;
      }
    } catch {
      // Fall through to default message
    }
    throw new Error(detail);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Internal Loans (Dana Talangan Internal) — /api/v1/internal-loans
// ---------------------------------------------------------------------------

export interface InternalLoan {
  id: number;
  user_id: number;
  source_account_id: number;
  source_pocket_id?: number | null;
  target_account_id: number;
  target_pocket_id?: number | null;
  source_account_name: string;
  target_account_name: string;
  source_pocket_name?: string | null;
  target_pocket_name?: string | null;
  amount: number;
  remaining_amount: number;
  status: "active" | "settled" | "cancelled";
  note?: string | null;
  created_at: string;
  settled_at?: string | null;
}

export interface InternalLoanListResponse {
  items: InternalLoan[];
  total: number;
  total_active_loan_amount: number;
}

export interface InternalLoanCreatePayload {
  source_account_id: number;
  source_pocket_id?: number | null;
  target_account_id: number;
  target_pocket_id?: number | null;
  amount: number;
  note?: string;
}

export type CreateInternalLoanPayload = InternalLoanCreatePayload;

export interface SettleInternalLoanPayload {
  amount?: number | null;
  note?: string | null;
}

export async function getInternalLoans(
  status?: string,
  limit?: number,
  skip?: number
): Promise<InternalLoanListResponse> {
  const query = new URLSearchParams();
  if (status) query.set("status", status);
  if (typeof limit === "number") query.set("limit", String(limit));
  if (typeof skip === "number") query.set("skip", String(skip));

  const res = await authFetch(`/api/v1/internal-loans${query.size ? `?${query}` : ""}`);
  if (!res.ok) {
    let detail = "Gagal memuat daftar pinjaman internal";
    try {
      const data = await res.json();
      if (data && typeof data.detail === "string" && data.detail.trim()) {
        detail = data.detail;
      }
    } catch {
      // Fall through
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function createInternalLoan(
  data: InternalLoanCreatePayload
): Promise<InternalLoan> {
  const res = await authFetch("/api/v1/internal-loans", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    let detail = "Gagal membuat pinjaman dana talangan internal";
    try {
      const respData = await res.json();
      if (respData && typeof respData.detail === "string" && respData.detail.trim()) {
        detail = respData.detail;
      }
    } catch {
      // Fall through
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function settleInternalLoan(
  id: number,
  data?: { amount?: number | null; note?: string | null }
): Promise<InternalLoan> {
  const res = await authFetch(`/api/v1/internal-loans/${id}/settle`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data || {}),
  });
  if (!res.ok) {
    let detail = "Gagal melunasi pinjaman dana talangan";
    try {
      const respData = await res.json();
      if (respData && typeof respData.detail === "string" && respData.detail.trim()) {
        detail = respData.detail;
      }
    } catch {
      // Fall through
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function cancelInternalLoan(
  id: number
): Promise<void> {
  const res = await authFetch(`/api/v1/internal-loans/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    let detail = "Gagal membatalkan pinjaman internal";
    try {
      const data = await res.json();
      if (data && typeof data.detail === "string" && data.detail.trim()) {
        detail = data.detail;
      }
    } catch {
      // Fall through
    }
    throw new Error(detail);
  }
}


