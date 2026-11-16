import { DateField } from "@/components/ui/DateField";
import React, { useState, useEffect } from "react";
import {
  Target,
  ShieldCheck,
  TrendingUp,
  AlertTriangle,
  Sparkles,
  Laptop,
  Plane,
  Car,
  Home,
  Coins,
  GraduationCap,
  Heart,
  CheckCircle2,
  Check,
} from "lucide-react";
import { CustomModal } from "@/components/ui/CustomModal";
import { CustomSelect } from "@/components/ui/CustomSelect";
import { CurrencyInput } from "@/components/ui/CurrencyInput";
import { authFetch } from "@/lib/api";

export interface GoalItem {
  id: number;
  name: string;
  target_amount: number;
  manual_current_amount: number;
  linked_account: string | null;
  target_date: string | null;
  category: string;
  icon: string;
  color: string;
  is_active: boolean;
  notes: string | null;
  current_amount: number;
  percentage: number;
  remaining_amount: number;
  estimated_cycles: number | null;
  estimated_months: number | null;
  estimated_finish_date: string | null;
  is_behind_schedule?: boolean;
  required_per_cycle?: number | null;
  created_at: string;
  updated_at: string;
}

interface EditGoalModalProps {
  goal: GoalItem | null;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  availableAccounts: string[];
}

const CATEGORY_OPTIONS = [
  { value: "Tabungan", label: "Tabungan / simpanan", description: "Dana dingin dan tabungan terkunci" },
  { value: "Investasi", label: "Investasi portofolio", description: "Reksadana, obligasi, saham, emas" },
  { value: "Darurat", label: "Dana darurat", description: "Cadangan likuid untuk situasi genting" },
  { value: "Wishlist", label: "Wishlist & impian", description: "Gadget, perlengkapan, hobi" },
  { value: "Lainnya", label: "Lain-lain", description: "Target tabungan kustom" },
];

const COLOR_OPTIONS = [
  { value: "emerald", label: "Emerald", dot: "bg-emerald-400" },
  { value: "cyan", label: "Cyan", dot: "bg-cyan-400" },
  { value: "amber", label: "Amber", dot: "bg-amber-400" },
  { value: "purple", label: "Purple", dot: "bg-purple-400" },
  { value: "rose", label: "Rose", dot: "bg-rose-400" },
];

const ICON_OPTIONS = [
  { id: "🎯", label: "Target", icon: Target },
  { id: "🛡️", label: "Tabungan", icon: ShieldCheck },
  { id: "📈", label: "Investasi", icon: TrendingUp },
  { id: "🚨", label: "Darurat", icon: AlertTriangle },
  { id: "✨", label: "Impian", icon: Sparkles },
  { id: "💻", label: "Gadget", icon: Laptop },
  { id: "✈️", label: "Liburan", icon: Plane },
  { id: "🚗", label: "Kendaraan", icon: Car },
  { id: "🏠", label: "Rumah", icon: Home },
  { id: "🪙", label: "Aset", icon: Coins },
  { id: "🎓", label: "Edukasi", icon: GraduationCap },
  { id: "❤️", label: "Keluarga", icon: Heart },
];

export function EditGoalModal({ goal, isOpen, onClose, onSuccess, availableAccounts }: EditGoalModalProps) {
  const [name, setName] = useState("");
  const [targetAmount, setTargetAmount] = useState("");
  const [category, setCategory] = useState("Tabungan");
  const [linkedAccount, setLinkedAccount] = useState("");
  const [manualCurrentAmount, setManualCurrentAmount] = useState("");
  const [targetDate, setTargetDate] = useState("");
  const [icon, setIcon] = useState("🎯");
  const [color, setColor] = useState("emerald");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (goal) {
      setName(goal.name);
      setTargetAmount(goal.target_amount.toString());
      setCategory(goal.category || "Tabungan");
      setLinkedAccount(goal.linked_account || "");
      setManualCurrentAmount(goal.manual_current_amount ? goal.manual_current_amount.toString() : "");
      setTargetDate(goal.target_date || "");
      setIcon(goal.icon || "🎯");
      setColor(goal.color || "emerald");
      setNotes(goal.notes || "");
      setError(null);
    }
  }, [goal, isOpen]);

  const accountOptions = [
    { value: "", label: "Manual (tanpa sinkronisasi rekening)", description: "Progres diinput/diupdate secara mandiri" },
    ...availableAccounts.map((acc) => ({
      value: acc,
      label: `Sinkronisasi Otomatis: ${acc}`,
      description: `Saldo diambil real-time dari mutasi rekening ${acc}`,
    })),
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!goal) return;
    setError(null);

    const nameTrim = name.trim();
    if (!nameTrim) {
      setError("Nama target tabungan wajib diisi");
      return;
    }

    const numTarget = parseInt(targetAmount.replace(/[^\d]/g, ""), 10);
    if (!numTarget || numTarget <= 0) {
      setError("Nominal target harus lebih dari Rp 0");
      return;
    }

    const numManual = manualCurrentAmount ? parseInt(manualCurrentAmount.replace(/[^\d]/g, ""), 10) : 0;

    setLoading(true);
    try {
      const res = await authFetch(`/api/v1/goals/${goal.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: nameTrim,
          target_amount: numTarget,
          manual_current_amount: numManual,
          linked_account: linkedAccount || null,
          target_date: targetDate || null,
          category,
          icon,
          color,
          notes: notes.trim() || null,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Gagal memperbarui target");
      }

      onSuccess();
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Terjadi kesalahan saat memperbarui target";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <CustomModal
      isOpen={isOpen}
      onClose={onClose}
      title="Ubah target tabungan"
      subtitle="Perbarui nominal sasaran, akun rekening tertaut, atau proyeksi tanggal"
      icon={<Target className="w-5 h-5 text-amberGold" />}
      accent="amber"
      maxWidth="lg"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="p-3 bg-coralFall/10 border border-coralFall/20 rounded-2xl text-coralFall text-xs">
            {error}
          </div>
        )}

        {/* Nama Target */}
        <div>
          <label className="block text-xs font-semibold text-zinc-400 mb-1.5">
            Nama target / milestone <span className="text-coralFall">*</span>
          </label>
          <input
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full bg-obsidian-panel border border-luma-smokeline rounded-2xl px-4 py-2.5 text-xs sm:text-sm text-white focus:outline-none focus:border-amberGold transition"
          />
        </div>

        {/* Nominal Target */}
        <div>
          <label className="block text-xs font-semibold text-zinc-400 mb-1.5">
            Nominal target (Rp) <span className="text-coralFall">*</span>
          </label>
          <CurrencyInput
            value={targetAmount}
            onChange={(raw) => setTargetAmount(raw)}
            placeholder="5.000.000"
            required
            accent={color === "emerald" ? "mint" : color === "cyan" ? "cyan" : color === "rose" ? "coral" : "amber"}
            quickAmounts={[1000000, 3000000, 5000000, 10000000]}
          />
        </div>

        {/* 2 Kolom: Rekening & Kategori */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-zinc-400 mb-1.5">
              Sinkronisasi rekening
            </label>
            <CustomSelect
              options={accountOptions}
              value={linkedAccount}
              onChange={(val) => setLinkedAccount(val)}
              placeholder="Pilih rekening terhubung"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-zinc-400 mb-1.5">
              Kategori
            </label>
            <CustomSelect
              options={CATEGORY_OPTIONS}
              value={category}
              onChange={(val) => setCategory(val)}
            />
          </div>
        </div>

        {!linkedAccount && (
          <div>
            <label className="block text-xs font-semibold text-zinc-400 mb-1.5">
              Saldo terkumpul saat ini (Rp)
            </label>
            <CurrencyInput
              value={manualCurrentAmount}
              onChange={(raw) => setManualCurrentAmount(raw)}
              placeholder="0"
              accent="amber"
            />
          </div>
        )}

        {/* Tema Warna - Grid 5 Kolom Proporsional */}
        <div>
          <label className="block text-xs font-semibold text-zinc-400 mb-1.5">
            Tema warna aksen
          </label>
          <div className="grid grid-cols-5 gap-2 pt-0.5">
            {COLOR_OPTIONS.map((c) => (
              <button
                key={c.value}
                type="button"
                onClick={() => setColor(c.value)}
                className={`flex items-center justify-center gap-1.5 py-2 px-2 rounded-2xl border text-xs font-medium transition cursor-pointer ${
                  color === c.value
                    ? "bg-obsidian-card border-amberGold text-white shadow-xs"
                    : "bg-obsidian-panel border-luma-smokeline text-zinc-400 hover:text-white hover:border-white/[0.16]"
                }`}
              >
                <span className={`w-2.5 h-2.5 rounded-full ${c.dot} shrink-0`} />
                <span className="truncate">{c.label}</span>
                {color === c.value && <Check className="w-3.5 h-3.5 text-amberGold shrink-0" />}
              </button>
            ))}
          </div>
        </div>

        {/* Pilih Ikon */}
        <div>
          <label className="block text-xs font-semibold text-zinc-400 mb-1.5">
            Pilih ikon
          </label>
          <div className="grid grid-cols-6 gap-2 pt-0.5">
            {ICON_OPTIONS.map((item) => {
              const IconComp = item.icon;
              const isSelected = icon === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setIcon(item.id)}
                  title={item.label}
                  className={`h-11 rounded-2xl flex items-center justify-center transition cursor-pointer ${
                    isSelected
                      ? "bg-amberGold/15 border-2 border-amberGold text-amberGold shadow-xs scale-105"
                      : "bg-obsidian-panel border border-luma-smokeline text-zinc-400 hover:text-white hover:border-white/[0.16]"
                  }`}
                >
                  <IconComp className="w-5 h-5" />
                </button>
              );
            })}
          </div>
        </div>

        {/* 2 Kolom: Tanggal & Catatan */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-zinc-400 mb-1.5">
              Target tanggal (opsional)
            </label>
            <DateField label="Target tanggal"
              value={targetDate}
              onChange={(dateValue) => setTargetDate(dateValue)}
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-zinc-400 mb-1.5">
              Catatan / rencana (opsional)
            </label>
            <input
              type="text"
              placeholder="Strategi alokasi atau tujuan..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full bg-obsidian-panel border border-luma-smokeline rounded-2xl px-3.5 py-2.5 text-xs sm:text-sm text-white focus:outline-none focus:border-amberGold transition placeholder:text-zinc-400"
            />
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex justify-end gap-3 pt-3 border-t border-luma-smokeline mt-5">
          <button
            type="button"
            onClick={onClose}
            className="px-5 py-2.5 rounded-2xl text-xs sm:text-sm font-medium text-zinc-400 hover:text-white border border-luma-smokeline hover:border-white/[0.16] transition cursor-pointer"
          >
            Batal
          </button>
          <button
            type="submit"
            disabled={loading}
            className="px-6 py-2.5 rounded-2xl text-xs sm:text-sm bg-amberGold text-slate-950 font-semibold hover:bg-amber-300 transition flex items-center gap-2 shadow-sm disabled:opacity-50 cursor-pointer"
          >
            {loading ? "Menyimpan..." : (
              <>
                <CheckCircle2 className="w-4 h-4 stroke-[2.5]" />
                Simpan perubahan
              </>
            )}
          </button>
        </div>
      </form>
    </CustomModal>
  );
}
