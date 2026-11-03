import type {
  Credential,
  DashboardSummary,
  Heartbeat,
  LatestTelemetry,
  LoginResponse,
  MeResponse,
  MetricsSeries,
  MetricsWindow,
  Page,
  ProvisioningToken,
  RotateCredential,
  Server,
  ServerInput,
  ServerStatus,
} from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const PREFIX = `${API_BASE}/api/v1`;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

/** Token CSRF double-submit: lido do cookie e reenviado no header. */
function csrfToken(): string {
  const name = "guardian_csrf=";
  const entry = document.cookie.split("; ").find((item) => item.startsWith(name));
  return entry ? decodeURIComponent(entry.slice(name.length)) : "";
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");

  if (init.body !== undefined && init.body !== null) {
    headers.set("Content-Type", "application/json");
  }
  if (method !== "GET" && method !== "HEAD") {
    headers.set("X-CSRF-Token", csrfToken());
  }

  let response: Response;
  try {
    response = await fetch(`${PREFIX}${path}`, {
      ...init,
      method,
      headers,
      credentials: "same-origin",
    });
  } catch {
    throw new ApiError(0, "network_error", "Não foi possível falar com o servidor.");
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    const error = (payload as { error?: { code?: string; message?: string } } | null)?.error;
    throw new ApiError(
      response.status,
      error?.code ?? "request_failed",
      error?.message ?? `Falha na requisição (HTTP ${response.status}).`,
    );
  }

  return payload as T;
}

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  }
  const asString = search.toString();
  return asString ? `?${asString}` : "";
}

export interface ServerFilters {
  status?: ServerStatus | "";
  panel?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

export const api = {
  login: (email: string, password: string) =>
    request<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  logout: () => request<void>("/auth/logout", { method: "POST" }),

  me: () => request<MeResponse>("/auth/me"),

  summary: () => request<DashboardSummary>("/dashboard/summary"),

  latestTelemetry: () => request<LatestTelemetry[]>("/telemetry/latest"),

  listServers: (filters: ServerFilters = {}) =>
    request<Page<Server>>(`/servers${query({ ...filters })}`),

  getServer: (id: string) => request<Server>(`/servers/${id}`),

  createServer: (payload: ServerInput) =>
    request<Server>("/servers", { method: "POST", body: JSON.stringify(payload) }),

  pauseServer: (id: string) => request<Server>(`/servers/${id}/pause`, { method: "POST" }),

  resumeServer: (id: string) => request<Server>(`/servers/${id}/resume`, { method: "POST" }),

  disableServer: (id: string) => request<Server>(`/servers/${id}/disable`, { method: "POST" }),

  credentials: (id: string) => request<Credential[]>(`/servers/${id}/credentials`),

  provisioningToken: (id: string) =>
    request<ProvisioningToken>(`/servers/${id}/provisioning-token`, { method: "POST" }),

  rotateCredential: (id: string) =>
    request<RotateCredential>(`/servers/${id}/rotate-credential`, { method: "POST" }),

  revokeCredentials: (id: string) =>
    request<{ revoked: number }>(`/servers/${id}/credentials/revoke`, { method: "POST" }),

  metrics: (id: string, window: MetricsWindow) =>
    request<MetricsSeries>(`/servers/${id}/metrics${query({ window })}`),

  heartbeats: (id: string, limit = 50) =>
    request<Heartbeat[]>(`/servers/${id}/heartbeats${query({ limit })}`),
};
