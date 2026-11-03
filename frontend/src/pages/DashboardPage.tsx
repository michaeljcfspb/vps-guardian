import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { NewServerModal } from "../components/NewServerModal";
import {
  Button,
  EmptyState,
  ErrorBox,
  KpiCard,
  Spinner,
  StatusBadge,
  UsageBar,
  inputClasses,
} from "../components/ui";
import { api } from "../lib/api";
import { useMe } from "../lib/auth";
import { formatDateTime, formatPercent, formatRelative } from "../lib/format";
import type { LatestTelemetry, Server, ServerStatus } from "../lib/types";

const STATUS_OPTIONS: { value: ServerStatus | ""; label: string }[] = [
  { value: "", label: "Todos os estados" },
  { value: "online", label: "Online" },
  { value: "attention", label: "Atenção" },
  { value: "offline", label: "Offline" },
  { value: "unprovisioned", label: "Não provisionado" },
  { value: "paused", label: "Pausado" },
  { value: "disabled", label: "Desativado" },
];

export function DashboardPage() {
  const me = useMe();
  const isAdmin = me.data?.user.role === "admin";
  const [status, setStatus] = useState<ServerStatus | "">("");
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);

  const summary = useQuery({
    queryKey: ["summary"],
    queryFn: api.summary,
    refetchInterval: 15_000,
  });

  const servers = useQuery({
    queryKey: ["servers", status, search],
    queryFn: () => api.listServers({ status, search, limit: 200 }),
    refetchInterval: 15_000,
  });

  const telemetry = useQuery({
    queryKey: ["telemetry", "latest"],
    queryFn: api.latestTelemetry,
    refetchInterval: 15_000,
  });

  const latestByServer = useMemo(() => {
    const map = new Map<string, LatestTelemetry>();
    for (const item of telemetry.data ?? []) {
      map.set(item.server_id, item);
    }
    return map;
  }, [telemetry.data]);

  if (summary.isLoading || servers.isLoading) {
    return (
      <div className="py-16">
        <Spinner label="Carregando dashboard..." />
      </div>
    );
  }

  if (summary.isError) {
    return <ErrorBox error={summary.error} onRetry={() => void summary.refetch()} />;
  }

  if (!summary.data) {
    return <ErrorBox error={summary.error} onRetry={() => void summary.refetch()} />;
  }

  const counts = summary.data.servers;
  const averages = summary.data.averages;
  const incidents = summary.data.incidents;
  const total = servers.data?.total ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-100">Dashboard</h1>
          <p className="mt-1 text-sm text-slate-500">
            Última comunicação {formatRelative(summary.data.last_heartbeat_at)} ·{" "}
            {formatDateTime(summary.data.last_heartbeat_at)}
          </p>
        </div>
        {isAdmin ? (
          <Button onClick={() => setCreating(true)}>+ Novo servidor</Button>
        ) : null}
      </div>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3" aria-label="Indicadores">
        <KpiCard
          label="Servidores"
          value={String(counts.total)}
          hint={`${counts.online} online · ${counts.attention} atenção · ${counts.offline} offline`}
        />
        <KpiCard
          label="CPU média"
          value={formatPercent(averages.cpu_percent)}
          hint={`${averages.servers_considered} servidor(es) com coleta recente`}
        />
        <KpiCard label="RAM média" value={formatPercent(averages.ram_percent)} />
        <KpiCard label="Disco (pior montagem)" value={formatPercent(averages.disk_percent)} />
        <KpiCard
          label="Incidentes abertos"
          value={String(incidents.open)}
          hint={incidents.available ? undefined : "Motor de alertas chega na fase 9"}
        />
        <KpiCard
          label="Última comunicação"
          value={formatRelative(summary.data.last_heartbeat_at)}
          hint={formatDateTime(summary.data.last_heartbeat_at)}
        />
      </section>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Buscar por nome ou hostname"
            className={`${inputClasses} max-w-xs`}
            aria-label="Buscar servidores"
          />
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value as ServerStatus | "")}
            className={`${inputClasses} max-w-[200px]`}
            aria-label="Filtrar por estado"
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {total > 0 ? (
            <span className="text-xs text-slate-500">{total} servidor(es)</span>
          ) : null}
        </div>

        {servers.isError ? (
          <ErrorBox error={servers.error} onRetry={() => void servers.refetch()} />
        ) : total === 0 ? (
          <EmptyState
            title="Nenhum servidor cadastrado"
            description="Cadastre a primeira VPS para começar a receber telemetria."
            action={
              isAdmin ? <Button onClick={() => setCreating(true)}>Cadastrar servidor</Button> : undefined
            }
          />
        ) : (
          <ServerTable servers={servers.data?.items ?? []} latest={latestByServer} />
        )}
      </section>

      <NewServerModal open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}

function ServerTable({
  servers,
  latest,
}: {
  servers: Server[];
  latest: Map<string, LatestTelemetry>;
}) {
  return (
    <div className="card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[900px] text-sm">
          <thead>
            <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="px-4 py-3 font-medium">Servidor</th>
              <th className="px-4 py-3 font-medium">Estado</th>
              <th className="px-4 py-3 font-medium">CPU</th>
              <th className="px-4 py-3 font-medium">RAM</th>
              <th className="px-4 py-3 font-medium">Disco</th>
              <th className="px-4 py-3 font-medium">Última comunicação</th>
              <th className="px-4 py-3 font-medium">Agente</th>
              <th className="px-4 py-3 text-right font-medium">Ações</th>
            </tr>
          </thead>
          <tbody>
            {servers.map((server) => {
              const metrics = latest.get(server.id);
              return (
                <tr
                  key={server.id}
                  className="border-b border-slate-800/60 last:border-0 hover:bg-slate-800/30"
                >
                  <td className="px-4 py-3">
                    <Link
                      to={`/servers/${server.id}`}
                      title={`Abrir detalhes de ${server.name}`}
                      className="focus-ring rounded font-medium text-slate-100 underline decoration-slate-700 underline-offset-4 hover:text-emerald-300 hover:decoration-emerald-400"
                    >
                      {server.name}
                    </Link>
                    <p className="text-xs text-slate-500">
                      {server.ip_address ?? server.hostname ?? "sem endereço"}
                    </p>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={server.status} />
                  </td>
                  <td className="px-4 py-3">
                    <MetricCell value={metrics?.cpu_percent} />
                  </td>
                  <td className="px-4 py-3">
                    <MetricCell value={metrics?.ram_percent} />
                  </td>
                  <td className="px-4 py-3">
                    <MetricCell value={metrics?.disk_percent} />
                  </td>
                  <td className="px-4 py-3 text-slate-400">
                    {formatRelative(server.last_heartbeat_at)}
                  </td>
                  <td className="px-4 py-3 text-slate-500">
                    {server.agent_version ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      to={`/servers/${server.id}`}
                      className="focus-ring inline-flex items-center gap-1 rounded-lg border border-slate-700 px-2.5 py-1 text-xs text-slate-300 transition hover:border-emerald-500/50 hover:text-emerald-300"
                    >
                      Abrir →
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function MetricCell({ value }: { value?: number | null }) {
  if (value === null || value === undefined) {
    return <span className="text-slate-600">—</span>;
  }
  return (
    <div className="w-24">
      <span className="text-xs tabular-nums text-slate-300">{formatPercent(value)}</span>
      <div className="mt-1">
        <UsageBar value={value} />
      </div>
    </div>
  );
}
