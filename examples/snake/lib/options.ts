import {
  RELATIVE_ACTIONS,
  actionSymbol,
  availableDirections,
  isRelativeAction,
  relativeLabel,
} from "./game";
import type { ActionId, DecisionOption, Direction } from "./types";

export const MOVE_PROMPT =
  "What should the snake do next to survive and move toward the food?";

/**
 * Relative framing: turn_left / straight / turn_right. The 180 degree reversal
 * is not representable, so it can never be offered.
 */
export function buildRelativeOptions(): DecisionOption[] {
  return RELATIVE_ACTIONS.map((action) => ({
    id: action,
    text: relativeLabel(action),
  }));
}

/**
 * Absolute framing: the three directions that do not reverse the heading.
 * Colliding directions stay on the table.
 */
export function buildAbsoluteOptions(heading: Direction): DecisionOption[] {
  return availableDirections(heading).map((direction) => ({
    id: direction,
    text: `Move ${direction}`,
  }));
}

export function optionSymbol(id: ActionId): string {
  return actionSymbol(id);
}

export function optionText(id: ActionId): string {
  return isRelativeAction(id) ? relativeLabel(id) : `Move ${id}`;
}

export function isOffered(options: DecisionOption[], action: string): boolean {
  return options.some((option) => option.id === action);
}
