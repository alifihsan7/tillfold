"use client";

import { DateField } from "@/components/ui/DateField";
import { useEffect, useId, useRef, useState } from "react";
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
  allocations: { account_id: number; account: string | null; amount: number; transfer_id: number | null; account_archived?: boolean }[];
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
const percentage = new Intl.NumberFormat("id-ID", { style: "percent", maximumFractionDigits: 2 });
const share = (amount: number, total: number) => total > 0 ? percentage.format(amount / total) : "—";
const today = () => new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Jakarta" });

const PAGE_SIZE = 2;

function pageOf<T>(items: T[], page: number, size = PAGE_SIZE) {
  const last = Math.max(0, Math.ceil(items.length / size) - 1);
  const current = Math.min(last, page);
  return { current, last, rows: items.slice(current * size, (current + 1) * size) };
}

function AllocationPager({ current, last, onChange, disabled }: {
  current: number;
  last: number;
  onChange: (page: number) => void;
  disabled: boolean;
}) {
  if (last === 0) return null;
  return (
    <nav aria-label="Halaman rekening tujuan" className="flex items-center justify-between gap-1 text-sm">
      <button type="button" className="luma-text-action px-1 disabled:opacity-50"
        disabled={disabled || current === 0} onClick={() => onChange(current - 1)}>Sebelumnya</button>
      <span className="tabular-nums text-luma-smoke" aria-live="polite">{current + 1} / {last + 1}</span>
      <button type="button" className="luma-text-action px-1 disabled:opacity-50"
        disabled={disabled || current === last} onClick={() => onChange(current + 1)}>Berikutnya</button>
    </nav>
  );
}

export function RecordPaycheckModal({ isOpen, accounts, allocationAccounts, onClose, onSuccess, onConfigure }: Props) {
  const [amount, setAmount] = useState("");
  const [destinationAmounts, setDestinationAmounts] = useState<Record<number, string>>({});
  const [account, setAccount] = useState("");
  const [date, setDate] = useState(today);
  const [step, setStep] = useState<"details" | "cycle" | "allocation">("details");
  const [allocationPage, setAllocationPage] = useState(0);
  const formId = useId();
  const stepTitle = useRef<HTMLParagraphElement>(null);
  const movedStep = useRef(false);

  function goTo(next: typeof step) {
    movedStep.current = true;
    setStep(next);
  }

  useEffect(() => {
    if (movedStep.current) {
      stepTitle.current?.focus({ preventScroll: true });
      movedStep.current = false;
    }
  }, [step]);
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
    setStep("details");
    setAllocationPage(0);
    void authFetch("/api/v1/paycheck/config?include_buckets=false").then(async (response) => {
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
  const destinations = allocationAccounts.filter((item) => item.name !== selectedAccount);
  const allocations = destinations.map(({ id }) => ({
    account_id: id,
    amount: Number((destinationAmounts[id] || "").replace(/\D/g, "")),
  })).filter((item) => item.amount > 0);
  const draftTotal = allocations.reduce((sum, item) => sum + item.amount, 0);
  const draftRemaining = nominal - draftTotal;
  const invalidNominal = !Number.isSafeInteger(nominal) || nominal <= 0 || nominal > 9_000_000_000_000_000;
  const invalidDraft = !Number.isSafeInteger(draftTotal) || draftRemaining < 0;
  const invalidCycle = startCycle && cycleType === "custom" &&
    (!Number.isInteger(Number(cycleDays)) || Number(cycleDays) < 1 || Number(cycleDays) > 365);
  const destinationPage = pageOf(destinations, allocationPage);
  const receiptRows = receipt?.allocations.filter((item) => item.amount > 0) ?? [];
  const displayedReceipt = pageOf(receiptRows, allocationPage);
  const draftPage = pageOf(allocationDraft, allocationPage, 1);
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
        setShowAllocations(data.allocations.length > 0);
        setAllocationPage(0);
        setDestinationAmounts({});
        requestKey.current = "";
        setAmount("");
        setCycleType("");
        setSaveDefault(false);
        setStartCycle(true);
      }
      if (method === "PUT") { setEditingAllocation(false); setAllocationPage(0); }
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
    setAllocationPage(0);
    setEditingAllocation(true);
    setError("");
  };

  const footer = (
    <div className="flex flex-wrap items-center justify-end gap-2">
      {receipt ? (
        editingAllocation ? <>
          <button type="button" disabled={pending} className="luma-action-secondary" onClick={() => {
            setEditingAllocation(false); setAllocationPage(0); setError("");
          }}>Batal</button>
          <button type="submit" form={formId} className="luma-action-primary"
            disabled={pending || allocationRemaining < 0 || !Number.isSafeInteger(allocationTotal)}>
            {pending ? "Menyimpan…" : "Simpan pembagian"}
          </button>
        </> : <>
          <button type="button" disabled={pending} onClick={onClose} className="luma-action-secondary">Tutup</button>
          {!showAllocations && allocationAccounts.some((item) => item.name !== receipt.account) && (
            <button type="button" onClick={() => setShowAllocations(true)} className="luma-action-primary">Bagi gaji</button>
          )}
        </>
      ) : <>
        {step === "allocation" && <button type="button" disabled={pending}
          className="luma-action-secondary" onClick={() => goTo("details")}>Kembali</button>}
        <button type="submit" form={formId} className="luma-action-primary"
          disabled={pending || (step === "cycle" ? invalidCycle : !selectedAccount || invalidNominal ||
            (step === "allocation" && (invalidDraft || invalidCycle)))}>
          {step === "cycle" ? "Pakai siklus ini" : step === "details" ? "Lanjut" : pending ? "Menyimpan…" : "Simpan gaji"}
        </button>
      </>}
    </div>
  );

  return (
    <CustomModal isOpen={isOpen} onClose={() => { if (!pending) onClose(); }}
      title={showAllocations ? "Bagi gaji" : receipt ? "Gaji tercatat" : "Catat gaji"} maxWidth="form" footer={footer}>
      <div className="payroll-flow space-y-3">
        {error && <p role="alert" className="text-sm text-luma-coral">{error}</p>}
        {receipt ? (
          <>
            {!editingAllocation && <div className="luma-matte space-y-1 p-2.5">
              <p className="ai7-type-metric">{rupiah.format(receipt.amount)}</p>
              <p className="text-sm text-luma-smoke">{receipt.account} · {receipt.date}{receipt.cycle_end && ` · sampai ${receipt.cycle_end}`}</p>
            </div>}
            {showAllocations && (
              <>
                {!editingAllocation && <div className="flex flex-wrap items-center justify-between gap-1">
                  <p className="text-sm text-luma-smoke">Catat transfer setelah uang dipindahkan.</p>
                  <button type="button" disabled={pending} className="luma-text-action" onClick={beginAllocationEdit}>Sesuaikan pembagian</button>
                </div>}
                {editingAllocation ? (
                  <form id={formId} className="payroll-form space-y-3" onSubmit={(event) => {
                    event.preventDefault();
                    if (allocationRemaining < 0 || !Number.isSafeInteger(allocationTotal)) return;
                    void submit(`/api/v1/paycheck/record/${receipt.id}/allocations`, {
                      allocations: allocationDraft.map(({ account_id, amount, transfer_id }) => ({ account_id, amount, transfer_id })),
                      expected_allocations: receipt.allocations.map(({ account_id, amount, transfer_id }) => ({ account_id, amount, transfer_id })),
                    }, "PUT");
                  }}>
                    <ul>
                      {draftPage.rows.map((item) => (
                        <li key={item.account_id} className="space-y-1">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <label htmlFor={`salary-allocation-${item.account_id}`} className="text-sm font-medium">{item.account || "Rekening tidak tersedia"}</label>
                            {item.transfer_id ? <span className="text-sm text-luma-sage">Tercatat · terkunci</span> :
                              <button type="button" disabled={pending} className="luma-text-action" onClick={() => setAllocationDraft((rows) => rows.filter((row) => row.account_id !== item.account_id))}>Hapus alokasi</button>}
                          </div>
                          <p className="text-xs text-luma-smoke">{share(item.amount, receipt.amount)} dari gaji</p>
                          {item.transfer_id ? <p className="text-sm">{rupiah.format(item.amount)}</p> :
                            <CurrencyInput id={`salary-allocation-${item.account_id}`} disabled={pending} value={String(item.amount)}
                              onChange={(value) => setAllocationDraft((rows) => rows.map((row) => row.account_id === item.account_id ? { ...row, amount: Number(value.replace(/\D/g, "")) } : row))} />}
                        </li>
                      ))}
                    </ul>
                    <AllocationPager {...draftPage} onChange={setAllocationPage} disabled={pending} />
                    {availableTargets.length > 0 && <div className="space-y-1">
                      <span className="text-sm">Tambah rekening tujuan</span>
                      <CustomSelect label="Tambah rekening tujuan" value="" placeholder="Pilih rekening" disabled={pending}
                        options={availableTargets.map((target) => ({ value: String(target.id), label: target.name }))}
                        onChange={(value) => {
                          const target = availableTargets.find((row) => row.id === Number(value));
                          if (target) {
                            setAllocationPage(allocationDraft.length);
                            setAllocationDraft((rows) => [...rows, { account_id: target.id, account: target.name, amount: 0, transfer_id: null }]);
                          }
                        }} />
                    </div>}
                    <div className="text-sm" aria-live="polite">
                      <p>Total pembagian: {rupiah.format(allocationTotal)}</p>
                      <p className={allocationRemaining < 0 ? "text-luma-coral" : "text-luma-smoke"}>
                        {allocationRemaining < 0 ? `Melebihi gaji ${rupiah.format(-allocationRemaining)}` : `Tetap di ${receipt.account}: ${rupiah.format(allocationRemaining)}`}
                      </p>
                    </div>
                  </form>
                ) : (
                  <ul className="space-y-2">
                    {displayedReceipt.rows.map((item) => (
                      <li key={item.account_id} className="flex flex-wrap items-center justify-between gap-2 border-b border-luma-smokeline py-2">
                        <div className="min-w-0"><p>{item.account || "Rekening tidak tersedia"}</p><p className="text-sm text-luma-smoke">{rupiah.format(item.amount)} · {share(item.amount, receipt.amount)}</p></div>
                        {item.transfer_id ? <span className="text-sm text-luma-sage">Tercatat</span> :
                          <button type="button" className="luma-action-secondary" disabled={pending || !item.account || item.account_archived}
                            onClick={() => void submit(`/api/v1/paycheck/record/${receipt.id}/transfer/${item.account_id}`)}>{item.account_archived ? "Rekening diarsipkan" : "Catat transfer"}</button>}
                      </li>
                    ))}
                    <li><AllocationPager {...displayedReceipt} onChange={setAllocationPage} disabled={pending} /></li>
                    {receipt.allocations.length === 0 && <li className="text-sm text-luma-smoke">Belum ada pembagian. Pilih “Sesuaikan pembagian” untuk menambah tujuan.</li>}
                  </ul>
                )}
              </>
            )}
          </>
        ) : (
          <form id={formId} className={step === "details" ? "payroll-form space-y-3 md:grid md:grid-cols-2 md:gap-3 md:space-y-0" : "payroll-form space-y-3"}
            onSubmit={(event) => {
            event.preventDefault();
            if (step === "cycle") {
              if (!invalidCycle) goTo("details");
              return;
            }
            if (!selectedAccount || invalidNominal) return;
            if (step === "details") { goTo("allocation"); return; }
            if (invalidDraft || invalidCycle) return;
            requestKey.current ||= crypto.randomUUID();
            void submit("/api/v1/paycheck/record", {
              request_key: requestKey.current, total_amount: nominal, account: selectedAccount, date, allocations,
              start_cycle: startCycle, cycle_type: startCycle && cycleType ? cycleType : null,
              cycle_days: startCycle && cycleType === "custom" ? Number(cycleDays) : null,
              save_cycle_default: startCycle && !!cycleType && saveDefault,
            });
          }}>
            <p ref={stepTitle} tabIndex={-1} className="md:col-span-2 text-xs text-luma-smoke">
              {step === "details" ? "1 dari 2 · Detail gaji" : step === "cycle" ? "Durasi dan awal siklus" : "2 dari 2 · Pembagian gaji"}
            </p>
            {step === "details" && <>
            <div>
              <label htmlFor="paycheck-amount" className="mb-1 block">Nominal gaji</label>
              <CurrencyInput id="paycheck-amount" value={amount} onChange={setAmount} placeholder="0" required />
            </div>
            <div className="space-y-1 text-sm">
              <span>Rekening penerima</span>
              <CustomSelect label="Rekening penerima" value={selectedAccount} onChange={(value) => { setAccount(value); setDestinationAmounts((rows) => {
                  const next = { ...rows };
                  const source = allocationAccounts.find((item) => item.name === value);
                  if (source) delete next[source.id];
                  return next;
                }); }}
                disabled={!accounts.length} placeholder="Tambahkan rekening dulu"
                options={accounts.map((name) => ({ value: name, label: name }))} />
            </div>
            <div className="space-y-1 text-sm">
              <label htmlFor="paycheck-received-date">Tanggal gaji masuk</label>
              <DateField id="paycheck-received-date" value={date} required max={today()} onChange={setDate} />
            </div>
            <div className="flex items-center justify-between gap-2 md:self-end">
              <span className="text-sm text-luma-smoke">{cycleSummary}</span>
              <button type="button" className="luma-text-action px-1" onClick={() => goTo("cycle")}>Ubah siklus</button>
            </div>
            <div className="md:col-span-2 flex flex-wrap gap-x-3 gap-y-1 text-sm">
              {canResume && <button type="button" className="luma-text-action" disabled={pending} onClick={() => {
                setAllocationPage(0);
                setReceipt(previousReceipt);
                setShowAllocations(true);
              }}>Lanjut bagi gaji</button>}
              <button type="button" className="luma-text-action" disabled={pending} onClick={onConfigure}>Atur rekening gaji</button>
            </div>
            </>}
            {step === "cycle" && <>
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
            </>}
            {step === "allocation" && (
              <fieldset className="space-y-3">
                <legend className="text-sm font-semibold">{rupiah.format(nominal)} · {selectedAccount}</legend>
                <p className="text-xs text-luma-smoke">Isi nominal tujuan. Kosongkan rekening yang tidak dapat bagian.</p>
                <div className="grid gap-2 md:grid-cols-2 md:gap-3">
                  {destinationPage.rows.map(({ id, name }) => {
                    const allocation = allocations.find((item) => item.account_id === id)?.amount ?? 0;
                    return (
                      <div className="grid grid-cols-[minmax(0,1fr)_5rem] items-end gap-2" key={id}>
                        <label className="block space-y-1 text-sm" htmlFor={`paycheck-destination-${id}`}>
                          <span>{name}</span>
                          <CurrencyInput id={`paycheck-destination-${id}`} value={destinationAmounts[id] ?? ""}
                            onChange={(value) => setDestinationAmounts((rows) => ({ ...rows, [id]: value }))} placeholder="0" />
                        </label>
                        <output className="pb-2 text-right text-sm text-luma-smoke tabular-nums">{share(allocation, nominal)}</output>
                      </div>
                    );
                  })}
                </div>

                <AllocationPager {...destinationPage} onChange={setAllocationPage} disabled={pending} />
                <p className={`text-sm ${invalidDraft ? "text-luma-coral" : "text-luma-smoke"}`} aria-live="polite">
                  {draftRemaining < 0 ? `Melebihi gaji ${rupiah.format(-draftRemaining)}` :
                    `Tetap di ${selectedAccount}: ${rupiah.format(draftRemaining)} · ${share(draftRemaining, nominal)}`}
                </p>
              </fieldset>
            )}
          </form>
        )}
      </div>
    </CustomModal>
  );
}
