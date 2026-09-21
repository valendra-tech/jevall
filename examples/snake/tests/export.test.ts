import { buildRunExport } from "@/lib/export";
import { createGame } from "@/lib/game";
import type { HistoryEntry } from "@/lib/types";

function entry(overrides: Partial<HistoryEntry> = {}): HistoryEntry {
  return {
    turn: 1,
    usedImage: false,
    stateText: "SNAKE GAME",
    options: [{ id: "right", text: "Move right" }],
    rawResponse: { id: "dec_1" } as never,
    selected: "right",
    probabilities: { right: 0.9, up: 0.1 },
    selectedProbability: 0.9,
    latencyMs: 80,
    diagnostics: { queueMs: 8, forwardMs: 50, scoringMs: 22 },
    outcome: "ate",
    boardBefore: "before",
    boardAfter: "after",
    ...overrides,
  };
}

describe("buildRunExport", () => {
  it("summarises the run and keeps every turn", () => {
    const game = { ...createGame(12, () => 0), score: 1, moves: 2, outcome: "wall" as const };
    const run = buildRunExport(game, [entry(), entry({ turn: 2, outcome: "wall" })]);

    expect(run.model).toBe("Qwen/Qwen3.5-4B");
    expect(run.boardSize).toBe(12);
    expect(run.score).toBe(1);
    expect(run.moves).toBe(2);
    expect(run.survived).toBe(1);
    expect(run.cause).toBe("wall");
    expect(run.averageLatencyMs).toBe(80);
    expect(run.averageSelectedProbability).toBeCloseTo(0.9);
    expect(run.history).toHaveLength(2);
    expect(run.history[0].stateText).toBe("SNAKE GAME");
    expect(run.history[0].boardBefore).toBe("before");
    expect(run.history[0].boardAfter).toBe("after");
    expect(run.history[1].outcome).toBe("wall");
  });
});
