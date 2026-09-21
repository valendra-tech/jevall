import { availableDirections, type GameState } from "./game";
import type { DecisionOption, Direction } from "./types";

const LABELS: Record<Direction, string> = {
  up: "Move up",
  down: "Move down",
  left: "Move left",
  right: "Move right",
};

export const MOVE_PROMPT =
  "What should the snake do next to survive and move toward the food?";

export function buildOptions(state: Pick<GameState, "direction">): DecisionOption[] {
  return availableDirections(state.direction).map((direction) => ({
    id: direction,
    text: LABELS[direction],
  }));
}

export function isOffered(options: DecisionOption[], direction: Direction): boolean {
  return options.some((option) => option.id === direction);
}
