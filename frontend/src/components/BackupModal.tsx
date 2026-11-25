"use client";

import React, { useRef, useState } from "react";
import { Download, Upload } from "@/components/icons";
import { authFetch } from "@/lib/api";
import { CustomModal } from "./ui/CustomModal";

interface BackupSummary {
  counts: Record<string, number>;
  total_balance: number;
  balances: Record<string, number>;
  legacy_missing_loan_history?: boolean;
}

const labels: Record<string, string> = {
  accounts: "Rekening", transactions: "Transaksi", categories: "Kategori",
  pockets: "Kantong", subscriptions: "Tagihan", goals: "Target tabungan",
  paycheck_configs: "Pengaturan gajian", paycheck_buckets: "Alokasi gaji",
  paycheck_sessions: "Checklist gajian", paycheck_cycles: "Siklus checklist",
  legacy_paycheck_cycles: "Riwayat siklus", paycheck_receipts: "Catatan gaji",
  subscription_payments: "Pembayaran tagihan", internal_loans: "Pinjaman internal",
  pocket_mutations: "Mutasi kantong",
};

export function BackupModal({ isOpen, onClose, onRestored }: {
  isOpen: boolean; onClose: () => void; onRestored: () => void;
}) {
  const fileInput = useRef<HTMLInputElement>(null);
  const inFlight = useRef(false);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<BackupSummary | null>(null);
  const [content, setContent] = useState("");
  const [filename, setFilename] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [message, setMessage] = useState<{ error: boolean; text: string } | null>(null);

  const download = async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setMessage(null);
    try {
      const response = await authFetch("/api/v1/backup/export");
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Gagal membuat backup.");
      }
      const url = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "tillfold-backup-" + new Date().toISOString().replace(/[:.]/g, "-") + ".json";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setMessage({ error: false, text: "Backup diunduh. File berisi data keuangan pribadi, simpan di tempat aman." });
    } catch (error) {
      setMessage({ error: true, text: error instanceof Error ? error.message : "Gagal membuat backup." });
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  };

  const inspectFile = async (file: File | undefined) => {
    if (!file || inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setPreview(null);
    setContent("");
    setFilename(file.name);
    setConfirmed(false);
    setMessage(null);
    try {
      if (file.size > 25 * 1024 * 1024) throw new Error("Ukuran backup maksimal 25 MB.");
      const text = await file.text();
      const response = await authFetch("/api/v1/backup/preview", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: text,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "File backup tidak valid.");
      setContent(text);
      setPreview(data);
    } catch (error) {
      setMessage({ error: true, text: error instanceof Error ? error.message : "Gagal membaca backup." });
    } finally {
      inFlight.current = false;
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const restore = async () => {
    if (!confirmed || !preview || inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setMessage(null);
    try {
      const response = await authFetch("/api/v1/backup/restore", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: content,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Gagal memulihkan data.");
      setPreview(null);
      setContent("");
      setConfirmed(false);
      setMessage({ error: false, text: "Data dipulihkan. Jumlah data dan saldo sudah cocok dengan backup." });
      onRestored();
    } catch (error) {
      setMessage({ error: true, text: error instanceof Error ? error.message : "Gagal memulihkan data." });
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  };

  return (
    <CustomModal isOpen={isOpen} onClose={() => { if (!inFlight.current) onClose(); }}
      title="Cadangkan dan pulihkan" subtitle="Simpan dan pulihkan data keuangan" maxWidth="form">
      <div className="space-y-5 text-sm text-luma-ivory">
        <section className="space-y-3">
          <h3 className="font-medium">Backup lengkap</h3>
          <p className="text-luma-smoke">Simpan rekening, transaksi, kategori, kantong, tagihan, target, dan pengaturan gajian ke file JSON.</p>
          <p className="text-xs text-luma-smoke">Password, koneksi Telegram, dan pengaturan server tidak disertakan.</p>
          <button type="button" onClick={download} disabled={busy} className="luma-action-primary"><Download size={16} />Unduh backup</button>
        </section>
        <section className="space-y-3 border-t border-luma-smokeline pt-5">
          <h3 className="font-medium">Pulihkan backup</h3>
          <p className="text-luma-smoke">Gunakan akun dengan data keuangan kosong. Pilih file backup Tillfold untuk memeriksa isinya sebelum dipulihkan. Maksimal 25 MB.</p>
          <input ref={fileInput} type="file" accept=".json,application/json" className="hidden"
            aria-label="File backup Tillfold" disabled={busy} onChange={event => inspectFile(event.target.files?.[0])} />
          <button type="button" onClick={() => fileInput.current?.click()} disabled={busy} className="luma-action-secondary"><Upload size={16} />Pilih file backup</button>
          {filename && <p className="break-all text-xs text-luma-smoke">{filename}</p>}
          {preview && <div className="space-y-4 rounded-3xl border border-luma-smokeline bg-luma-coal p-4">
            <dl className="grid grid-cols-2 gap-3">
              {Object.entries(preview.counts).map(([key, count]) => <div key={key}><dt className="text-xs text-luma-smoke">{labels[key] || key}</dt><dd className="font-medium">{count.toLocaleString("id-ID")}</dd></div>)}
            </dl>
            <p>Total saldo <strong className="tabular-nums">{new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", maximumFractionDigits: 0 }).format(preview.total_balance)}</strong></p>
            {preview.legacy_missing_loan_history && (
              <p className="text-sm text-luma-smoke">Backup versi lama ini hanya memuat transaksi talangan yang tercatat di riwayat. Daftar talangan dan mutasi kantong belum tersedia di format ini.</p>
            )}
            <label className="flex min-h-11 items-start gap-3 cursor-pointer">
              <input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} disabled={busy} className="mt-1 shrink-0" />
              <span>Saya ingin memulihkan file ini ke akun dengan data keuangan kosong.</span>
            </label>
            <button type="button" onClick={restore} disabled={busy || !confirmed} className="luma-action-primary">Pulihkan data</button>
          </div>}
        </section>
        {busy && <p role="status" className="text-luma-smoke">Memproses data…</p>}
        {message && <p role={message.error ? "alert" : "status"} className={message.error ? "text-coralFall" : "text-mintRise"}>{message.text}</p>}
      </div>
    </CustomModal>
  );
}
