"use client";

import { DateField } from "@/components/ui/DateField";
import { useEffect, useRef, useState } from "react";
import { authFetch } from "@/lib/api";
import { CurrencyInput } from "./ui/CurrencyInput";
import { CustomSelect } from "./ui/CustomSelect";
import { CustomModal } from "./ui/CustomModal";

interface Receipt {
  id: number;
  amount: number;
  account: string;
  date: string;
  cycle_end: string | null;
  allocations: { account_id: number; account: string | null; amount: number; transfer_id: number | null }[];
}

interface Props {
  isOpen: boolean;
  accounts: string[];
  allocationAccounts: { id: number; name: string }[];
  onClose: () => void;
  onSuccess: (cycle?: { start: string; end: string }) => void;
  onConfigure: () => void;
}

const rupiah = new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", maximumFractionDigits: 0 });
const today = () => new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Jakarta" });

export function RecordPaycheckModal({ isOpen, accounts, allocationAccounts, onClose, onSuccess, onConfigure }: Props) {
  const [amount, setAmount] = useState("");
  const [account, setAccount] = useState("");
  const [date, setDate] = useState(today);
  const [cycleOpen, setCycleOpen] = useState(false);
  const [startCycle, setStartCycle] = useState(true);
  const [cycleType, setCycleType] = useState("");
  const [cycleDays, setCycleDays] = useState("14");
  const [saveDefault, setSaveDefault] = useState(false);
  const [cycleLabel, setCycleLabel] = useState("Ikuti default");
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [previousReceipt, setPreviousReceipt] = useState<Receipt | null>(null);
  const [showAllocations, setShowAllocations] = useState(false);
  const [pending, setPending] = useState(false);
  const [editingAllocation, setEditingAllocation] = useState(false);
  const [allocationDraft, setAllocationDraft] = useState<Receipt["allocations"]>([]);
  const [error, setError] = useState("");
  const requestKey = useRef("");
  const inFlight = useRef(false);

  useEffect(() => {
    if (!isOpen) return;
    let active = true;
    setReceipt(null);
    setPreviousReceipt(null);
    setEditingAllocation(false);
    setShowAllocations(false);
    setError("");
    setCycleOpen(false);
    void authFetch("/api/v1/paycheck/config").then(async (response) => {
      if (!response.ok || !active) return;
      const { config } = await response.json();
      if (!active) return;
      setAccount((current) => current || config.source_account || "");
      setCycleLabel(config.cycle_type === "monthly_date" ? "Bulanan" : `${config.cycle_days} hari`);
    }).catch(() => {});
    void authFetch("/api/v1/paycheck/record/latest").then(async (response) => {
      if (!response.ok || !active) return;
      const data = await response.json();
      if (active) setPreviousReceipt(data);
    }).catch(() => {});
    return () => { active = false; };
  }, [isOpen]);

  const selectedAccount = accounts.includes(account) ? account : accounts[0] || "";
  const nominal = Number(amount.replace(/\D/g, ""));
  const canResume = previousReceipt && (previousReceipt.allocations.some((item) => item.account && item.amount > 0 && !item.transfer_id) ||
    (previousReceipt.allocations.length === 0 && allocationAccounts.some((item) => item.name !== previousReceipt.account)));
  const cycleSummary = !startCycle ? "Pakai siklus berjalan" :
    cycleType === "custom" ? `Siklus ${cycleDays} hari` :
    cycleType === "weekly" ? "Siklus 7 hari" : cycleType === "biweekly" ? "Siklus 14 hari" :
    cycleType === "monthly" ? "Siklus 30 hari" : `Siklus · ${cycleLabel}`;

  async function submit(path: string, body?: object, method = "POST") {
    if (inFlight.current) return;
    inFlight.current = true;
    setPending(true);
    setError("");
    try {
      const response = await authFetch(path, {
        method,
        ...(body ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {}),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(typeof data?.detail === "string" ? data.detail : "Perubahan gagal disimpan.");
      }
      const data: Receipt = await response.json();
      setReceipt(data);
      setPreviousReceipt(data);
      if (path === "/api/v1/paycheck/record") {
        requestKey.current = "";
        setAmount("");
        setCycleType("");
        setSaveDefault(false);
        setStartCycle(true);
      }
      if (method === "PUT") setEditingAllocation(false);
      onSuccess(path === "/api/v1/paycheck/record" && data.cycle_end ? { start: data.date, end: data.cycle_end } : undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Perubahan gagal disimpan.");
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  }

  const allocationTotal = allocationDraft.reduce((sum, item) => sum + item.amount, 0);
  const allocationRemaining = (receipt?.amount || 0) - allocationTotal;
  const availableTargets = allocationAccounts.filter((target) => target.name !== receipt?.account &&
    !allocationDraft.some((item) => item.account_id === target.id));
  const beginAllocationEdit = () => {
    if (!receipt) return;
    setAllocationDraft(receipt.allocations.map((item) => ({ ...item })));
    setEditingAllocation(true);
    setError("");
  };

  return (
    <CustomModal isOpen={isOpen} onClose={() => { if (!pending) onClose(); }}
      title={showAllocations ? "Bagi gaji" : receipt ? "Gaji tercatat" : "Catat gaji"} maxWidth="md">
      <div className="space-y-4">
        {error && <p role="alert" className="text-sm text-luma-coral">{error}</p>}
        {receipt ? (
          <>
            <div className="luma-matte space-y-1 p-4">
              <p className="ai7-type-metric">{rupiah.format(receipt.amount)}</p>
              <p className="text-sm text-luma-smoke">{receipt.account} · {receipt.date}</p>
              {receipt.cycle_end && <p className="text-sm text-luma-smoke">Siklus sampai {receipt.cycle_end}</p>}
            </div>
            {showAllocations && (
              <>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm text-luma-smoke">Catat transfer setelah uang dipindahkan.</p>
                  {!editingAllocation && <button type="button" disabled={pending} className="luma-action-secondary" onClick={beginAllocationEdit}>Sesuaikan pembagian</button>}
                </div>
                {editingAllocation ? (
                  <form className="payroll-form space-y-4" onSubmit={(event) => {
                    event.preventDefault();
                    if (allocationRemaining < 0) return;
                    void submit(`/api/v1/paycheck/record/${receipt.id}/allocations`, {
                      allocations: allocationDraft.map(({ account_id, amount, transfer_id }) => ({ account_id, amount, transfer_id })),
                      expected_allocations: receipt.allocations.map(({ account_id, amount, transfer_id }) => ({ account_id, amount, transfer_id })),
                    }, "PUT");
                  }}>
                    <p className="text-sm text-luma-smoke">Atur nominal untuk gaji ini. Sisa dana tetap di {receipt.account}.</p>
                    <ul className="space-y-3">
                      {allocationDraft.map((item) => (
                        <li key={item.account_id} className="space-y-2 border-b border-luma-smokeline pb-3">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <label htmlFor={`salary-allocation-${item.account_id}`} className="text-sm font-medium">{item.account || "Rekening tidak tersedia"}</label>
                            {item.transfer_id ? <span className="text-sm text-luma-sage">Tercatat · terkunci</span> :
                              <button type="button" disabled={pending} className="luma-text-action min-h-11" onClick={() => setAllocationDraft((rows) => rows.filter((row) => row.account_id !== item.account_id))}>Hapus alokasi</button>}
                          </div>
                          {item.transfer_id ? <p className="text-sm">{rupiah.format(item.amount)}</p> :
                            <CurrencyInput id={`salary-allocation-${item.account_id}`} disabled={pending} value={String(item.amount)}
                              onChange={(value) => setAllocationDraft((rows) => rows.map((row) => row.account_id === item.account_id ? { ...row, amount: Number(value.replace(/\D/g, "")) } : row))} />}
                        </li>
                      ))}
                    </ul>
                    {availableTargets.length > 0 && <div className="space-y-1">
                      <span className="text-sm">Tambah rekening tujuan</span>
                      <CustomSelect label="Tambah rekening tujuan" value="" placeholder="Pilih rekening" disabled={pending}
                        options={availableTargets.map((target) => ({ value: String(target.id), label: target.name }))}
                        onChange={(value) => {
                          const target = availableTargets.find((row) => row.id === Number(value));
                          if (target) setAllocationDraft((rows) => [...rows, { account_id: target.id, account: target.name, amount: 0, transfer_id: null }]);
                        }} />
                    </div>}
                    <div className="luma-matte space-y-1 p-3 text-sm" aria-live="polite">
                      <p>Total pembagian: {rupiah.format(allocationTotal)}</p>
                      <p className={allocationRemaining < 0 ? "text-luma-coral" : "text-luma-smoke"}>
                        {allocationRemaining < 0 ? `Melebihi gaji ${rupiah.format(-allocationRemaining)}` : `Tetap di ${receipt.account}: ${rupiah.format(allocationRemaining)}`}
                      </p>
                    </div>
                    <div className="flex flex-wrap justify-end gap-2">
                      <button type="button" disabled={pending} className="luma-action-secondary" onClick={() => { setEditingAllocation(false); setError(""); }}>Batal</button>
                      <button type="submit" className="luma-action-primary" disabled={pending || allocationRemaining < 0 || !Number.isSafeInteger(allocationTotal)}>{pending ? "Menyimpan…" : "Simpan pembagian"}</button>
                    </div>
                  </form>
                ) : (
                  <ul className="space-y-2">
                    {receipt.allocations.filter((item) => item.amount > 0).map((item) => (
                      <li key={item.account_id} className="flex flex-wrap items-center justify-between gap-2 border-b border-luma-smokeline py-2">
                        <div className="min-w-0"><p>{item.account || "Rekening tidak tersedia"}</p><p className="text-sm text-luma-smoke">{rupiah.format(item.amount)}</p></div>
                        {item.transfer_id ? <span className="text-sm text-luma-sage">Tercatat</span> :
                          <button type="button" className="luma-action-secondary" disabled={pending || !item.account}
                            onClick={() => void submit(`/api/v1/paycheck/record/${receipt.id}/transfer/${item.account_id}`)}>Catat transfer</button>}
                      </li>
                    ))}
                    {receipt.allocations.length === 0 && <li className="text-sm text-luma-smoke">Belum ada pembagian. Pilih “Sesuaikan pembagian” untuk menambah tujuan.</li>}
                  </ul>
                )}
              </>
            )}
            <div className="flex flex-wrap justify-end gap-2">
              <button type="button" disabled={pending} onClick={onClose} className="luma-action-secondary">Tutup</button>
              {!showAllocations && allocationAccounts.some((item) => item.name !== receipt.account) && (
                <button type="button" onClick={() => setShowAllocations(true)} className="luma-action-primary">Bagi gaji</button>
              )}
            </div>
          </>
        ) : (
          <form className="payroll-form space-y-4" onSubmit={(event) => {
            event.preventDefault();
            if (!selectedAccount || nominal <= 0) return;
            requestKey.current ||= crypto.randomUUID();
            void submit("/api/v1/paycheck/record", {
              request_key: requestKey.current, total_amount: nominal, account: selectedAccount, date,
              start_cycle: startCycle, cycle_type: startCycle && cycleType ? cycleType : null,
              cycle_days: startCycle && cycleType === "custom" ? Number(cycleDays) : null,
              save_cycle_default: startCycle && !!cycleType && saveDefault,
            });
          }}>
            <div>
              <label htmlFor="paycheck-amount" className="mb-1 block">Nominal gaji</label>
              <CurrencyInput id="paycheck-amount" value={amount} onChange={setAmount} placeholder="0" required />
            </div>
            <div className="space-y-1 text-sm">
              <span>Rekening penerima</span>
              <CustomSelect label="Rekening penerima" value={selectedAccount} onChange={setAccount}
                disabled={!accounts.length} placeholder="Tambahkan rekening dulu"
                options={accounts.map((name) => ({ value: name, label: name }))} />
            </div>
            <div className="space-y-1 text-sm">
              <label htmlFor="paycheck-received-date">Tanggal gaji masuk</label>
              <DateField id="paycheck-received-date" value={date} required max={today()} onChange={setDate} />
            </div>
            <div className="luma-matte space-y-2 p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm">{cycleSummary}</span>
                <button type="button" className="luma-text-action px-2" aria-expanded={cycleOpen}
                  onClick={() => setCycleOpen(!cycleOpen)}>Ubah</button>
              </div>
              {cycleOpen && (
                <>
                  <label className="flex min-h-11 items-center gap-2 text-sm">
                    <input type="checkbox" checked={startCycle} onChange={(event) => setStartCycle(event.target.checked)} />
                    Mulai siklus baru
                  </label>
                  {startCycle && (
                    <>
                      <div className="space-y-1 text-sm">
                        <span>Durasi siklus</span>
                        <CustomSelect label="Durasi siklus" value={cycleType}
                          onChange={(value) => { setCycleType(value); setSaveDefault(false); }}
                          options={[
                            { value: "", label: `Default · ${cycleLabel}` },
                            { value: "weekly", label: "Mingguan · 7 hari" },
                            { value: "biweekly", label: "Dua mingguan · 14 hari" },
                            { value: "monthly", label: "Bulanan · 30 hari" },
                            { value: "custom", label: "Kustom" },
                          ]} />
                      </div>
                      {cycleType === "custom" && <label className="block space-y-1 text-sm">
                        <span>Jumlah hari</span>
                        <input className="w-full" type="number" required min={1} max={365} value={cycleDays}
                          onChange={(event) => setCycleDays(event.target.value)} />
                      </label>}
                      {cycleType && <label className="flex min-h-11 items-center gap-2 text-sm">
                        <input type="checkbox" checked={saveDefault} onChange={(event) => setSaveDefault(event.target.checked)} />
                        Jadikan default
                      </label>}
                    </>
                  )}
                </>
              )}
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap gap-2">
                {canResume && <button type="button" className="luma-text-action" disabled={pending} onClick={() => {
                  setReceipt(previousReceipt);
                  setShowAllocations(true);
                }}>Lanjut bagi gaji</button>}
                <button type="button" className="luma-text-action" disabled={pending} onClick={onConfigure}>Atur alokasi</button>
              </div>
              <button type="submit" className="luma-action-primary" disabled={pending || !selectedAccount || nominal <= 0}>
                {pending ? "Menyimpan…" : "Simpan gaji"}
              </button>
            </div>
          </form>
        )}
      </div>
    </CustomModal>
  );
}
