import { useEffect, type ButtonHTMLAttributes, type ReactNode } from "react";

import { ApiError } from "../lib/api";
import { statusClasses, statusLabel, usageTone } from "../lib/format";
import type { ServerStatus } from "../lib/types";

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 text-sm text-slate-400">
      <svg
        className="h-4 w-4 animate-spin text-emerald-400"
        viewBox="0 0 24 24"
        fill="none"
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="10" stroke="currentColor" strokeOpacity="0.25" strokeWidth="4" />
        <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
      </svg>
      <span>{label ?? "Carregando..."}</span>
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message =
    error instanceof ApiError
      ? error.message
      : error instanceof Error
        ? error.message
        : "Erro inesperado.";
  return (
    <div
      role="alert"
      className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-4 text-sm text-rose-200"
    >
      <p className="font-medium">Não foi possível carregar</p>
      <p className="mt-1 text-rose-200/80">{message}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="focus-ring mt-3 rounded-lg border border-rose-400/40 px-3 py-1.5 text-xs font-medium text-rose-100 hover:bg-rose-500/10"
        >
          Tentar novamente
        </button>
      ) : null}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-dashed border-slate-800 p-10 text-center">
      <p className="text-sm font-medium text-slate-200">{title}</p>
      {description ? <p className="mt-1 text-sm text-slate-500">{description}</p> : null}
      {action ? <div className="mt-4 flex justify-center">{action}</div> : null}
    </div>
  );
}

export function StatusBadge({ status }: { status: ServerStatus }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${statusClasses(status)}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden="true" />
      {statusLabel(status)}
    </span>
  );
}

export function KpiCard({
  label,
  value,
  hint,
  children,
}: {
  label: string;
  value?: string;
  hint?: string;
  children?: ReactNode;
}) {
  return (
    <div className="card p-4">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      {value !== undefined ? (
        <p className="mt-2 text-2xl font-semibold tabular-nums text-slate-100">{value}</p>
      ) : null}
      {children}
      {hint ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null}
    </div>
  );
}

export function UsageBar({ value }: { value?: number | null }) {
  const width = Math.max(0, Math.min(100, value ?? 0));
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800" aria-hidden="true">
      <div className={`h-full rounded-full ${usageTone(value)}`} style={{ width: `${width}%` }} />
    </div>
  );
}

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";

const BUTTON_CLASSES: Record<ButtonVariant, string> = {
  primary:
    "bg-emerald-500 text-slate-950 hover:bg-emerald-400 disabled:bg-emerald-500/40 disabled:text-slate-900",
  secondary:
    "border border-slate-700 text-slate-200 hover:border-slate-600 hover:bg-slate-800/60 disabled:opacity-50",
  danger:
    "border border-rose-500/40 text-rose-200 hover:bg-rose-500/10 disabled:opacity-50",
  ghost: "text-slate-300 hover:bg-slate-800/60 disabled:opacity-50",
};

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return (
    <button
      {...props}
      className={`focus-ring inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition disabled:cursor-not-allowed ${BUTTON_CLASSES[variant]} ${className}`}
    />
  );
}

export function Modal({
  open,
  title,
  onClose,
  children,
  footer,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}) {
  useEffect(() => {
    if (!open) {
      return;
    }
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-slate-950/80 p-4"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="w-full max-w-lg rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl"
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <h2 className="text-lg font-semibold text-slate-100">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fechar"
            className="focus-ring rounded-md p-1 text-slate-400 hover:bg-slate-800 hover:text-slate-200"
          >
            ✕
          </button>
        </div>
        {children}
        {footer ? <div className="mt-6 flex justify-end gap-2">{footer}</div> : null}
      </div>
    </div>
  );
}

/** Exibe um segredo (token/credencial) uma única vez, com botão de copiar. */
export function SecretBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3">
      <p className="text-xs font-medium uppercase tracking-wide text-amber-300">{label}</p>
      <div className="mt-2 flex items-start gap-2">
        <code className="min-w-0 flex-1 break-all rounded bg-slate-950/60 p-2 font-mono text-xs text-slate-200">
          {value}
        </code>
        <button
          type="button"
          onClick={() => void navigator.clipboard?.writeText(value)}
          className="focus-ring shrink-0 rounded-md border border-slate-700 px-2 py-1 text-xs text-slate-300 hover:bg-slate-800"
        >
          Copiar
        </button>
      </div>
      <p className="mt-2 text-xs text-amber-200/70">
        Este valor não será exibido novamente. Guarde-o agora.
      </p>
    </div>
  );
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-400">
        {label}
      </span>
      {children}
      {hint ? <span className="mt-1 block text-xs text-slate-500">{hint}</span> : null}
    </label>
  );
}

export const inputClasses =
  "focus-ring w-full rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600";
