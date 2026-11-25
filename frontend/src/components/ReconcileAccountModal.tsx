"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { authFetch } from "@/lib/api";
import { CustomModal } from "./ui/CustomModal";
import { CurrencyInput } from "./ui/CurrencyInput";

interface Snapshot { account: string; balance: number; latest_transaction_id: number }

export function ReconcileAccountModal({ accountId, onClose, onSuccess }: {
  accountId: number; onClose: () => void; onSuccess: () => void;
}) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [amount, setAmount] = useState("");
  const [negative, setNegative] = useState(false);
  const [note, setNote] = useState("");
  const [review, setReview] = useState(false);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const requestKey = useRef(crypto.randomUUID());
  const inFlight = useRef(false);
  const actual = Number(amount) * (negative ? -1 : 1);
  const valid = amount !== "" && Number.isSafeInteger(actual) && Math.abs(actual) <= 9_000_000_000_000_000;
  const difference = snapshot ? actual - snapshot.balance : 0;
  const rupiah = (value: number) => new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", maximumFractionDigits: 0 }).format(value);

  const loadSnapshot = useCallback(async (signal?: AbortSignal) => {
    setSnapshot(null);
    setReview(false);
    setError("");
    try {
      const response = await authFetch("/api/v1/accounts/" + accountId + "/reconciliation", { signal });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Gagal memuat saldo.");
      if (!signal?.aborted) {
        setSnapshot(data);
        requestKey.current = crypto.randomUUID();
      }
    } catch (failure) {
      if (!signal?.aborted) setError(failure instanceof Error ? failure.message : "Gagal memuat saldo.");
    }
  }, [accountId]);

  useEffect(() => {
    const controller = new AbortController();
    loadSnapshot(controller.signal);
    return () => controller.abort();
  }, [loadSnapshot]);

  const save = async () => {
    if (!snapshot || !valid || !review || !note.trim() || !difference || inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError("");
    try {
      const response = await authFetch("/api/v1/accounts/" + accountId + "/reconciliation", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request_key: requestKey.current, actual_balance: actual,
          expected_balance: snapshot.balance, latest_transaction_id: snapshot.latest_transaction_id, note: note.trim() }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Gagal menyimpan penyesuaian.");
      setSaved(true);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Gagal menyimpan penyesuaian.");
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  };

  const close = () => {
    if (inFlight.current) return;
    if (saved) onSuccess();
    onClose();
  };

  return <CustomModal isOpen onClose={close}
    title="Cocokkan saldo" subtitle={snapshot?.account || "Memuat rekening"} maxWidth="form">
    <div className="space-y-4 text-sm text-luma-ivory">
      {saved ? <>
        <p role="status" className="text-mintRise">Penyesuaian tersimpan. Saldo rekening diperbarui.</p>
        <p className="ai7-type-metric tabular-nums">{rupiah(actual)}</p>
        <button type="button" className="luma-action-primary" onClick={close}>Selesai</button>
      </> : <>
        <p className="text-luma-smoke">Cocokkan dengan saldo bank atau uang tunai saat ini. Selisih dicatat sebagai penyesuaian saldo.</p>
        {!snapshot && !error && <p role="status">Memuat saldo…</p>}
        {snapshot && <>
          <p>Saldo Tillfold <strong className="tabular-nums">{rupiah(snapshot.balance)}</strong></p>
          {!review ? <form className="space-y-4" onSubmit={event => { event.preventDefault(); if (valid && note.trim()) setReview(true); }}>
            <div className="space-y-2"><label htmlFor="reconcile-actual">Saldo aktual</label>
              <CurrencyInput id="reconcile-actual" value={amount} onChange={setAmount} required /></div>
            <label className="flex min-h-11 items-center gap-3 cursor-pointer">
              <input type="checkbox" checked={negative} onChange={event => setNegative(event.target.checked)} />Saldo aktual negatif
            </label>
            <div className="space-y-2"><label htmlFor="reconcile-note">Catatan penyesuaian</label>
              <textarea id="reconcile-note" value={note} onChange={event => setNote(event.target.value)} maxLength={120} required
                className="w-full rounded-xl border border-luma-smokeline bg-luma-coal p-3 text-base" /></div>
            <p className="text-xs text-luma-smoke">Penyesuaian disimpan di riwayat. Koreksi berikutnya dilakukan lewat rekonsiliasi baru.</p>
            <button type="submit" disabled={!valid || !note.trim()} className="luma-action-primary">Periksa selisih</button>
          </form> : <div className="space-y-4">
            <dl className="space-y-3 rounded-3xl border border-luma-smokeline bg-luma-coal p-4">
              <div className="flex flex-wrap justify-between gap-2"><dt>Saldo aktual</dt><dd className="font-medium tabular-nums">{rupiah(actual)}</dd></div>
              <div className="flex flex-wrap justify-between gap-2"><dt>Selisih</dt><dd className="font-medium tabular-nums">{difference > 0 ? "+" : ""}{rupiah(difference)}</dd></div>
            </dl>
            <p className="break-words">{note}</p>
            {difference === 0 ? <p role="status">Saldo sudah cocok. Tidak perlu penyesuaian.</p>
              : <p className="text-luma-smoke">Saldo akan {difference > 0 ? "bertambah" : "berkurang"} sebesar {rupiah(Math.abs(difference))}. Pemasukan dan pengeluaran di laporan tetap dihitung terpisah.</p>}
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={() => setReview(false)} disabled={busy} className="luma-action-secondary">Ubah</button>
              {difference !== 0 && <button type="button" onClick={save} disabled={busy} className="luma-action-primary">{busy ? "Menyimpan…" : "Simpan penyesuaian"}</button>}
            </div>
          </div>}
        </>}
        {error && <div className="space-y-3"><p role="alert" className="text-coralFall">{error}</p>
          <button type="button" disabled={busy} onClick={() => loadSnapshot()} className="luma-action-secondary">Muat ulang saldo</button></div>}
      </>}
    </div>
  </CustomModal>;
}
