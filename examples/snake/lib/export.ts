import type { GameState } from "./game";
import { averageSelectedProbability, latencyStats, survivedMoves } from "./stats";
import type { HistoryEntry, RunExport } from "./types";

export const MODEL_ID = "Qwen/Qwen3.5-4B";

export function buildRunExport(
  state: GameState,
  history: HistoryEntry[],
): RunExport {
  return {
    model: MODEL_ID,
    boardSize: state.size,
    score: state.score,
    moves: state.moves,
    survived: survivedMoves(history),
    snakeLength: state.snake.length,
    cause: state.outcome,
    averageLatencyMs: latencyStats(history).average,
    averageSelectedProbability: averageSelectedProbability(history),
    history,
  };
}

export function downloadRun(state: GameState, history: HistoryEntry[]): void {
  const payload = JSON.stringify(buildRunExport(state, history), null, 2);
  const blob = new Blob([payload], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `jevall-snake-run-${new Date().toISOString().replace(/[:.]/g, "-")}.json`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
