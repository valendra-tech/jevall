import { keyOf, type GameState } from "./game";

/** Render the board as ASCII rows, head first priority. */
export function renderBoard(state: GameState): string {
  const cells: string[][] = Array.from({ length: state.size }, () =>
    Array.from({ length: state.size }, () => "."),
  );

  cells[state.food.y][state.food.x] = "F";
  for (const segment of state.snake.slice(1)) {
    cells[segment.y][segment.x] = "S";
  }
  const head = state.snake[0];
  cells[head.y][head.x] = "H";

  return cells.map((row) => row.join("")).join("\n");
}

export function directionLabel(direction: string): string {
  return direction.toUpperCase();
}

export function formatPoint(point: { x: number; y: number }): string {
  return `(${point.x},${point.y})`;
}

export type StateTextOptions = {
  includeBoard?: boolean;
  framing?: "relative" | "absolute";
};

const RELATIVE_ACTIONS_BLOCK = [
  "Actions, relative to the current direction:",
  "turn_left = rotate 90 degrees counter-clockwise, then advance one cell.",
  "straight = keep the current direction, then advance one cell.",
  "turn_right = rotate 90 degrees clockwise, then advance one cell.",
  "Reversing is not a legal action and is never offered.",
];

const ABSOLUTE_ACTIONS_BLOCK = [
  "Actions: move up, move down, move left or move right.",
  "A move that reverses the current direction is not offered.",
];

export function buildStateText(
  state: GameState,
  options: StateTextOptions = {},
): string {
  const includeBoard = options.includeBoard ?? true;
  const framing = options.framing ?? "relative";
  const head = state.snake[0];
  const body = state.snake.slice(1);

  return [
    "SNAKE GAME",
    "",
    `Board size: ${state.size}x${state.size}`,
    "Coordinates: x increases left-to-right, y increases top-to-bottom.",
    "",
    "You control the snake in the game below.",
    "",
    "Your priorities, in order, are:",
    "1. Avoid immediate death by hitting the wall.",
    "2. Avoid hitting the snake body.",
    "3. Move toward the food when safe.",
    "4. Preserve future movement space.",
    "5. Survive for as long as possible.",
    "",
    "Inspect the board and choose the best next movement.",
    "Do not assume any information not represented in the state.",
    "",
    `Current direction: ${directionLabel(state.direction)}`,
    "",
    ...(framing === "relative" ? RELATIVE_ACTIONS_BLOCK : ABSOLUTE_ACTIONS_BLOCK),
    "",
    "Legend:",
    ". = empty",
    "H = snake head",
    "S = snake body",
    "F = food",
    "",
    ...(includeBoard
      ? ["Board:", "", renderBoard(state), ""]
      : ["The board is attached as an image.", ""]),
    `Snake head: ${formatPoint(head)}`,
    `Snake body: [${body.map(formatPoint).join(",")}]`,
    `Food: ${formatPoint(state.food)}`,
    "",
    "Choose the best next movement.",
  ].join("\n");
}

export function occupiedKeys(state: GameState): Set<string> {
  return new Set(state.snake.map(keyOf));
}
