// @vitest-environment jsdom
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useSnakeGame } from "@/hooks/useSnakeGame";

function decisionResponse(selected: string) {
  return {
    id: "dec_test",
    model: "Qwen/Qwen3.5-4B",
    decisions: [
      {
        id: "move",
        type: "choice",
        selected,
        probabilities: { turn_left: 0.15, straight: 0.7, turn_right: 0.15 },
      },
    ],
    usage: { latency_ms: 42 },
    diagnostics: { queue_ms: 5, forward_ms: 30, scoring_ms: 7 },
  };
}

describe("useSnakeGame", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(JSON.stringify(decisionResponse("straight")), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("applies exactly one decision per turn and never repeats a turn", async () => {
    let calls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        calls += 1;
        if (calls > 12) {
          // A runaway loop must fail the test instead of exhausting memory.
          throw new Error("too many decisions for one game");
        }
        return new Response(JSON.stringify(decisionResponse("straight")), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }),
    );
    const { result } = renderHook(() => useSnakeGame());

    act(() => {
      result.current.setSpeed("fast");
      result.current.start();
    });

    // Always moving right on a 12x12 board reaches the wall after 6 moves.
    await waitFor(() => expect(result.current.phase).toBe("over"), {
      timeout: 5000,
    });

    const turns = result.current.history.map((entry) => entry.turn);

    expect(turns).toEqual([1, 2, 3, 4, 5, 6]);
    expect(new Set(turns).size).toBe(turns.length);
    expect(calls).toBe(6);
    expect(result.current.history.at(-1)?.outcome).toBe("wall");
    expect(result.current.game.outcome).toBe("wall");
  });

  it("pauses without inventing a move when the API fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("network down");
      }),
    );
    const { result } = renderHook(() => useSnakeGame());

    act(() => {
      result.current.setSpeed("fast");
      result.current.start();
    });

    await waitFor(() => expect(result.current.phase).toBe("paused"), {
      timeout: 5000,
    });

    expect(result.current.error).toBeTruthy();
    expect(result.current.history).toHaveLength(0);
    expect(result.current.game.moves).toBe(0);
  });
});
