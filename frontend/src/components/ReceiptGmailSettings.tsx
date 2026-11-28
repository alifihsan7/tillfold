"use client";

import { useEffect, useState } from "react";
import { apiErrorMessage, authFetch } from "@/lib/api";

interface GmailStatus {
  available: boolean;
  telegram_linked: boolean;
  email: string | null;
  status: "connected" | "disconnected" | "reconnect";
  last_checked_at: string | null;
}

const endpoint = "/api/v1/receipt-radar/gmail";
const outcomes: Record<string, string> = {
  connected: "Gmail terhubung. Receipt Radar akan mengecek struk baru.",
  cancelled: "Koneksi Gmail dibatalkan.",
  failed: "Gmail belum terhubung. Coba lagi dari Tillfold.",
  in_use: "Akun Gmail itu sudah terhubung ke akun Tillfold lain.",
  switch: "Putuskan akun Gmail yang sekarang sebelum memilih akun lain.",
};

async function gmailRequest<T>(path = "", method = "GET", signal?: AbortSignal): Promise<T> {
  const response = await authFetch(endpoint + path, { method, signal, cache: "no-store" });
  const data = await response.json();
  if (!response.ok) throw new Error(apiErrorMessage(data, "Koneksi Gmail gagal diproses."));
  return data;
}

export function ReceiptGmailSettings({ onConnectTelegram, telegramLink }: {
  onConnectTelegram: () => void;
  telegramLink: number | null;
}) {
  const [data, setData] = useState<GmailStatus>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [insideTelegram, setInsideTelegram] = useState(false);

  useEffect(() => {
    setInsideTelegram(Boolean(window.Telegram?.WebApp?.initData));
    const url = new URL(window.location.href);
    const outcome = url.searchParams.get("receipt_gmail");
    if (outcome) {
      setNotice(outcomes[outcome] || "");
      url.searchParams.delete("receipt_gmail");
      window.history.replaceState(window.history.state, "", url);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void gmailRequest<GmailStatus>("", "GET", controller.signal).then(setData).catch(err => {
      if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "Koneksi Gmail gagal dimuat.");
    });
    return () => controller.abort();
  }, [telegramLink]);

  const connect = async () => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const { url } = await gmailRequest<{ url: string }>("/connect", "POST");
      if (new URL(url).origin !== "https://accounts.google.com") throw new Error("Alamat login Gmail tidak valid.");
      window.location.assign(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Koneksi Gmail gagal dimulai.");
      setBusy(false);
    }
  };

  const disconnect = async () => {
    setBusy(true);
    setError("");
    try {
      const { revoked } = await gmailRequest<{ revoked: boolean }>("", "DELETE");
      setData(current => current && { ...current, email: null, status: "disconnected", last_checked_at: null });
      setNotice(revoked ? "Gmail sudah diputuskan." : "Gmail diputuskan dari Tillfold. Cabut izin Receipt Radar juga di Akun Google karena Google belum mengonfirmasi pencabutan.");
      setConfirm(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gmail gagal diputuskan.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3 rounded-2xl luma-inset p-4 text-sm">
      <div>
        <h4 className="font-semibold text-luma-ivory">Gmail otomatis</h4>
        <p className="mt-1 text-luma-smoke">Hubungkan sekali untuk menerima draf dari email struk baru di Telegram.</p>
      </div>
      {notice && <p role="status">{notice}</p>}
      {error && <p role="alert" className="text-coralFall">{error}</p>}
      {!data && !error && <p role="status" className="text-luma-smoke">Memuat koneksi Gmail…</p>}
      {data && !data.available && <p className="text-luma-smoke">Koneksi Gmail otomatis belum tersedia.</p>}
      {data?.available && !data.telegram_linked && (
        <button type="button" onClick={onConnectTelegram} className="luma-action-secondary">Hubungkan Telegram</button>
      )}
      {data?.email && (
        <div className="space-y-1">
          <p className="[overflow-wrap:anywhere]">{data.email}</p>
          {data.status === "reconnect" && <p className="text-coralFall">Akses Gmail sudah berakhir. Hubungkan kembali untuk melanjutkan.</p>}
          {data.last_checked_at && <p className="text-luma-smoke">Terakhir dicek {new Intl.DateTimeFormat("id-ID", {
            dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Jakarta",
          }).format(new Date(data.last_checked_at))} WIB</p>}
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {data?.available && data.telegram_linked && data.status !== "connected" && (
          insideTelegram ? (
            <a href="/#/profile" target="_blank" rel="noreferrer" className="luma-action-primary" onClick={event => {
              const telegram = window.Telegram?.WebApp;
              if (telegram?.openLink) {
                event.preventDefault();
                telegram.openLink(event.currentTarget.href);
              }
            }}>Buka browser untuk hubungkan Gmail</a>
          ) : (
            <button type="button" onClick={connect} disabled={busy} className="luma-action-primary">
              {data.status === "reconnect" ? "Hubungkan ulang Gmail" : "Hubungkan Gmail"}
            </button>
          )
        )}
        {data?.email && !confirm && (
          <button type="button" onClick={() => setConfirm(true)} disabled={busy} className="luma-action-secondary">Putuskan Gmail</button>
        )}
      </div>
      {confirm && (
        <div className="space-y-2">
          <p>Tillfold akan berhenti mengecek Gmail dan membuang draf Gmail yang belum dicatat.</p>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={() => setConfirm(false)} disabled={busy} className="luma-action-secondary">Batal</button>
            <button type="button" onClick={disconnect} disabled={busy} className="luma-action-secondary text-coralFall">Ya, putuskan Gmail</button>
          </div>
        </div>
      )}
    </div>
  );
}
