import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatBps, formatShortTime } from "../lib/format";
import type { MetricPoint } from "../lib/types";

const CHART = {
  grid: "#1e293b",
  axis: "#64748b",
  tooltipBg: "#0f172a",
  tooltipBorder: "#1e293b",
  cpu: "#34d399",
  ram: "#60a5fa",
  swap: "#f59e0b",
  disk: "#f472b6",
  rx: "#22d3ee",
  tx: "#a78bfa",
};

const tooltipStyle = {
  background: CHART.tooltipBg,
  border: `1px solid ${CHART.tooltipBorder}`,
  borderRadius: 8,
  fontSize: 12,
  color: "#e2e8f0",
};

interface UsagePoint {
  at: string;
  cpu: number | null;
  ram: number | null;
  swap: number | null;
  disk: number | null;
}

function toUsage(points: MetricPoint[]): UsagePoint[] {
  return points.map((point) => ({
    at: formatShortTime(point.at),
    cpu: point.cpu_percent,
    ram: point.ram_percent,
    swap: point.swap_percent,
    disk: point.disk_percent,
  }));
}

export function UsageChart({ points }: { points: MetricPoint[] }) {
  const data = toUsage(points);
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
          <defs>
            <linearGradient id="cpuFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={CHART.cpu} stopOpacity={0.35} />
              <stop offset="100%" stopColor={CHART.cpu} stopOpacity={0.02} />
            </linearGradient>
            <linearGradient id="ramFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={CHART.ram} stopOpacity={0.3} />
              <stop offset="100%" stopColor={CHART.ram} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={CHART.grid} strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="at" stroke={CHART.axis} fontSize={11} tickLine={false} minTickGap={28} />
          <YAxis
            stroke={CHART.axis}
            fontSize={11}
            tickLine={false}
            domain={[0, 100]}
            tickFormatter={(value: number) => `${value}%`}
          />
          <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: "#94a3b8" }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Area
            type="monotone"
            dataKey="cpu"
            name="CPU"
            stroke={CHART.cpu}
            fill="url(#cpuFill)"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
            connectNulls
          />
          <Area
            type="monotone"
            dataKey="ram"
            name="RAM"
            stroke={CHART.ram}
            fill="url(#ramFill)"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="swap"
            name="Swap"
            stroke={CHART.swap}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="disk"
            name="Disco"
            stroke={CHART.disk}
            strokeWidth={1.5}
            strokeDasharray="4 3"
            dot={false}
            isAnimationActive={false}
            connectNulls
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

interface NetworkPoint {
  at: string;
  rx: number | null;
  tx: number | null;
}

export function NetworkChart({ points }: { points: MetricPoint[] }) {
  const data: NetworkPoint[] = points.map((point) => ({
    at: formatShortTime(point.at),
    rx: point.net_rx_bps,
    tx: point.net_tx_bps,
  }));

  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 4 }}>
          <CartesianGrid stroke={CHART.grid} strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="at" stroke={CHART.axis} fontSize={11} tickLine={false} minTickGap={28} />
          <YAxis
            stroke={CHART.axis}
            fontSize={11}
            tickLine={false}
            width={64}
            tickFormatter={(value: number) => formatBps(value)}
          />
          <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: "#94a3b8" }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line
            type="monotone"
            dataKey="rx"
            name="Recebido"
            stroke={CHART.rx}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="tx"
            name="Enviado"
            stroke={CHART.tx}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
