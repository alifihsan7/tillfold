"use client";

import React, { useEffect, useRef, useState } from "react";
import { User, Send, LogOut, Unlink, Trash2, ExternalLink, FileSpreadsheet, Copy, Check, RefreshCw } from "lucide-react";
import { CustomModal } from "./ui/CustomModal";
import { authFetch, setStoredUser, UserProfile, syncGoogleSheets } from "@/lib/api";

const SERVICE_ACCOUNT_EMAIL = "ai7-finance-sync@ai7-finance-sync.iam.gserviceaccount.com";

interface UserProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
  user: UserProfile;
  onUserUpdated: (updated: UserProfile) => void;
  onLogout: () => void;
  initialTab?: "profile" | "telegram" | "sheets";
}

export function UserProfileModal({
  isOpen,
  onClose,
  user,
  onUserUpdated,
  onLogout,
  initialTab = "profile",
}: UserProfileModalProps) {
  const [activeTab, setActiveTab] = useState<"profile" | "telegram" | "sheets">(initialTab);
  const [fullName, setFullName] = useState(user.full_name);
  const [email, setEmail] = useState(user.email || "");
  const [newPassword, setNewPassword] = useState("");
  const [sheetUrl, setSheetUrl] = useState(
    user.google_spreadsheet_id
      ? `https://docs.google.com/spreadsheets/d/${user.google_spreadsheet_id}`
      : ""
  );
  const [loading, setLoading] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [copiedEmail, setCopiedEmail] = useState(false);
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showUnlinkConfirm, setShowUnlinkConfirm] = useState(false);
  const [showUnlinkSheetConfirm, setShowUnlinkSheetConfirm] = useState(false);
  const [link, setLink] = useState<{ url: string; expiresAt: number } | null>(null);
  const [expired, setExpired] = useState(false);
  const inFlight = useRef(false);
  const isConnected = Boolean(user.telegram_chat_id && user.telegram_mode !== "custom");

  const updateUser = (updated: UserProfile) => {
    setStoredUser(updated);
    onUserUpdated(updated);
  };

  useEffect(() => {
    if (isOpen) {
      if (initialTab) {
        setActiveTab(initialTab);
      }
      setFullName(user.full_name);
      setEmail(user.email || "");
      setSheetUrl(
        user.google_spreadsheet_id
          ? `https://docs.google.com/spreadsheets/d/${user.google_spreadsheet_id}`
          : ""
      );
      setMsg(null);
      setShowUnlinkSheetConfirm(false);
    }
  }, [isOpen, initialTab, user]);

  useEffect(() => {
    if (!isOpen || !link) return;
    const timer = window.setTimeout(() => setExpired(true), Math.max(0, link.expiresAt - Date.now()));
    return () => window.clearTimeout(timer);
  }, [isOpen, link]);

  const handleSaveProfile = async (event: React.FormEvent) => {
    event.preventDefault();
    if (inFlight.current) return;
    inFlight.current = true;
    setLoading(true);
    setMsg(null);
    try {
      const payload: Record<string, unknown> = { full_name: fullName.trim(), email: email.trim() || null };
      if (newPassword.trim()) {
        if (newPassword.trim().length < 8) throw new Error("Password baru minimal 8 karakter.");
        payload.password = newPassword.trim();
      }
      const response = await authFetch("/api/v1/auth/me", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Gagal menyimpan profil.");
      updateUser(data);
      setNewPassword("");
      setMsg({ type: "success", text: "Profil diperbarui." });
    } catch (error) {
      setMsg({ type: "error", text: error instanceof Error ? error.message : "Gagal menyimpan profil." });
    } finally {
      inFlight.current = false;
      setLoading(false);
    }
  };

  const handleCopyServiceEmail = async () => {
    try {
      await navigator.clipboard.writeText(SERVICE_ACCOUNT_EMAIL);
      setCopiedEmail(true);
      setTimeout(() => setCopiedEmail(false), 2000);
    } catch {
      // Fallback if clipboard API is restricted
      setMsg({ type: "success", text: `Salin manual: ${SERVICE_ACCOUNT_EMAIL}` });
    }
  };

  const handleSaveSheets = async (event: React.FormEvent) => {
    event.preventDefault();
    if (inFlight.current) return;
    inFlight.current = true;
    setLoading(true);
    setMsg(null);
    try {
      const trimmed = sheetUrl.trim();
      const response = await authFetch("/api/v1/auth/me", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ google_sheet_url: trimmed || null }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Gagal menyimpan link spreadsheet.");
      updateUser(data);
      if (data.google_spreadsheet_id) {
        setSheetUrl(`https://docs.google.com/spreadsheets/d/${data.google_spreadsheet_id}`);
        setMsg({ type: "success", text: "Google Spreadsheet berhasil ditautkan dan disimpan." });
      } else {
        setSheetUrl("");
        setMsg({ type: "success", text: "Tautan Google Spreadsheet berhasil dilepas." });
      }
    } catch (error) {
      setMsg({ type: "error", text: error instanceof Error ? error.message : "Gagal menyimpan link Google Spreadsheet." });
    } finally {
      inFlight.current = false;
      setLoading(false);
    }
  };

  const handleUnlinkSheets = async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    setLoading(true);
    setMsg(null);
    try {
      const response = await authFetch("/api/v1/auth/me", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ google_spreadsheet_id: null }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Gagal memutuskan spreadsheet.");
      updateUser(data);
      setSheetUrl("");
      setShowUnlinkSheetConfirm(false);
      setMsg({ type: "success", text: "Tautan Google Spreadsheet diputuskan." });
    } catch (error) {
      setMsg({ type: "error", text: error instanceof Error ? error.message : "Gagal memutuskan Google Spreadsheet." });
    } finally {
      inFlight.current = false;
      setLoading(false);
    }
  };

  const handleSyncNow = async () => {
    if (inFlight.current || isSyncing) return;
    setIsSyncing(true);
    setMsg(null);
    try {
      const res = await syncGoogleSheets();
      setMsg({
        type: "success",
        text: `Sinkronisasi berhasil! Lembar: ${res.sheet_title || "Snapshot"} (${res.transaction_count ?? 0} transaksi disinkronkan).`,
      });
    } catch (error) {
      setMsg({ type: "error", text: error instanceof Error ? error.message : "Gagal menyinkronkan data ke Google Sheets." });
    } finally {
      setIsSyncing(false);
    }
  };

  const handleConnect = async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    setLoading(true);
    setMsg(null);
    setLink(null);
    try {
      const response = await authFetch("/api/v1/auth/link-telegram", { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Gagal membuat tautan Telegram.");
      setLink({ url: data.url, expiresAt: Date.now() + data.expires_in * 1000 });
      setExpired(false);
    } catch (error) {
      setMsg({ type: "error", text: error instanceof Error ? error.message : "Gagal menghubungkan Telegram." });
    } finally {
      inFlight.current = false;
      setLoading(false);
    }
  };

  const handleCheckConnection = async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    setLoading(true);
    setMsg(null);
    try {
      const response = await authFetch("/api/v1/auth/me");
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Gagal memeriksa koneksi.");
      updateUser(data);
      const connected = data.telegram_chat_id && data.telegram_mode === "shared";
      if (connected) setLink(null);
      setMsg({
        type: connected ? "success" : "error",
        text: connected
          ? "Telegram terhubung. Ketik /menu di bot untuk mulai."
          : "Belum terhubung. Buka tautan bot dan tekan Start, lalu cek lagi.",
      });
    } catch (error) {
      setMsg({ type: "error", text: error instanceof Error ? error.message : "Gagal memeriksa koneksi." });
    } finally {
      inFlight.current = false;
      setLoading(false);
    }
  };

  const handleUnlink = async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    setLoading(true);
    setMsg(null);
    try {
      const response = await authFetch("/api/v1/auth/unlink-telegram", { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Gagal memutuskan tautan.");
      updateUser(data);
      setLink(null);
      setShowUnlinkConfirm(false);
      setMsg({ type: "success", text: "Telegram diputuskan." });
    } catch (error) {
      setMsg({ type: "error", text: error instanceof Error ? error.message : "Gagal memutuskan tautan." });
    } finally {
      inFlight.current = false;
      setLoading(false);
    }
  };

  const handleDeleteAccount = async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    setLoading(true);
    setMsg(null);
    try {
      const response = await authFetch("/api/v1/auth/me", { method: "DELETE" });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Gagal menghapus akun.");
      }
      onLogout();
    } catch (error) {
      setMsg({ type: "error", text: error instanceof Error ? error.message : "Gagal menghapus akun." });
    } finally {
      inFlight.current = false;
      setLoading(false);
    }
  };

  const fieldClass = "w-full min-h-11 rounded-[var(--ai7-radius-control)] border border-luma-smokeline bg-luma-coal px-3 text-base text-luma-ivory focus:border-luma-ember focus:outline-none transition-colors";

  return (
    <CustomModal
      isOpen={isOpen}
      onClose={onClose}
      title="Profil & pengaturan akun"
      subtitle={"Kelola akun @" + user.username}
      icon={<User className="h-4 w-4" />}
      maxWidth="lg"
    >
      <div className="space-y-5 text-sm text-luma-ivory">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="font-medium">{user.full_name}</p>
            <p className="text-luma-smoke">@{user.username}</p>
          </div>
          <button type="button" onClick={onLogout} className="luma-action-secondary cursor-pointer">
            <LogOut className="h-4 w-4" />Keluar
          </button>
        </div>

        <div className="flex flex-wrap gap-2" role="tablist" aria-label="Pengaturan akun">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "profile"}
            aria-controls="profile-panel"
            id="profile-tab"
            onClick={() => { setActiveTab("profile"); setMsg(null); }}
            className={`cursor-pointer ${activeTab === "profile" ? "luma-action-primary" : "luma-action-secondary"}`}
          >
            Profil
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "telegram"}
            aria-controls="telegram-panel"
            id="telegram-tab"
            onClick={() => { setActiveTab("telegram"); setMsg(null); }}
            className={`cursor-pointer ${activeTab === "telegram" ? "luma-action-primary" : "luma-action-secondary"}`}
          >
            <Send className="h-4 w-4" />Integrasi Telegram
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "sheets"}
            aria-controls="sheets-panel"
            id="sheets-tab"
            onClick={() => { setActiveTab("sheets"); setMsg(null); }}
            className={`cursor-pointer ${activeTab === "sheets" ? "luma-action-primary" : "luma-action-secondary"}`}
          >
            <FileSpreadsheet className="h-4 w-4" />Google Sheets
          </button>
        </div>

        {msg && (
          <p role={msg.type === "error" ? "alert" : "status"} className={`text-xs ${msg.type === "error" ? "text-coralFall" : "text-mintRise"}`}>
            {msg.text}
          </p>
        )}

        {/* Tab 1: Profil */}
        {activeTab === "profile" && (
          <div role="tabpanel" id="profile-panel" aria-labelledby="profile-tab" className="space-y-5">
            <form onSubmit={handleSaveProfile} className="space-y-4">
              <div className="space-y-2">
                <label htmlFor="profile-name">Nama lengkap</label>
                <input
                  id="profile-name"
                  value={fullName}
                  onChange={(event) => setFullName(event.target.value)}
                  className={fieldClass}
                  required
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="profile-email">Email</label>
                <input
                  id="profile-email"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className={fieldClass}
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="profile-password">Password baru</label>
                <input
                  id="profile-password"
                  type="password"
                  autoComplete="new-password"
                  minLength={8}
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  className={fieldClass}
                  aria-describedby="profile-password-help"
                />
                <p id="profile-password-help" className="text-xs text-luma-smoke">Kosongkan jika belum ingin mengganti password.</p>
              </div>
              <button type="submit" disabled={loading} className="luma-action-primary cursor-pointer">
                {loading ? "Menyimpan…" : "Simpan profil"}
              </button>
            </form>
            <div className="space-y-3 border-t border-luma-smokeline pt-5">
              <p>Hapus akun beserta seluruh data keuangan secara permanen.</p>
              {!showDeleteConfirm ? (
                <button type="button" className="luma-action-secondary text-coralFall cursor-pointer" onClick={() => setShowDeleteConfirm(true)}>
                  <Trash2 className="h-4 w-4" />Hapus akun
                </button>
              ) : (
                <div className="space-y-3">
                  <p role="alert">Seluruh data akan dihapus dan kamu akan keluar. Lanjutkan?</p>
                  <div className="flex gap-2">
                    <button type="button" disabled={loading} className="luma-action-secondary cursor-pointer" onClick={() => setShowDeleteConfirm(false)}>
                      Batal
                    </button>
                    <button type="button" disabled={loading} className="luma-action-secondary text-coralFall cursor-pointer" onClick={handleDeleteAccount}>
                      {loading ? "Menghapus…" : "Ya, hapus akun"}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Tab 2: Telegram */}
        {activeTab === "telegram" && (
          <div role="tabpanel" id="telegram-panel" aria-labelledby="telegram-tab" className="space-y-4">
            <div className="space-y-2 rounded-[var(--ai7-radius-panel)] border border-luma-smokeline bg-luma-coal p-5">
              <h3 className="font-medium">Bot Tillfold</h3>
              <p className="text-luma-smoke">Catat transaksi, kirim struk, dan cek saldo lewat Telegram. Semua pengguna memakai satu bot dengan akun keuangan masing-masing.</p>
              <p className={isConnected ? "text-mintRise" : "text-luma-smoke"}>{isConnected ? "Terhubung · ID " + user.telegram_chat_id : "Belum terhubung"}</p>
              {user.telegram_mode === "custom" && <p>Hubungkan ulang untuk beralih dari bot pribadi ke bot Tillfold.</p>}
            </div>
            {!isConnected && !link && (
              <button type="button" onClick={handleConnect} disabled={loading} className="luma-action-primary cursor-pointer">
                {loading ? "Menyiapkan tautan…" : "Hubungkan Telegram"}
              </button>
            )}
            {link && (
              <div className="space-y-3">
                <p>Buka bot dan tekan Start. Tautan ini berlaku 10 menit dan hanya bisa dipakai sekali. Simpan tautan untuk diri sendiri.</p>
                {expired ? (
                  <p role="status" className="text-coralFall">Tautan kedaluwarsa. Buat tautan baru untuk melanjutkan.</p>
                ) : (
                  <a href={link.url} target="_blank" rel="noreferrer" className="luma-action-primary">
                    <ExternalLink className="h-4 w-4" />Buka bot Tillfold
                  </a>
                )}
                <div className="flex flex-wrap gap-2">
                  <button type="button" onClick={handleCheckConnection} disabled={loading} className="luma-action-secondary cursor-pointer">
                    {loading ? "Memeriksa…" : "Cek koneksi"}
                  </button>
                  <button type="button" onClick={handleConnect} disabled={loading} className="luma-action-secondary cursor-pointer">
                    Buat tautan baru
                  </button>
                </div>
              </div>
            )}
            {(isConnected || user.telegram_mode === "custom") && !showUnlinkConfirm && (
              <button type="button" onClick={() => setShowUnlinkConfirm(true)} disabled={loading} className="luma-action-secondary cursor-pointer">
                <Unlink className="h-4 w-4" />Putuskan Telegram
              </button>
            )}
            {showUnlinkConfirm && (
              <div className="space-y-3">
                <p>Putuskan koneksi Telegram dari akun ini?</p>
                <div className="flex gap-2">
                  <button type="button" onClick={() => setShowUnlinkConfirm(false)} disabled={loading} className="luma-action-secondary cursor-pointer">
                    Batal
                  </button>
                  <button type="button" onClick={handleUnlink} disabled={loading} className="luma-action-secondary text-coralFall cursor-pointer">
                    {loading ? "Memutuskan…" : "Putuskan"}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab 3: Google Sheets */}
        {activeTab === "sheets" && (
          <div role="tabpanel" id="sheets-panel" aria-labelledby="sheets-tab" className="space-y-4">
            <div className="space-y-3 rounded-[var(--ai7-radius-panel)] border border-luma-smokeline bg-luma-coal p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="font-medium text-luma-ivory">Google Sheets Rapor Keuangan</h3>
                  <p className="text-luma-smoke text-xs mt-1">
                    Hubungkan Google Spreadsheet pribadi untuk membuat cadangan real-time serta visualisasi laporan siklus payroll secara otomatis.
                  </p>
                </div>
                {user.google_spreadsheet_id ? (
                  <span className="inline-flex items-center gap-1.5 text-xs text-mintRise font-medium px-2.5 py-1 rounded-full bg-mintRise/10 border border-mintRise/25 shrink-0">
                    <span className="w-1.5 h-1.5 rounded-full bg-mintRise"></span>
                    Terhubung
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 text-xs text-luma-smoke font-medium px-2.5 py-1 rounded-full bg-white/[0.04] border border-luma-smokeline shrink-0">
                    <span className="w-1.5 h-1.5 rounded-full bg-luma-smoke"></span>
                    Belum Terhubung
                  </span>
                )}
              </div>

              {user.google_spreadsheet_id && (
                <div className="pt-2 border-t border-luma-smokeline/60 flex flex-wrap items-center justify-between gap-2 text-xs">
                  <span className="font-mono text-luma-smoke truncate max-w-[280px]">
                    ID: {user.google_spreadsheet_id}
                  </span>
                  <a
                    href={`https://docs.google.com/spreadsheets/d/${user.google_spreadsheet_id}`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 text-luma-sage hover:underline font-medium"
                  >
                    <ExternalLink className="h-3.5 w-3.5" />
                    Buka Spreadsheet
                  </a>
                </div>
              )}
            </div>

            {/* Microcopy: Editor Access */}
            <div className="rounded-[var(--ai7-radius-panel)] border border-luma-smokeline bg-luma-coal/60 p-4 space-y-2.5">
              <p className="text-xs text-luma-smoke">
                Bagikan akses <span className="text-luma-ivory font-medium">Editor</span> pada spreadsheet-mu ke:
              </p>
              <div className="flex items-center justify-between gap-2 rounded-[var(--ai7-radius-control)] bg-black/40 border border-luma-smokeline px-3 py-2">
                <code className="text-xs font-mono text-luma-sage select-all break-all">
                  {SERVICE_ACCOUNT_EMAIL}
                </code>
                <button
                  type="button"
                  onClick={handleCopyServiceEmail}
                  className="luma-action-secondary !min-h-0 !py-1 !px-2.5 text-xs shrink-0 flex items-center gap-1.5 cursor-pointer hover:border-luma-sage/50"
                  title="Salin email Service Account"
                >
                  {copiedEmail ? (
                    <>
                      <Check className="h-3.5 w-3.5 text-mintRise" />
                      <span className="text-mintRise font-medium">Tersalin!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="h-3.5 w-3.5 text-luma-smoke" />
                      <span>Salin</span>
                    </>
                  )}
                </button>
              </div>
              <p className="text-[11px] text-luma-smoke leading-relaxed">
                Di Google Sheets: Klik <strong className="text-luma-ivory font-medium">Share</strong> (Bagikan), masukkan email di atas, atur peran sebagai <strong className="text-luma-ivory font-medium">Editor</strong>, lalu simpan.
              </p>
            </div>

            {/* Input Form */}
            <form onSubmit={handleSaveSheets} className="space-y-4">
              <div className="space-y-2">
                <label htmlFor="sheets-link" className="font-medium text-luma-ivory">Google Spreadsheet Link</label>
                <input
                  id="sheets-link"
                  type="text"
                  value={sheetUrl}
                  onChange={(event) => setSheetUrl(event.target.value)}
                  placeholder="https://docs.google.com/spreadsheets/d/..."
                  className={fieldClass}
                  aria-describedby="sheets-link-help"
                />
                <p id="sheets-link-help" className="text-xs text-luma-smoke">
                  Tempel URL lengkap spreadsheet Google Sheets atau Spreadsheet ID unik Anda.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2 pt-1">
                <button type="submit" disabled={loading || isSyncing} className="luma-action-primary cursor-pointer">
                  {loading ? "Menyimpan…" : "Simpan link spreadsheet"}
                </button>

                {user.google_spreadsheet_id && (
                  <button
                    type="button"
                    onClick={handleSyncNow}
                    disabled={loading || isSyncing}
                    className="luma-action-secondary cursor-pointer"
                  >
                    <RefreshCw className={`h-4 w-4 text-luma-sage ${isSyncing ? "animate-spin" : ""}`} />
                    {isSyncing ? "Menyinkronkan…" : "Sync sekarang"}
                  </button>
                )}
              </div>
            </form>

            {user.google_spreadsheet_id && (
              <div className="space-y-3 border-t border-luma-smokeline pt-4 mt-2">
                {!showUnlinkSheetConfirm ? (
                  <button
                    type="button"
                    onClick={() => setShowUnlinkSheetConfirm(true)}
                    disabled={loading || isSyncing}
                    className="luma-action-secondary text-coralFall cursor-pointer"
                  >
                    <Unlink className="h-4 w-4" />
                    Putuskan spreadsheet
                  </button>
                ) : (
                  <div className="space-y-3">
                    <p className="text-xs text-coralFall" role="alert">
                      Lepaskan tautan Google Spreadsheet dari akun ini? Data yang tersimpan di Google Sheets tidak akan terhapus.
                    </p>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => setShowUnlinkSheetConfirm(false)}
                        disabled={loading}
                        className="luma-action-secondary cursor-pointer"
                      >
                        Batal
                      </button>
                      <button
                        type="button"
                        onClick={handleUnlinkSheets}
                        disabled={loading}
                        className="luma-action-secondary text-coralFall cursor-pointer"
                      >
                        {loading ? "Memutuskan…" : "Ya, putuskan"}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </CustomModal>
  );
}
