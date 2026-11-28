"use client";

import { useEffect, useState } from "react";
import { Check, Copy, ExternalLink, RefreshCw } from "@/components/icons";
import { apiErrorMessage, authFetch } from "@/lib/api";
import { ReceiptGmailSettings } from "./ReceiptGmailSettings";

interface ReceiptRadarStatus {
  available: boolean;
  telegram_linked: boolean;
  address: string | null;
  verification_code: string | null;
  verification_url: string | null;
}

async function receiptRadarRequest(method = "GET", signal?: AbortSignal): Promise<ReceiptRadarStatus> {
  const response = await authFetch("/api/v1/receipt-radar", { method, signal, cache: "no-store" });
  const data = await response.json();
  if (!response.ok) throw new Error(apiErrorMessage(data, "Receipt Radar gagal memproses permintaan."));
  return data;
}

export function ReceiptRadarSettings({ onConnectTelegram, telegramLink }: {
  onConnectTelegram: () => void;
  telegramLink: number | null;
}) {
  const [data, setData] = useState<ReceiptRadarStatus>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [confirmDisable, setConfirmDisable] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    void receiptRadarRequest("GET", controller.signal).then(result => {
      if (!controller.signal.aborted) setData(result);
    }).catch(err => {
      if (!controller.signal.aborted) setError(err.message);
    });
    return () => controller.abort();
  }, [telegramLink]);

  const request = async (method = "GET") => {
    setBusy(true);
    setError("");
    setCopied(false);
    try {
      setData(await receiptRadarRequest(method));
      setConfirmDisable(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Receipt Radar gagal memproses permintaan.");
    } finally {
      setBusy(false);
    }
  };

  const copyAddress = async () => {
    if (!data?.address) return;
    setError("");
    try {
      await navigator.clipboard.writeText(data.address);
      setCopied(true);
    } catch {
      setError("Alamat belum tersalin. Pilih alamat email lalu salin manual.");
    }
  };

  return (
    <section aria-labelledby="receipt-radar-title" className="space-y-3">
      <h3 id="receipt-radar-title" className="ai7-type-card text-luma-ivory tracking-tight">Receipt Radar</h3>
      <ReceiptGmailSettings onConnectTelegram={onConnectTelegram} telegramLink={telegramLink} />
      {(data?.available || error) && <details className="space-y-3 rounded-2xl luma-inset p-4 text-sm" open={data?.address ? true : undefined}>
        <summary className="cursor-pointer font-semibold text-luma-ivory">Forwarding email manual</summary>
        <p className="text-luma-smoke">Teruskan email struk ke Tillfold dan pilih rekening serta kategori di chat pribadi Telegram.</p>

        {error && <p role="alert" className="text-coralFall">{error}</p>}
        {!data && !error && <p role="status" className="text-luma-smoke">Memuat Receipt Radar…</p>}
        {!data && error && <button type="button" onClick={() => request()} disabled={busy} className="luma-action-secondary">Coba lagi</button>}
        {data && !data.available && <p className="text-luma-smoke">Alamat penerima belum tersedia.</p>}
        {data?.available && !data.telegram_linked && (
          <button type="button" className="luma-action-secondary" onClick={onConnectTelegram}>Hubungkan Telegram</button>
        )}
        {data?.available && data.telegram_linked && !data.address && (
          <button type="button" onClick={() => request("POST")} disabled={busy} className="luma-action-primary">Buat alamat forwarding</button>
        )}

        {data?.address && (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <code className="min-w-0 flex-1 select-all text-luma-ivory [overflow-wrap:anywhere]">{data.address}</code>
              <button type="button" onClick={copyAddress} className="luma-action-secondary shrink-0">
                {copied ? <Check size={16} aria-hidden="true" /> : <Copy size={16} aria-hidden="true" />}
                {copied ? "Tersalin" : "Salin alamat"}
              </button>
            </div>
            <ol className="list-decimal space-y-1 pl-5 text-luma-smoke">
              <li>Tambahkan alamat ini di pengaturan forwarding email.</li>
              <li>Jika penyedia meminta verifikasi, periksa pesan konfirmasinya di bawah.</li>
              <li>Buat filter khusus email struk Livin’ Mandiri, BRImo, atau Google Play.</li>
            </ol>
            {data.verification_code && <p>Status verifikasi Gmail · <code className="select-all">{data.verification_code}</code></p>}
            <div className="flex flex-wrap gap-2">
              {data.verification_url && (
                <a href={data.verification_url} target="_blank" rel="noreferrer" className="luma-action-secondary">
                  <ExternalLink size={16} aria-hidden="true" /> Konfirmasi di Gmail
                </a>
              )}
              <button type="button" onClick={() => request()} disabled={busy} className="luma-action-secondary">
                <RefreshCw size={16} aria-hidden="true" /> Cek verifikasi
              </button>
              {!confirmDisable && (
                <button type="button" onClick={() => setConfirmDisable(true)} disabled={busy} className="luma-action-secondary">Nonaktifkan</button>
              )}
            </div>
            {confirmDisable && (
              <div className="space-y-2">
                <p>Alamat ini akan berhenti menerima struk dan draf yang belum dicatat akan dibuang.</p>
                <div className="flex flex-wrap gap-2">
                  <button type="button" onClick={() => setConfirmDisable(false)} disabled={busy} className="luma-action-secondary">Batal</button>
                  <button type="button" onClick={() => request("DELETE")} disabled={busy} className="luma-action-secondary text-coralFall">Ya, nonaktifkan</button>
                </div>
              </div>
            )}
          </>
        )}
      </details>}
    </section>
  );
}
