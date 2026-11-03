import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { NetworkChart, UsageChart } from "../components/charts";
import {
  Button,
  EmptyState,
  ErrorBox,
  KpiCard,
  Modal,
  SecretBox,
  Spinner,
  StatusBadge,
  UsageBar,
} from "../components/ui";
import { api } from "../lib/api";
import { useMe } from "../lib/auth";
import {
  ENVIRONMENT_LABELS,
  PANEL_LABELS,
  formatDateTime,
  formatPercent,
  formatRelative,
  formatUptime,
} from "../lib/format";
import type { MetricsWindow } from "../lib/types";

const WINDOWS: MetricsWindow[] = ["1h", "6h", "24h", "7d"];

interface RevealedSecret {
  title: string;
  value: string;
  hint?: string;
  command?: string;
}

/** Base da API a partir do register_url (absoluto quando PUBLIC_BASE_URL está definido). */
function resolveApiBase(registerUrl: string): string {
  try {
    return new URL(registerUrl, window.location.origin).origin;
  } catch {
    return window.location.origin;
  }
}

export function ServerDetailPage() {
  const { serverId = "" } = useParams<{ serverId: string }>();
  const queryClient = useQueryClient();
  const me = useMe();
  const isAdmin = me.data?.user.role === "admin";

  const [window, setWindow] = useState<MetricsWindow>("1h");
  const [secret, setSecret] = useState<RevealedSecret | null>(null);
  const [confirm, setConfirm] = useState<"revoke" | "disable" | null>(null);

  const server = useQuery({
    queryKey: ["server", serverId],
    queryFn: () => api.getServer(serverId),
    enabled: Boolean(serverId),
    refetchInterval: 20_000,
  });

  const series = useQuery({
    queryKey: ["metrics", serverId, window],
    queryFn: () => api.metrics(serverId, window),
    enabled: Boolean(serverId),
    refetchInterval: 30_000,
  });

  const beats = useQuery({
    queryKey: ["heartbeats", serverId],
    queryFn: () => api.heartbeats(serverId, 20),
    enabled: Boolean(serverId),
    refetchInterval: 30_000,
  });

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["server", serverId] });
    void queryClient.invalidateQueries({ queryKey: ["servers"] });
    void queryClient.invalidateQueries({ queryKey: ["summary"] });
  };

  const pause = useMutation({ mutationFn: () => api.pauseServer(serverId), onSuccess: refresh });
  const resume = useMutation({ mutationFn: () => api.resumeServer(serverId), onSuccess: refresh });
  const disable = useMutation({ mutationFn: () => api.disableServer(serverId), onSuccess: refresh });
  const issueToken = useMutation({
    mutationFn: () => api.provisioningToken(serverId),
    onSuccess: (data) => {
      const apiBase = resolveApiBase(data.register_url);
      setSecret({
        title: "Token de provisionamento",
        value: data.token,
        hint: `Uso único · expira em ${formatDateTime(data.expires_at)}`,
        command: [
          "sudo bash agent/scripts/install.sh \\",
          `  --server-id ${data.server_id} \\`,
          `  --token ${data.token} \\`,
          `  --api-url ${apiBase}`,
        ].join("\n"),
      });
    },
  });
  const rotate = useMutation({
    mutationFn: () => api.rotateCredential(serverId),
    onSuccess: (data) => {
      setSecret({
        title: "Nova credencial do agente",
        value: data.credential,
        hint: `${data.revoked_previous} credencial(is) anterior(es) revogada(s). Reinstale o agente com este valor.`,
      });
    },
  });
  const revoke = useMutation({
    mutationFn: () => api.revokeCredentials(serverId),
    onSuccess: () => {
      setConfirm(null);
      refresh();
    },
  });

  if (server.isLoading) {
    return (
      <div className="py-16">
        <Spinner label="Carregando servidor..." />
      </div>
    );
  }

  if (server.isError || !server.data) {
    return (
      <div className="space-y-4">
        <BackLink />
        <ErrorBox error={server.error} onRetry={() => void server.refetch()} />
      </div>
    );
  }

  const data = server.data;
  const points = series.data?.points ?? [];
  const current = points.length > 0 ? points[points.length - 1] : undefined;
  const lastBeat = beats.data?.[0];

  return (
    <div className="space-y-6">
      <BackLink />

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-xl font-semibold text-slate-100">{data.name}</h1>
            <StatusBadge status={data.status} />
          </div>
          <p className="mt-1 text-sm text-slate-500">
            {data.ip_address ?? "sem IP"} · {data.hostname ?? "sem hostname"} ·{" "}
            {PANEL_LABELS[data.panel] ?? data.panel} ·{" "}
            {ENVIRONMENT_LABELS[data.environment] ?? data.environment}
          </p>
          {data.tags.length > 0 ? (
            <div className="mt-2 flex flex-wrap gap-1">
              {data.tags.map((tag) => (
                <span
                  key={tag}
                  className="rounded-full border border-slate-700 px-2 py-0.5 text-xs text-slate-400"
                >
                  {tag}
                </span>
              ))}
            </div>
          ) : null}
        </div>

        {isAdmin ? (
          <div className="flex flex-wrap gap-2">
            {data.status === "paused" || data.status === "disabled" ? (
              <Button variant="secondary" onClick={() => resume.mutate()} disabled={resume.isPending}>
                Retomar
              </Button>
            ) : (
              <Button variant="secondary" onClick={() => pause.mutate()} disabled={pause.isPending}>
                Pausar
              </Button>
            )}
            <Button variant="danger" onClick={() => setConfirm("disable")}>
              Desativar
            </Button>
          </div>
        ) : null}
      </div>

      {data.status === "unprovisioned" ? (
        <div className="rounded-xl border border-sky-500/30 bg-sky-500/5 p-4 text-sm text-sky-200">
          <p className="font-medium">Aguardando o primeiro contato do agente</p>
          <p className="mt-1 text-sky-200/70">
            Gere um token de provisionamento, instale o agente na VPS e o monitoramento começa
            automaticamente.
          </p>
          {isAdmin ? (
            <Button className="mt-3" onClick={() => issueToken.mutate()} disabled={issueToken.isPending}>
              {issueToken.isPending ? "Gerando..." : "Gerar token de provisionamento"}
            </Button>
          ) : null}
        </div>
      ) : null}

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3" aria-label="Métricas atuais">
        <KpiCard label="CPU" value={formatPercent(current?.cpu_percent)}>
          <div className="mt-2">
            <UsageBar value={current?.cpu_percent} />
          </div>
        </KpiCard>
        <KpiCard label="RAM" value={formatPercent(current?.ram_percent)}>
          <div className="mt-2">
            <UsageBar value={current?.ram_percent} />
          </div>
        </KpiCard>
        <KpiCard label="Swap" value={formatPercent(current?.swap_percent)}>
          <div className="mt-2">
            <UsageBar value={current?.swap_percent} />
          </div>
        </KpiCard>
        <KpiCard label="Disco (pior montagem)" value={formatPercent(current?.disk_percent)}>
          <div className="mt-2">
            <UsageBar value={current?.disk_percent} />
          </div>
        </KpiCard>
        <KpiCard label="Uptime" value={formatUptime(lastBeat?.uptime_seconds)} />
        <KpiCard
          label="Última coleta"
          value={formatRelative(data.last_metrics_at)}
          hint={formatDateTime(data.last_metrics_at)}
        />
      </section>

      <section className="card p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-slate-200">CPU · RAM · Swap</h2>
          <div className="flex gap-1" role="group" aria-label="Janela de tempo">
            {WINDOWS.map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setWindow(option)}
                className={`focus-ring rounded-md px-2.5 py-1 text-xs transition ${
                  window === option
                    ? "bg-emerald-500/15 text-emerald-300"
                    : "text-slate-400 hover:bg-slate-800"
                }`}
              >
                {option}
              </button>
            ))}
          </div>
        </div>

        {series.isLoading ? (
          <Spinner label="Carregando série..." />
        ) : series.isError ? (
          <ErrorBox error={series.error} onRetry={() => void series.refetch()} />
        ) : points.length === 0 ? (
          <EmptyState
            title="Sem métricas nesta janela"
            description="Nenhuma coleta recebida no período selecionado."
          />
        ) : (
          <UsageChart points={points} />
        )}
      </section>

      <section className="card p-4">
        <h2 className="mb-3 text-sm font-semibold text-slate-200">Rede</h2>
        {points.length === 0 ? (
          <EmptyState title="Sem dados de rede nesta janela" />
        ) : (
          <NetworkChart points={points} />
        )}
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-200">Heartbeats recentes</h2>
          {beats.isLoading ? (
            <Spinner />
          ) : (beats.data ?? []).length === 0 ? (
            <EmptyState title="Nenhum heartbeat recebido" />
          ) : (
            <ul className="divide-y divide-slate-800/60 text-sm">
              {(beats.data ?? []).slice(0, 8).map((beat) => (
                <li key={beat.received_at} className="flex items-center justify-between py-2">
                  <span className="text-slate-300">{formatDateTime(beat.received_at)}</span>
                  <span className="text-xs text-slate-500">
                    uptime {formatUptime(beat.uptime_seconds)} · v{beat.agent_version}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-200">Informações do servidor</h2>
          <dl className="space-y-2 text-sm">
            <Row label="Sistema" value={`${data.os_name ?? "—"} ${data.os_version ?? ""}`.trim()} />
            <Row label="Kernel" value={data.kernel ?? "—"} />
            <Row label="Arquitetura" value={data.architecture ?? "—"} />
            <Row label="Agente" value={data.agent_version ?? "—"} />
            <Row label="Intervalo de coleta" value={`${data.collection_interval_seconds}s`} />
            <Row
              label="Tolerância de heartbeat"
              value={`${data.heartbeat_timeout_seconds}s`}
            />
            <Row label="Credenciais ativas" value={String(data.active_credentials)} />
            <Row label="Cadastrado em" value={formatDateTime(data.created_at)} />
          </dl>

          {isAdmin ? (
            <div className="mt-4 flex flex-wrap gap-2 border-t border-slate-800 pt-4">
              <Button
                variant="secondary"
                onClick={() => issueToken.mutate()}
                disabled={issueToken.isPending}
              >
                Token de provisionamento
              </Button>
              <Button variant="secondary" onClick={() => rotate.mutate()} disabled={rotate.isPending}>
                Rotacionar credencial
              </Button>
              <Button variant="danger" onClick={() => setConfirm("revoke")}>
                Revogar credenciais
              </Button>
            </div>
          ) : null}
        </section>
      </div>

      <Modal open={secret !== null} title={secret?.title ?? ""} onClose={() => setSecret(null)}>
        <div className="space-y-3">
          <SecretBox label="Valor" value={secret?.value ?? ""} />
          {secret?.hint ? <p className="text-xs text-slate-400">{secret.hint}</p> : null}
          {secret?.command ? (
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                Comando de instalação
              </p>
              <pre className="mt-1 overflow-x-auto rounded-lg bg-slate-950/60 p-3 text-xs leading-relaxed text-slate-200">
                {secret.command}
              </pre>
              <Button
                variant="secondary"
                className="mt-2"
                onClick={() => void navigator.clipboard?.writeText(secret.command ?? "")}
              >
                Copiar comando
              </Button>
            </div>
          ) : null}
        </div>
      </Modal>

      <Modal
        open={confirm !== null}
        title={confirm === "revoke" ? "Revogar credenciais" : "Desativar servidor"}
        onClose={() => setConfirm(null)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirm(null)}>
              Cancelar
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                if (confirm === "revoke") {
                  revoke.mutate();
                } else if (confirm === "disable") {
                  disable.mutate();
                  setConfirm(null);
                }
              }}
            >
              Confirmar
            </Button>
          </>
        }
      >
        <p className="text-sm text-slate-300">
          {confirm === "revoke"
            ? "Todas as credenciais ativas serão revogadas. O agente para de enviar dados até ser reinstalado."
            : "O servidor deixa de aceitar telemetria e não é removido do histórico."}
        </p>
      </Modal>
    </div>
  );
}

function BackLink() {
  return (
    <Link
      to="/"
      className="focus-ring inline-flex items-center gap-1 rounded text-xs text-slate-500 hover:text-slate-300"
    >
      ← Voltar ao dashboard
    </Link>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right text-slate-300">{value}</dd>
    </div>
  );
}
