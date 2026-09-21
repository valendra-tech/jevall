import { buildStateText } from "./stateText";
import type { GameState } from "./game";
import type { StatePart } from "./types";

/**
 * Render the board to a PNG data URI with an offscreen canvas. Browser only.
 * Returns null when canvas is unavailable (SSR or tests).
 */
export function renderBoardPng(state: GameState, cell = 26, border = 2): string | null {
  if (typeof document === "undefined") {
    return null;
  }
  const size = state.size;
  const width = size * cell + (size + 1) * border;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = width;
  const context = canvas.getContext("2d");
  if (!context) {
    return null;
  }

  context.fillStyle = "#3f3f46";
  context.fillRect(0, 0, width, width);

  const colors = {
    empty: "#18181b",
    head: "#34d399",
    body: "#059669",
    food: "#fbbf24",
  };

  const body = new Set(state.snake.slice(1).map((point) => `${point.x},${point.y}`));
  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      const key = `${x},${y}`;
      let color = colors.empty;
      if (state.snake[0].x === x && state.snake[0].y === y) {
        color = colors.head;
      } else if (body.has(key)) {
        color = colors.body;
      } else if (state.food.x === x && state.food.y === y) {
        color = colors.food;
      }
      context.fillStyle = color;
      context.fillRect(
        border + x * (cell + border),
        border + y * (cell + border),
        cell,
        cell,
      );
    }
  }

  return canvas.toDataURL("image/png");
}

export type StatePartsOptions = {
  vision: boolean;
  imageDataUri: string | null;
  framing?: "relative" | "absolute";
};

export function buildStateParts(
  state: GameState,
  options: StatePartsOptions,
): string | StatePart[] {
  const framing = options.framing ?? "relative";
  if (!options.vision || !options.imageDataUri) {
    return buildStateText(state, { includeBoard: true, framing });
  }
  return [
    {
      type: "text",
      text: buildStateText(state, { includeBoard: false, framing }),
    },
    { type: "image", uri: options.imageDataUri },
  ];
}

export function statePartsLabel(
  state: GameState,
  options: { vision: boolean; framing?: "relative" | "absolute" },
): string {
  return buildStateText(state, {
    includeBoard: !options.vision,
    framing: options.framing ?? "relative",
  });
}
