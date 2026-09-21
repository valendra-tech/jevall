import { buildStateText, renderBoard } from "@/lib/stateText";
import { createGame } from "@/lib/game";

describe("renderBoard", () => {
  it("marks head, body and food and keeps the grid rectangular", () => {
    const game = createGame(12, () => 0);
    const rows = renderBoard(game).split("\n");

    expect(rows).toHaveLength(12);
    expect(rows.every((row) => row.length === 12)).toBe(true);
    expect(renderBoard(game)).toContain("H");
    expect(renderBoard(game)).toContain("S");
    expect(renderBoard(game)).toContain("F");
  });
});

describe("buildStateText", () => {
  it("describes the rules, the board and the coordinates", () => {
    const game = createGame(12, () => 0);
    const text = buildStateText(game);
    const head = game.snake[0];
    const body = game.snake.slice(1);

    expect(text).toContain("SNAKE GAME");
    expect(text).toContain("Board size: 12x12");
    expect(text).toContain("Avoid immediate death by hitting the wall");
    expect(text).toContain("Do not assume any information not represented");
    expect(text).toContain("Current direction: RIGHT");
    expect(text).toContain(". = empty");
    expect(text).toContain("H = snake head");
    expect(text).toContain("S = snake body");
    expect(text).toContain("F = food");
    expect(text).toContain(`Snake head: (${head.x},${head.y})`);
    expect(text).toContain(
      `Snake body: [${body.map((point) => `(${point.x},${point.y})`).join(",")}]`,
    );
    expect(text).toContain(`Food: (${game.food.x},${game.food.y})`);
    expect(text).toContain("Choose the best next movement.");
  });

  it("does not leak future information", () => {
    const game = createGame(12, () => 0);
    const text = buildStateText(game).toLowerCase();

    expect(text).not.toContain("next food");
    expect(text).not.toContain("will");
  });
});
