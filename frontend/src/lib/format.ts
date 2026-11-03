/** Formatação de datas, números e rótulos — fuso America/Sao_Paulo (PRD §4.2). */

import type { ServerStatus } from "./types";

const TIME_ZONE = "America/Sao_Paulo";

const dateTimeFormatter = new Intl.DateTimeFormat("pt-BR", {
  timeZone: TIME_ZONE,
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

const shortTimeFormatter = new Intl.DateTimeFormat("pt-BR", {
  timeZone: TIME_ZONE,
  hour: "2-digit",
  minute: "2-digit",
});

export function formatDateTime(iso?: string | null): string {
  if (!iso) {
    return "—";
  }
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "—" : dateTimeFormatter.format(date);
}

export function formatShortTime(iso?: string | null): string {
  if (!iso) {
    return "";
  }
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "" : shortTimeFormatter.format(date);
}

export function formatRelative(iso?: string | null): string {
  if (!iso) {
    return "nunca";
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 0) {
    return "agora";
  }
  if (seconds < 10) {
    return "agora";
  }
  if (seconds < 60) {
    return `há ${seconds} s`;
  }
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `há ${minutes} min`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `há ${hours} h`;
  }
  const days = Math.floor(hours / 24);
  return `há ${days} d`;
}

export function formatBytes(value?: number | null): string {
  if (value === null || value === undefined) {
    return "—";
  }
  const units = ["B", "KB", "MB", "GB", "TB", "PB"];
  let size = value;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  const unit = units[index] ?? "B";
  const digits = size >= 100 || index === 0 ? 0 : 1;
  return `${size.toFixed(digits)} ${unit}`;
}

export function formatPercent(value?: number | null, digits = 1): string {
  if (value === null || value === undefined) {
    return "—";
  }
  return `${value.toFixed(digits)}%`;
}

export function formatBps(value?: number | null): string {
  if (value === null || value === undefined) {
    return "—";
  }
  const units = ["bps", "Kbps", "Mbps", "Gbps"];
  let rate = value;
  let index = 0;
  while (rate >= 1000 && index < units.length - 1) {
    rate /= 1000;
    index += 1;
  }
  const unit = units[index] ?? "bps";
  return `${rate.toFixed(rate >= 100 ? 0 : 1)} ${unit}`;
}

export function formatUptime(seconds?: number | null): string {
  if (seconds === null || seconds === undefined || seconds < 0) {
    return "—";
  }
  const days = Math.floor(seconds / 86_400);
  const hours = Math.floor((seconds % 86_400) / 3_600);
  const minutes = Math.floor((seconds % 3_600) / 60);
  if (days > 0) {
    return `${days}d ${hours}h`;
  }
  if (hours > 0) {
    return `${hours}h ${minutes}min`;
  }
  return `${minutes}min`;
}

const STATUS_LABELS: Record<ServerStatus, string> = {
  online: "Online",
  attention: "Atenção",
  offline: "Offline",
  paused: "Pausado",
  unprovisioned: "Não provisionado",
  disabled: "Desativado",
};

const STATUS_CLASSES: Record<ServerStatus, string> = {
  online: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  attention: "border-amber-500/40 bg-amber-500/10 text-amber-300",
  offline: "border-rose-500/40 bg-rose-500/10 text-rose-300",
  paused: "border-slate-600/60 bg-slate-700/20 text-slate-300",
  unprovisioned: "border-sky-500/40 bg-sky-500/10 text-sky-300",
  disabled: "border-slate-700 bg-slate-800/40 text-slate-400",
};

export function statusLabel(status: ServerStatus): string {
  return STATUS_LABELS[status] ?? status;
}

export function statusClasses(status: ServerStatus): string {
  return STATUS_CLASSES[status] ?? STATUS_CLASSES.disabled;
}

/** Verde/âmbar/vermelho para barras de uso. */
export function usageTone(value?: number | null): string {
  if (value === null || value === undefined) {
    return "bg-slate-600";
  }
  if (value >= 90) {
    return "bg-rose-500";
  }
  if (value >= 75) {
    return "bg-amber-400";
  }
  return "bg-emerald-500";
}

export const PANEL_LABELS: Record<string, string> = {
  easypanel: "Easypanel",
  portainer: "Portainer",
  icp: "ICP Integrator",
  none: "Nenhum",
};

export const ENVIRONMENT_LABELS: Record<string, string> = {
  production: "Produção",
  staging: "Homologação",
  development: "Desenvolvimento",
  other: "Outro",
};
