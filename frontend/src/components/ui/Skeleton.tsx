import React from "react";

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  className?: string;
}

export function Skeleton({ className = "", ...props }: SkeletonProps) {
  return (
    <div
      className={`animate-pulse rounded-xl bg-[var(--ui-control-bg)] ${className}`}
      {...props}
    />
  );
}

export function SkeletonCard({ className = "", children }: { className?: string; children?: React.ReactNode }) {
  return (
    <div className={`p-5 sm:p-6 rounded-3xl bg-obsidian-card border border-luma-smokeline shadow-sm ${className}`}>
      {children}
    </div>
  );
}
