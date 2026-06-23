"use client";
import { Loader2 } from "lucide-react";

interface GoogleButtonProps {
  onClick: () => void;
  loading?: boolean;
  disabled?: boolean;
}

function GoogleLogo() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M15.68 8.18c0-.57-.05-1.11-.14-1.64H8v3.1h4.3a3.67 3.67 0 0 1-1.59 2.41v2h2.57c1.5-1.38 2.4-3.42 2.4-5.87Z"
        fill="#4285F4"
      />
      <path
        d="M8 16c2.16 0 3.97-.72 5.29-1.94l-2.57-2a4.8 4.8 0 0 1-2.72.75 4.79 4.79 0 0 1-4.5-3.32H.86v2.06A8 8 0 0 0 8 16Z"
        fill="#34A853"
      />
      <path
        d="M3.5 9.49A4.83 4.83 0 0 1 3.25 8c0-.52.09-1.02.25-1.49V4.45H.86A8 8 0 0 0 0 8c0 1.29.31 2.51.86 3.55l2.64-2.06Z"
        fill="#FBBC05"
      />
      <path
        d="M8 3.19c1.22 0 2.31.42 3.17 1.24l2.37-2.37A8 8 0 0 0 .86 4.45L3.5 6.51A4.79 4.79 0 0 1 8 3.19Z"
        fill="#EA4335"
      />
    </svg>
  );
}

export function GoogleButton({ onClick, loading = false, disabled = false }: GoogleButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || loading}
      className="w-full flex items-center justify-center gap-3 px-4 py-2.5 rounded-xl border border-border bg-card text-foreground text-sm font-medium hover:bg-secondary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {loading ? <Loader2 size={16} className="animate-spin" /> : <GoogleLogo />}
      Continue with Google
    </button>
  );
}
