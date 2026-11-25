import React from "react";
import { AlertTriangle, Trash2 } from "@/components/icons";
import { CustomModal } from "./CustomModal";

interface ConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title?: string;
  message?: string;
  confirmText?: string;
  cancelText?: string;
  danger?: boolean;
  loading?: boolean;
}

export function ConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  title = "Konfirmasi Tindakan",
  message = "Apakah kamu yakin ingin melanjutkan tindakan ini?",
  confirmText = "Konfirmasi",
  cancelText = "Batal",
  danger = true,
  loading = false,
}: ConfirmModalProps) {
  return (
    <CustomModal
      isOpen={isOpen}
      onClose={onClose}
      title={title}
      icon={danger ? <Trash2 className="w-5 h-5" /> : <AlertTriangle className="w-5 h-5" />}
      accent={danger ? "coral" : "amber"}
      maxWidth="sm"
    >
      <div className="space-y-5">
        <p className="text-xs sm:text-sm text-luma-secondary leading-relaxed">
          {message}
        </p>

        <div className="ui-dialog-actions">
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="luma-action-secondary"
          >
            {cancelText}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className={danger
              ? "luma-action-primary !bg-[var(--luma-coral)] !text-luma-charcoal hover:!brightness-110 disabled:cursor-not-allowed"
              : "luma-action-primary disabled:cursor-not-allowed"}
          >
            {loading ? "Memproses…" : confirmText}
          </button>
        </div>
      </div>
    </CustomModal>
  );
}
