"use client";

import React, { useEffect, useRef, useState } from "react";
import { authFetch } from "@/lib/api";
import { CustomModal } from "./ui/CustomModal";
import { CustomSelect } from "./ui/CustomSelect";
import { DateField } from "./ui/DateField";
import { todayWib } from "@/lib/transactionCalendar";

interface PaymentPreview {
  name: string; amount: number; account: string; is_active: boolean;
  payment_period: string | null; payment_due_date: string | null;
  is_paid: boolean; paid_date: string | null;
  paid_amount?: number | null;
  candidates: { id: number; date: string; description: string }[];
}

export function BillPaymentModal({ subscriptionId, onClose, onChanged }: {
  subscriptionId: number; onClose: () => void; onChanged: () => void;
}) {
  const today = todayWib();
  const [data, setData] = useState<PaymentPreview | null>(null);
  const [source, setSource] = useState("new");
  const [paidDate, setPaidDate] = useState(today);
  const [review, setReview] = useState(false);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const inFlight = useRef(false);
  const rupiah = (amount: number) => new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", maximumFractionDigits: 0 }).format(amount);

  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setError("");
    setReview(false);
    setSource("new");
    const load = async () => {
      try {
        const response = await authFetch("/api/v1/subscriptions/" + subscriptionId + "/payment", { signal: controller.signal });
        const preview = await response.json();
        if (!response.ok) throw new Error(preview.detail || "Gagal memuat tagihan.");
        if (!controller.signal.aborted) setData(preview);
      } catch (failure) {
        if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : "Gagal memuat tagihan.");
      }
    };
    load();
    return () => controller.abort();
  }, [subscriptionId, reload]);

  const close = () => {
    if (inFlight.current) return;
    if (saved || data?.is_paid) onChanged();
    onClose();
  };
  const save = async () => {
    if (!data?.payment_period || !review || inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError("");
    try {
      const response = await authFetch("/api/v1/subscriptions/" + subscriptionId + "/payment", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          period: data.payment_period, expected_amount: data.amount, expected_account: data.account,
          paid_date: source === "new" ? paidDate : null,
          existing_transaction_id: source === "new" ? null : Number(source),
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Gagal mencatat pembayaran.");
      setData({ ...data, amount: result.amount, account: result.account, paid_date: result.paid_date });
      setSaved(true);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Gagal mencatat pembayaran.");
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  };

  return <CustomModal isOpen onClose={close} title="Catat pembayaran" subtitle={data?.name || "Memuat tagihan"} maxWidth="md">
    <div className="space-y-4 text-sm text-luma-ivory">
      {!data && !error && <p role="status">Memuat tagihan…</p>}
      {data && <>
        <dl className="space-y-3 rounded-[var(--ai7-radius-panel)] border border-luma-smokeline bg-luma-coal p-4">
          <div className="flex flex-wrap justify-between gap-2"><dt>Nominal</dt><dd className="font-medium tabular-nums">{rupiah(data.is_paid ? data.paid_amount ?? data.amount : data.amount)}</dd></div>
          <div className="flex flex-wrap justify-between gap-2"><dt>Rekening</dt><dd>{data.account}</dd></div>
          <div className="flex flex-wrap justify-between gap-2"><dt>Jatuh tempo periode ini</dt><dd>{data.payment_due_date || "Belum diatur"}</dd></div>
        </dl>
        {saved || data.is_paid ? <div className="space-y-4">
          <p role="status" className="text-mintRise">{saved ? "Pembayaran tercatat. Tagihan periode ini sudah lunas." : "Tagihan periode ini sudah dibayar pada " + data.paid_date + "."}</p>
          <button type="button" onClick={close} className="luma-action-primary">Selesai</button>
        </div> : !data.is_active || !data.payment_period ? <p>Aktifkan tagihan dan lengkapi tanggalnya sebelum mencatat pembayaran.</p> : <>
          {!review ? <form className="space-y-4" onSubmit={event => { event.preventDefault(); setReview(true); setError(""); }}>
            {data.candidates.length > 0 && <div className="space-y-2">
              <CustomSelect label="Pencatatan" value={source} onChange={setSource} options={[
                { value: "new", label: "Catat pengeluaran baru" },
                ...data.candidates.map(tx => ({ value: String(tx.id), label: tx.date + " · " + tx.description })),
              ]} />
              <p className="text-xs text-luma-smoke">Sudah dicatat? Pilih transaksi yang ada agar saldo tidak terpotong lagi. Daftar menampilkan transaksi dengan nominal dan rekening yang sama.</p>
            </div>}
            {source === "new" && <div className="space-y-2">
              <label htmlFor="bill-paid-date">Tanggal pembayaran</label>
              <DateField id="bill-paid-date" label="Tanggal pembayaran" value={paidDate} onChange={setPaidDate} max={today} required />
            </div>}
            <button type="submit" disabled={source === "new" && !paidDate} className="luma-action-primary">Periksa pembayaran</button>
          </form> : <div className="space-y-4">
            <p>{source === "new" ? "Catat pengeluaran " + rupiah(data.amount) + " dari " + data.account + " pada " + paidDate + "."
              : "Hubungkan transaksi yang dipilih sebagai pembayaran periode ini. Saldo tidak dipotong ulang."}</p>
            {source !== "new" && <p className="text-luma-smoke">{data.candidates.find(tx => String(tx.id) === source)?.description}</p>}
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={() => { setReview(false); setError(""); }} disabled={busy} className="luma-action-secondary">Ubah</button>
              <button type="button" onClick={save} disabled={busy} className="luma-action-primary">{busy ? "Menyimpan…" : "Simpan pembayaran"}</button>
            </div>
          </div>}
        </>}
      </>}
      {error && <div className="space-y-3"><p role="alert" className="text-coralFall">{error}</p>
        <button type="button" onClick={() => setReload(value => value + 1)} disabled={busy} className="luma-action-secondary">Muat ulang tagihan</button></div>}
    </div>
  </CustomModal>;
}
