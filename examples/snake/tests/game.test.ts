import { availableDirections, createGame, spawnFood, step } from "@/lib/game";
import type { GameState } from "@/lib/game";

function state(overrides: Partial<GameState> = {}): GameState {
  return {
    size: 5,
    snake: [
      { x: 2, y: 2 },
      { x: 1, y: 2 },
      { x: 0, y: 2 },
    ],
    direction: "right",
    food: { x: 4, y: 0 },
    score: 0,
    moves: 0,
    eaten: 0,
    outcome: null,
    ...overrides,
  };
}

describe("createGame", () => {
  it("starts with a three segment snake heading right and food off the snake", () => {
    const game = createGame(12, () => 0);

    expect(game.snake).toHaveLength(3);
    expect(game.direction).toBe("right");
    expect(game.outcome).toBeNull();
    expect(game.snake.some((segment) => segment.x === game.food.x && segment.y === game.food.y)).toBe(false);
  });

  it("honours the configured board size", () => {
    expect(createGame(20, () => 0).size).toBe(20);
  });
});

describe("availableDirections", () => {
  it("removes only the 180 degree reversal", () => {
    expect(availableDirections("right")).toEqual(["up", "down", "right"]);
    expect(availableDirections("up")).toEqual(["up", "left", "right"]);
    expect(availableDirections("down")).toEqual(["down", "left", "right"]);
    expect(availableDirections("left")).toEqual(["up", "down", "left"]);
  });

  it("keeps colliding directions on the table", () => {
    const game = state({ snake: [{ x: 2, y: 0 }, { x: 1, y: 0 }, { x: 0, y: 0 }] });

    expect(availableDirections(game.direction)).toContain("up");
  });
});

describe("step", () => {
  it("moves the head and drops the tail", () => {
    const next = step(state(), "right", () => 0);

    expect(next.outcome).toBe("moved");
    expect(next.snake[0]).toEqual({ x: 3, y: 2 });
    expect(next.snake).toHaveLength(3);
    expect(next.moves).toBe(1);
  });

  it("reports a wall collision and applies the fatal direction", () => {
    const game = state({
      snake: [
        { x: 2, y: 0 },
        { x: 1, y: 0 },
        { x: 0, y: 0 },
      ],
    });

    const next = step(game, "up", () => 0);

    expect(next.outcome).toBe("wall");
    expect(next.direction).toBe("up");
    expect(next.moves).toBe(1);
  });

  it("reports a self collision", () => {
    const game = state({
      snake: [
        { x: 2, y: 2 },
        { x: 2, y: 1 },
        { x: 1, y: 1 },
        { x: 1, y: 2 },
        { x: 1, y: 3 },
      ],
      direction: "up",
    });

    expect(step(game, "left", () => 0).outcome).toBe("self");
  });

  it("allows moving into the cell the tail is leaving", () => {
    const game = state({
      snake: [
        { x: 2, y: 2 },
        { x: 2, y: 1 },
        { x: 1, y: 1 },
        { x: 1, y: 2 },
      ],
      direction: "down",
    });

    const next = step(game, "left", () => 0);

    expect(next.outcome).toBe("moved");
    expect(next.snake[0]).toEqual({ x: 1, y: 2 });
  });

  it("grows and scores when eating, then respawns food on a free cell", () => {
    const game = state({ food: { x: 3, y: 2 } });

    const next = step(game, "right", () => 0);

    expect(next.outcome).toBe("ate");
    expect(next.snake).toHaveLength(4);
    expect(next.score).toBe(1);
    expect(next.eaten).toBe(1);
    expect(next.snake.some((segment) => segment.x === next.food.x && segment.y === next.food.y)).toBe(false);
  });

  it("never corrects a suicidal direction", () => {
    const game = state({
      snake: [
        { x: 2, y: 0 },
        { x: 1, y: 0 },
        { x: 0, y: 0 },
      ],
      direction: "right",
    });
    const next = step(game, "up", () => 0);

    expect(next.outcome).toBe("wall");
    expect(next.snake[0]).toEqual({ x: 2, y: 0 });
  });
});

describe("spawnFood", () => {
  it("never returns an occupied cell", () => {
    const snake = [
      { x: 0, y: 0 },
      { x: 1, y: 0 },
      { x: 2, y: 0 },
    ];
    for (const value of [0, 0.1, 0.25, 0.5, 0.75, 0.99]) {
      const food = spawnFood(snake, 3, () => value);
      expect(food).not.toBeNull();
      expect(snake.some((segment) => segment.x === food?.x && segment.y === food?.y)).toBe(false);
    }
  });

  it("returns null when the board is full", () => {
    const snake = [];
    for (let y = 0; y < 2; y += 1) {
      for (let x = 0; x < 2; x += 1) {
        snake.push({ x, y });
      }
    }

    expect(spawnFood(snake, 2, () => 0)).toBeNull();
  });
});
