/** Tipos espelhando o contrato da API (backend/app/schemas). */

export type ServerStatus =
  | "unprovisioned"
  | "online"
  | "attention"
  | "offline"
  | "paused"
  | "disabled";

export type ServerEnvironment = "production" | "staging" | "development" | "other";
export type ServerPanel = "easypanel" | "portainer" | "icp" | "none";
export type UserRole = "admin" | "operator";
export type MetricsWindow = "1h" | "6h" | "24h" | "7d";

export interface User {
  id: number;
  email: string;
  name: string;
  role: UserRole;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface MeResponse {
  user: User;
  session_expires_at: string;
}

export interface LoginResponse {
  user: User;
}

export interface Server {
  id: string;
  name: string;
  hostname: string | null;
  ip_address: string | null;
  environment: ServerEnvironment;
  provider: string | null;
  region: string | null;
  panel: ServerPanel;
  os_name: string | null;
  os_version: string | null;
  kernel: string | null;
  architecture: string | null;
  tags: string[];
  notes: string | null;
  collection_interval_seconds: number;
  heartbeat_timeout_seconds: number;
  status: ServerStatus;
  status_reason: string | null;
  agent_version: string | null;
  last_heartbeat_at: string | null;
  last_metrics_at: string | null;
  registered_at: string | null;
  created_at: string;
  updated_at: string;
  active_credentials: number;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Credential {
  id: string;
  token_prefix: string;
  label: string;
  created_at: string;
  expires_at: string | null;
  revoked_at: string | null;
  revoked_reason: string | null;
  last_used_at: string | null;
}

export interface ProvisioningToken {
  server_id: string;
  token: string;
  token_prefix: string;
  expires_at: string;
  register_url: string;
}

export interface RotateCredential {
  server_id: string;
  credential: string;
  token_prefix: string;
  expires_at: string | null;
  revoked_previous: number;
}

export interface ServerCounts {
  total: number;
  online: number;
  attention: number;
  offline: number;
  paused: number;
  unprovisioned: number;
  disabled: number;
}

export interface AverageMetrics {
  cpu_percent: number | null;
  ram_percent: number | null;
  disk_percent: number | null;
  servers_considered: number;
}

export interface IncidentCounts {
  open: number;
  critical: number;
  warning: number;
  info: number;
  available: boolean;
}

export interface DashboardSummary {
  servers: ServerCounts;
  averages: AverageMetrics;
  incidents: IncidentCounts;
  last_heartbeat_at: string | null;
  data_age_seconds: number | null;
  generated_at: string;
}

export interface MetricPoint {
  at: string;
  cpu_percent: number | null;
  ram_percent: number | null;
  swap_percent: number | null;
  disk_percent: number | null;
  net_rx_bps: number | null;
  net_tx_bps: number | null;
}

export interface MetricsSeries {
  server_id: string;
  window: MetricsWindow;
  step_seconds: number;
  from_at: string;
  to_at: string;
  points: MetricPoint[];
}

export interface Heartbeat {
  received_at: string;
  agent_version: string;
  uptime_seconds: number;
}

export interface LatestTelemetry {
  server_id: string;
  collected_at: string;
  cpu_percent: number | null;
  ram_percent: number | null;
  swap_percent: number | null;
  disk_percent: number | null;
  net_rx_bps: number | null;
  net_tx_bps: number | null;
  uptime_seconds: number | null;
}

export interface ServerInput {
  name: string;
  hostname?: string | null;
  ip_address?: string | null;
  environment?: ServerEnvironment;
  panel?: ServerPanel;
  provider?: string | null;
  region?: string | null;
  tags?: string[];
  notes?: string | null;
  collection_interval_seconds?: number;
  heartbeat_timeout_seconds?: number;
}
