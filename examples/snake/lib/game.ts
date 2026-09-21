import type { ActionId, Direction, Point, RelativeAction, TurnOutcome } from "./types";

export const DIRECTIONS: Direction[] = ["up", "down", "left", "right"];
export const RELATIVE_ACTIONS: RelativeAction[] = [
  "turn_left",
  "straight",
  "turn_right",
];

/** Clockwise order used to rotate headings. */
const CLOCKWISE: Direction[] = ["up", "right", "down", "left"];

const DELTAS: Record<Direction, Point> = {
  up: { x: 0, y: -1 },
  down: { x: 0, y: 1 },
  left: { x: -1, y: 0 },
  right: { x: 1, y: 0 },
};

export type GameState = {
  size: number;
  /** Head first. */
  snake: Point[];
  direction: Direction;
  food: Point;
  score: number;
  /** Every applied direction, including a fatal one. */
  moves: number;
  eaten: number;
  /** `null` while the game is alive. */
  outcome: TurnOutcome | null;
};

export type Random = () => number;

export function opposite(direction: Direction): Direction {
  switch (direction) {
    case "up":
      return "down";
    case "down":
      return "up";
    case "left":
      return "right";
    case "right":
      return "left";
  }
}

/**
 * Options offered to the model: only the 180 degree reversal is removed
 * because it is a game rule. Colliding directions stay on the table.
 */
export function availableDirections(direction: Direction): Direction[] {
  const reverse = opposite(direction);
  return DIRECTIONS.filter((candidate) => candidate !== reverse);
}

/**
 * Map each relative action to an absolute direction for the current heading.
 * `behind` is never an action, so the 180 degree reversal cannot be chosen.
 */
export function relativeDirections(
  heading: Direction,
): Record<RelativeAction, Direction> {
  const index = CLOCKWISE.indexOf(heading);
  return {
    turn_left: CLOCKWISE[(index + 3) % 4],
    straight: heading,
    turn_right: CLOCKWISE[(index + 1) % 4],
  };
}

export function absoluteOf(action: RelativeAction, heading: Direction): Direction {
  return relativeDirections(heading)[action];
}

const RELATIVE_IDS: RelativeAction[] = ["turn_left", "straight", "turn_right"];

export function isRelativeAction(id: ActionId): id is RelativeAction {
  return (RELATIVE_IDS as string[]).includes(id);
}

/** Resolve either an absolute direction or a relative action to a direction. */
export function resolveDirection(id: ActionId, heading: Direction): Direction {
  return isRelativeAction(id) ? absoluteOf(id, heading) : id;
}

export function actionSymbol(id: ActionId): string {
  return isRelativeAction(id) ? relativeSymbol(id) : directionSymbol(id);
}

export function nextPoint(point: Point, direction: Direction): Point {
  const delta = DELTAS[direction];
  return { x: point.x + delta.x, y: point.y + delta.y };
}

export function relativeLabel(action: RelativeAction): string {
  switch (action) {
    case "turn_left":
      return "Turn left";
    case "straight":
      return "Keep going straight";
    case "turn_right":
      return "Turn right";
  }
}

export function relativeSymbol(action: RelativeAction): string {
  switch (action) {
    case "turn_left":
      return "↺";
    case "straight":
      return "↑";
    case "turn_right":
      return "↻";
  }
}

export function directionSymbol(direction: Direction): string {
  switch (direction) {
    case "up":
      return "↑";
    case "down":
      return "↓";
    case "left":
      return "←";
    case "right":
      return "→";
  }
}

export function samePoint(left: Point, right: Point): boolean {
  return left.x === right.x && left.y === right.y;
}

export function spawnFood(
  snake: Point[],
  size: number,
  random: Random = Math.random,
): Point | null {
  const occupied = new Set(snake.map((segment) => `${segment.x},${segment.y}`));
  const free: Point[] = [];
  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      if (!occupied.has(`${x},${y}`)) {
        free.push({ x, y });
      }
    }
  }
  if (free.length === 0) {
    return null;
  }
  const index = Math.min(free.length - 1, Math.floor(random() * free.length));
  return free[index];
}

export function createGame(size = 12, random: Random = Math.random): GameState {
  const middle = Math.floor(size / 2);
  const snake: Point[] = [
    { x: middle, y: middle },
    { x: middle - 1, y: middle },
    { x: middle - 2, y: middle },
  ];
  const food = spawnFood(snake, size, random);
  return {
    size,
    snake,
    direction: "right",
    food: food ?? { x: 0, y: 0 },
    score: 0,
    moves: 0,
    eaten: 0,
    outcome: food ? null : "board-full",
  };
}

/**
 * Apply exactly the requested direction. There is no correction: a fatal
 * direction kills the snake.
 */
export function step(
  state: GameState,
  direction: Direction,
  random: Random = Math.random,
): GameState {
  const head = state.snake[0];
  const delta = DELTAS[direction];
  const next: Point = { x: head.x + delta.x, y: head.y + delta.y };
  const moves = state.moves + 1;

  if (
    next.x < 0 ||
    next.y < 0 ||
    next.x >= state.size ||
    next.y >= state.size
  ) {
    return { ...state, direction, moves, outcome: "wall" };
  }

  const eats = samePoint(next, state.food);
  const body = eats ? state.snake : state.snake.slice(0, -1);
  if (body.some((segment) => samePoint(segment, next))) {
    return { ...state, direction, moves, outcome: "self" };
  }

  const snake = [next, ...(eats ? state.snake : state.snake.slice(0, -1))];
  if (!eats) {
    return { ...state, snake, direction, moves, outcome: "moved" };
  }

  const food = spawnFood(snake, state.size, random);
  return {
    ...state,
    snake,
    direction,
    moves,
    score: state.score + 1,
    eaten: state.eaten + 1,
    food: food ?? state.food,
    outcome: food ? "ate" : "board-full",
  };
}

export function isFatal(outcome: TurnOutcome | null): boolean {
  return outcome === "wall" || outcome === "self" || outcome === "board-full";
}

export function outcomeLabel(outcome: TurnOutcome): string {
  switch (outcome) {
    case "moved":
      return "survived";
    case "ate":
      return "ate food";
    case "wall":
      return "WALL COLLISION";
    case "self":
      return "SELF COLLISION";
    case "board-full":
      return "BOARD FULL";
  }
}

export function keyOf(point: Point): string {
  return `${point.x},${point.y}`;
}
