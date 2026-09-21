"use client";

import type { HistoryEntry, TurnDiagnostics } from "@/lib/types";
import { formatMs, formatPercent } from "@/lib/stats";

const ARROWS: Record<string, string> = {
  up: "↑",
  down: "↓",
  left: "←",
  right: "→",
};

type DecisionPanelProps = {
  mode: "ai" | "human";
  thinking: boolean;
  error: string | null;
  last: HistoryEntry | null;
  onRetry: () => void;
  onRestart: () => void;
};

export function DecisionPanel({
  mode,
  thinking,
  error,
  last,
  onRetry,
  onRestart,
}: DecisionPanelProps) {
  if (mode === "human") {
    return (
      <Panel title="Human control">
        <p className="text-sm text-zinc-400">
          Arrow keys or WASD. Decision statistics are only collected in AI
          mode.
        </p>
      </Panel>
    );
  }

  if (error) {
    return (
      <Panel title="AI decision">
        <p className="text-sm font-medium text-rose-400">
          Decision API unavailable
        </p>
        <p className="mt-1 break-words font-mono text-xs text-zinc-500">
          {error}
        </p>
        <div className="mt-4 flex gap-2">
          <button
            type="button"
            onClick={onRetry}
            className="rounded-md bg-zinc-100 px-3 py-1.5 text-xs font-medium text-zinc-900 hover:bg-white"
          >
            Retry
          </button>
          <button
            type="button"
            onClick={onRestart}
            className="rounded-md border border-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-300 hover:border-zinc-500"
          >
            Restart
          </button>
        </div>
      </Panel>
    );
  }

  if (!last) {
    return (
      <Panel title="AI decision">
        <p className="text-sm text-zinc-400">
          {thinking ? "Evaluating state…" : "No decision yet."}
        </p>
      </Panel>
    );
  }

  const ranked = last.options
    .map((option) => ({
      ...option,
      probability: last.probabilities[option.id] ?? 0,
    }))
    .sort((left, right) => right.probability - left.probability);

  return (
    <Panel
      title="AI decision"
      aside={thinking ? <Thinking /> : <span className="text-xs text-zinc-500">turn {last.turn}</span>}
    >
      <ul className="space-y-2">
        {ranked.map((option) => {
          const selected = option.id === last.selected;
          return (
            <li key={option.id} className="space-y-1">
              <div className="flex items-baseline justify-between font-mono text-xs">
                <span className={selected ? "text-emerald-300" : "text-zinc-400"}>
                  {ARROWS[option.id]} {option.id.toUpperCase()}
                </span>
                <span className={selected ? "text-emerald-300" : "text-zinc-500"}>
                  {formatPercent(option.probability)}
                </span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-800">
                <div
                  className={selected ? "h-full bg-emerald-400" : "h-full bg-zinc-600"}
                  style={{ width: `${Math.min(100, option.probability * 100)}%` }}
                />
              </div>
            </li>
          );
        })}
      </ul>

      <div className="mt-4 flex items-center justify-between border-t border-zinc-800 pt-3">
        <span className="text-xs uppercase tracking-wide text-zinc-500">
          Selected
        </span>
        <span className="font-mono text-sm text-emerald-300">
          {ARROWS[last.selected]} {last.selected.toUpperCase()}
        </span>
      </div>
    </Panel>
  );
}

export function LatencyPanel({
  diagnostics,
  total,
}: {
  diagnostics: TurnDiagnostics | null;
  total: number | null;
}) {
  const rows: Array<[string, number | null]> = [
    ["Total", total],
    ["Queue", diagnostics?.queueMs ?? null],
    ["Forward", diagnostics?.forwardMs ?? null],
    ["Scoring", diagnostics?.scoringMs ?? null],
  ];
  const visible = rows.filter(([, value]) => value !== null);
  if (visible.length === 0) {
    return null;
  }
  return (
    <Panel title="Latency">
      <dl className="space-y-1 font-mono text-xs">
        {visible.map(([label, value]) => (
          <div key={label} className="flex justify-between">
            <dt className="text-zinc-500">{label}</dt>
            <dd className="text-zinc-300">{formatMs(value)}</dd>
          </div>
        ))}
      </dl>
    </Panel>
  );
}

function Panel({
  title,
  aside,
  children,
}: {
  title: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
      <header className="mb-3 flex items-center justify-between">
        <h2 className="text-xs font-medium uppercase tracking-wide text-zinc-500">
          {title}
        </h2>
        {aside}
      </header>
      {children}
    </section>
  );
}

function Thinking() {
  return (
    <span className="flex items-center gap-2 text-xs text-sky-300">
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-sky-400" />
      Evaluating…
    </span>
  );
}
