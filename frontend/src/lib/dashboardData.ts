interface DashboardPeriod {
  type: string;
  start?: string;
  end?: string;
  month?: string;
}

export class DashboardLoadError extends Error {
  constructor(public status: number, resource: string) {
    super(status === 401
      ? "Sesi Anda berakhir. Masuk kembali untuk memuat ringkasan."
      : `Gagal memuat ${resource} (HTTP ${status}). Coba lagi.`);
  }
}

export async function loadDashboardData(fetcher: (url: string) => Promise<Response>, period: DashboardPeriod) {
  const summaryParams = new URLSearchParams({ period_type: period.type });
  const txParams = new URLSearchParams({ limit: "100" });
  if (period.start) { summaryParams.set("start", period.start); txParams.set("start_date", period.start); }
  if (period.end) { summaryParams.set("end", period.end); txParams.set("end_date", period.end); }
  if (period.month) summaryParams.set("month", period.month);

  const required = async (url: string, resource: string) => {
    const response = await fetcher(url);
    if (!response.ok) throw new DashboardLoadError(response.status, resource);
    return response.json();
  };
  const optional = async (url: string) => {
    try {
      const response = await fetcher(url);
      if (response.status === 401) throw new DashboardLoadError(401, "sesi");
      return response.ok ? await response.json() : null;
    } catch (error) {
      if (error instanceof DashboardLoadError && error.status === 401) throw error;
      return null;
    }
  };
  const [transactions, summary, subscriptions, accounts, goals, session, paycheck, categories] = await Promise.all([
    required(`/api/v1/transactions?${txParams}`, "transaksi"),
    required(`/api/v1/analytics/summary?${summaryParams}`, "ringkasan"),
    optional("/api/v1/subscriptions"), optional("/api/v1/accounts"), optional("/api/v1/goals"),
    optional("/api/v1/paycheck/session/active"), optional("/api/v1/paycheck/config"), optional("/api/v1/categories"),
  ]);
  return { transactions, summary, subscriptions, accounts, goals, session, paycheck, categories };
}
