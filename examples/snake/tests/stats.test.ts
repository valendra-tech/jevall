import {
  averageSelectedProbability,
  latencyStats,
  survivedMoves,
} from "@/lib/stats";
import type { HistoryEntry } from "@/lib/types";

function entry(overrides: Partial<HistoryEntry> = {}): HistoryEntry {
  return {
    turn: 1,
    usedImage: false,
    stateText: "state",
    options: [{ id: "up", text: "Move up" }],
    rawResponse: null,
    selected: "up",
    probabilities: { up: 0.6, down: 0.4 },
    selectedProbability: 0.6,
    latencyMs: 100,
    diagnostics: { queueMs: 8, forwardMs: 50, scoringMs: 20 },
    outcome: "moved",
    boardBefore: "",
    boardAfter: "",
    ...overrides,
  };
}

describe("latencyStats", () => {
  it("computes average, min and max", () => {
    const stats = latencyStats([
      entry({ latencyMs: 100 }),
      entry({ latencyMs: 300 }),
      entry({ latencyMs: 200 }),
    ]);

    expect(stats).toEqual({ average: 200, min: 100, max: 300, count: 3 });
  });

  it("returns nulls without history", () => {
    expect(latencyStats([])).toEqual({
      average: null,
      min: null,
      max: null,
      count: 0,
    });
  });
});

describe("averageSelectedProbability", () => {
  it("averages the probability of the selected option", () => {
    const average = averageSelectedProbability([
      entry({ selectedProbability: 0.5 }),
      entry({ selectedProbability: 1 }),
    ]);

    expect(average).toBe(0.75);
  });

  it("ignores entries without probabilities", () => {
    expect(
      averageSelectedProbability([entry({ selectedProbability: null })]),
    ).toBeNull();
  });
});

describe("survivedMoves", () => {
  it("counts only non fatal moves", () => {
    const survived = survivedMoves([
      entry({ outcome: "moved" }),
      entry({ outcome: "ate" }),
      entry({ outcome: "wall" }),
    ]);

    expect(survived).toBe(2);
  });
});
