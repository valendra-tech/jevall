import {
  RELATIVE_ACTIONS,
  absoluteOf,
  relativeDirections,
  relativeLabel,
  relativeSymbol,
  step,
} from "@/lib/game";
import type { Direction } from "@/lib/types";

describe("relativeDirections", () => {
  it("maps the three actions for every heading", () => {
    expect(relativeDirections("right")).toEqual({
      turn_left: "up",
      straight: "right",
      turn_right: "down",
    });
    expect(relativeDirections("up")).toEqual({
      turn_left: "left",
      straight: "up",
      turn_right: "right",
    });
    expect(relativeDirections("down")).toEqual({
      turn_left: "right",
      straight: "down",
      turn_right: "left",
    });
    expect(relativeDirections("left")).toEqual({
      turn_left: "down",
      straight: "left",
      turn_right: "up",
    });
  });

  it("never offers the reverse direction", () => {
    const opposite: Record<Direction, Direction> = {
      up: "down",
      down: "up",
      left: "right",
      right: "left",
    };
    for (const heading of Object.keys(opposite) as Direction[]) {
      const mapped = Object.values(relativeDirections(heading));
      expect(mapped).not.toContain(opposite[heading]);
      expect(new Set(mapped).size).toBe(3);
    }
  });

  it("has an action for every relative move", () => {
    expect(RELATIVE_ACTIONS).toEqual(["turn_left", "straight", "turn_right"]);
    expect(absoluteOf("straight", "left")).toBe("left");
    expect(relativeLabel("turn_right")).toBe("Turn right");
    expect(relativeSymbol("turn_left")).toBe("↺");
  });
});

describe("relative actions drive the game", () => {
  it("turns the snake instead of dying at a wall", () => {
    const state = {
      size: 12,
      snake: [
        { x: 11, y: 6 },
        { x: 10, y: 6 },
        { x: 9, y: 6 },
      ],
      direction: "right" as Direction,
      food: { x: 1, y: 0 },
      score: 0,
      moves: 0,
      eaten: 0,
      outcome: null,
    };

    const straight = step(state, absoluteOf("straight", state.direction), () => 0);
    const turnLeft = step(state, absoluteOf("turn_left", state.direction), () => 0);

    expect(straight.outcome).toBe("wall");
    expect(turnLeft.outcome).toBe("moved");
    expect(turnLeft.snake[0]).toEqual({ x: 11, y: 5 });
  });
});
