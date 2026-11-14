import React, { useEffect, useState } from "react";
import { Link2 } from "lucide-react";
import { getPocketBills, linkPocketBill, PocketItem, PocketsSummaryResponse, PocketBill } from "@/lib/api";
import { CustomModal } from "./ui/CustomModal";
import { CustomSelect } from "./ui/CustomSelect";

export interface LinkPocketBillModalProps {
  pockets: PocketItem[];
  initialPocketId: number;
  accountName: string;
  formatRupiah: (value: number) => string;
  onClose: () => void;
  onSuccess: (data: PocketsSummaryResponse) => void;
}

export function LinkPocketBillModal({ pockets, initialPocketId, accountName, formatRupiah, onClose, onSuccess }: LinkPocketBillModalProps) {
  const [pocketId, setPocketId] = useState(initialPocketId);
  const pocket = pockets.find(item => item.id === pocketId);
  const [billId, setBillId] = useState(String(pocket?.subscription_id || "manual"));
  const [bills, setBills] = useState<PocketBill[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let current = true;
    setLoading(true);
    setLoadError(null);
    getPocketBills().then(data => { if (current) setBills(data); })
      .catch(err => { if (current) setLoadError(err instanceof Error ? err.message : "Gagal memuat tagihan."); })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [retry]);

  const used = new Set(pockets.filter(item => item.id !== pocketId).map(item => item.subscription_id));
  const eligible = bills.filter(bill => bill.is_active && bill.account.trim().toLowerCase() === accountName.trim().toLowerCase() && !used.has(bill.id));
  const choices = [{ value: "manual", label: "Atur target manual" }, ...eligible.map(bill => ({
    value: String(bill.id), label: `${bill.name} · ${formatRupiah(bill.amount)} / ${bill.billing_type === "exact_date" ? "periode" : bill.billing_cycle === "yearly" ? "tahun" : "bulan"}`,
  }))];
  if (pocket?.subscription_id && !eligible.some(bill => bill.id === pocket.subscription_id)) {
    choices.push({ value: String(pocket.subscription_id), label: `${pocket.subscription_name || "Tagihan terhubung"} · tidak aktif / tidak tersedia` });
  }
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!pocket || saving) return;
    setSaving(true);
    setError(null);
    try {
      const data = await linkPocketBill(pocket.id, billId === "manual" ? null : Number(billId));
      onSuccess(data);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal menyimpan hubungan tagihan.");
      setSaving(false);
    }
  };

  return <CustomModal isOpen onClose={() => { if (!saving) onClose(); }} title="Hubungkan tagihan" subtitle={`Rekening induk: ${accountName}`} icon={<Link2 className="w-5 h-5 text-luma-gold" />} maxWidth="lg">
    <form onSubmit={submit} className="space-y-4">
      {error && <p role="alert" className="text-sm text-luma-coral">{error}</p>}
      <fieldset disabled={saving}>
        <legend className="text-xs text-luma-smoke font-medium mb-2">Kantong</legend>
        <CustomSelect value={String(pocketId)} disabled={saving} options={pockets.map(item => ({ value: String(item.id), label: item.name }))} onChange={value => {
          const next = pockets.find(item => item.id === Number(value));
          setPocketId(Number(value));
          setBillId(String(next?.subscription_id || "manual"));
          setError(null);
        }} />
      </fieldset>
      {loading ? <p role="status" className="text-sm text-luma-smoke">Memuat tagihan…</p> : loadError ? <div role="alert" className="space-y-2 text-sm text-luma-coral">
        <p>{loadError}</p><button type="button" onClick={() => setRetry(value => value + 1)} className="px-3 border border-luma-smokeline">Coba lagi</button>
      </div> : <fieldset disabled={saving}>
        <legend className="text-xs text-luma-smoke font-medium mb-2">Tagihan</legend>
        <CustomSelect value={billId} onChange={setBillId} disabled={saving} options={choices} />
        {eligible.length === 0 && <p className="text-xs text-luma-smoke mt-2">Belum ada tagihan aktif yang tersedia untuk {accountName}. Buat atau atur rekening tagihan di halaman Tagihan.</p>}
      </fieldset>}
      <p className="text-sm text-luma-smoke">Hanya tagihan aktif dari rekening yang sama yang bisa dihubungkan. Satu tagihan untuk satu kantong. Target komitmen otomatis mengikuti nominal per tagihan.</p>
      <p className="text-xs text-luma-smoke">Pilih “Atur target manual” untuk melepas hubungan. Target terakhir dipertahankan; tagihan nonaktif menghasilkan target 0. Mutasi saldo kas dilakukan terpisah melalui menu Pindah Saldo.</p>
      <div className="flex justify-end gap-2 pt-4 border-t border-luma-smokeline">
        <button type="button" disabled={saving} onClick={onClose} className="px-4 py-2 border border-luma-smokeline text-luma-smoke">Batal</button>
        <button type="submit" disabled={saving || loading || !!loadError || !pocket} className="px-4 py-2 bg-luma-ivory text-luma-charcoal">{saving ? "Menyimpan…" : "Simpan hubungan"}</button>
      </div>
    </form>
  </CustomModal>;
}
