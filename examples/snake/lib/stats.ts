import type { HistoryEntry } from "./types";

export type LatencyStats = {
  average: number | null;
  min: number | null;
  max: number | null;
  count: number;
};

export function latencyStats(history: HistoryEntry[]): LatencyStats {
  const values = history
    .map((entry) => entry.latencyMs)
    .filter((value) => Number.isFinite(value));
  if (values.length === 0) {
    return { average: null, min: null, max: null, count: 0 };
  }
  const total = values.reduce((sum, value) => sum + value, 0);
  return {
    average: total / values.length,
    min: Math.min(...values),
    max: Math.max(...values),
    count: values.length,
  };
}

/** Mean of the probability assigned to the movement the model selected. */
export function averageSelectedProbability(
  history: HistoryEntry[],
): number | null {
  const values = history
    .map((entry) => entry.selectedProbability)
    .filter((value): value is number => value !== null);
  if (values.length === 0) {
    return null;
  }
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

export function survivedMoves(history: HistoryEntry[]): number {
  return history.filter(
    (entry) => entry.outcome === "moved" || entry.outcome === "ate",
  ).length;
}

export function formatPercent(value: number | null, digits = 1): string {
  if (value === null || !Number.isFinite(value)) {
    return "n/a";
  }
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatMs(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return "n/a";
  }
  return `${Math.round(value)} ms`;
}
