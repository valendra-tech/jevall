"use client";

import { outcomeLabel, type GameState } from "@/lib/game";
import { formatMs, formatPercent, latencyStats, averageSelectedProbability, survivedMoves } from "@/lib/stats";
import type { HistoryEntry } from "@/lib/types";

const ARROWS: Record<string, string> = {
  up: "↑",
  down: "↓",
  left: "←",
  right: "→",
};

const OUTCOME_STYLES: Record<string, string> = {
  moved: "text-zinc-500",
  ate: "text-emerald-300",
  wall: "text-rose-400",
  self: "text-rose-400",
  "board-full": "text-sky-300",
};

export function MetricsBar({ history }: { history: HistoryEntry[] }) {
  const latency = latencyStats(history);
  const averageProbability = averageSelectedProbability(history);
  const last = history.at(-1) ?? null;

  const metrics: Array<{ label: string; value: string }> = [
    { label: "Score", value: String(history.filter((entry) => entry.outcome === "ate").length) },
    { label: "Food eaten", value: String(history.filter((entry) => entry.outcome === "ate").length) },
    { label: "Moves survived", value: String(survivedMoves(history)) },
    { label: "Snake length", value: String(3 + history.filter((entry) => entry.outcome === "ate").length) },
    { label: "Average latency", value: formatMs(latency.average) },
    { label: "Min latency", value: formatMs(latency.min) },
    { label: "Max latency", value: formatMs(latency.max) },
    { label: "Current latency", value: formatMs(last?.latencyMs ?? null) },
    {
      label: "Average selected probability",
      value: formatPercent(averageProbability),
    },
  ];

  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {metrics.map((metric) => (
        <div
          key={metric.label}
          className="rounded-lg border border-zinc-800 bg-zinc-900/40 px-3 py-2"
        >
          <dt className="text-[10px] uppercase tracking-wide text-zinc-500">
            {metric.label}
          </dt>
          <dd className="mt-0.5 font-mono text-sm text-zinc-100">
            {metric.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function HistoryTable({ history }: { history: HistoryEntry[] }) {
  const rows = [...history].reverse().slice(0, 20);
  if (rows.length === 0) {
    return null;
  }
  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900/40">
      <header className="flex items-center justify-between border-b border-zinc-800 px-4 py-3">
        <h2 className="text-xs font-medium uppercase tracking-wide text-zinc-500">
          Decision history
        </h2>
        <span className="text-xs text-zinc-600">
          last {rows.length} of {history.length}
        </span>
      </header>
      <div className="overflow-x-auto">
        <table className="w-full font-mono text-xs">
          <thead>
            <tr className="text-left text-zinc-600">
              <th className="px-4 py-2 font-normal">#</th>
              <th className="px-4 py-2 font-normal">Move</th>
              <th className="px-4 py-2 font-normal">P(selected)</th>
              <th className="px-4 py-2 font-normal">Latency</th>
              <th className="px-4 py-2 font-normal">Outcome</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((entry) => (
              <tr key={entry.turn} className="border-t border-zinc-800/70">
                <td className="px-4 py-1.5 text-zinc-600">{entry.turn}</td>
                <td className="px-4 py-1.5 text-zinc-300">
                  {ARROWS[entry.selected]} {entry.selected.toUpperCase()}
                </td>
                <td className="px-4 py-1.5 text-zinc-400">
                  {formatPercent(entry.selectedProbability)}
                </td>
                <td className="px-4 py-1.5 text-zinc-400">
                  {formatMs(entry.latencyMs)}
                </td>
                <td
                  className={`px-4 py-1.5 ${OUTCOME_STYLES[entry.outcome] ?? "text-zinc-500"}`}
                >
                  {outcomeLabel(entry.outcome)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function GameOverPanel({
  game,
  history,
  mode,
  onRestart,
}: {
  game: GameState;
  history: HistoryEntry[];
  mode: "ai" | "human";
  onRestart: () => void;
}) {
  const last = history.at(-1) ?? null;
  const survived = survivedMoves(history);

  return (
    <section className="rounded-xl border border-rose-900/60 bg-rose-950/20 p-4">
      <h2 className="font-mono text-sm uppercase tracking-wide text-rose-300">
        Game over
      </h2>
      <dl className="mt-3 grid grid-cols-3 gap-3 font-mono text-xs">
        <div>
          <dt className="text-zinc-500">Score</dt>
          <dd className="text-zinc-100">{game.score}</dd>
        </div>
        <div>
          <dt className="text-zinc-500">Moves survived</dt>
          <dd className="text-zinc-100">{survived}</dd>
        </div>
        <div>
          <dt className="text-zinc-500">Snake length</dt>
          <dd className="text-zinc-100">{game.snake.length}</dd>
        </div>
      </dl>
      {last ? (
        <p className="mt-3 font-mono text-xs text-zinc-300">
          Final decision: {ARROWS[last.selected]} {last.selected.toUpperCase()}{" "}
          {formatPercent(last.selectedProbability)}
        </p>
      ) : null}
      <p className="mt-1 font-mono text-xs text-rose-300">
        Cause: {game.outcome ? outcomeLabel(game.outcome) : "unknown"}
      </p>
      <button
        type="button"
        onClick={onRestart}
        className="mt-4 rounded-md bg-zinc-100 px-3 py-1.5 text-xs font-medium text-zinc-900 hover:bg-white"
      >
        {mode === "ai" ? "Restart AI" : "Restart"}
      </button>
    </section>
  );
}
