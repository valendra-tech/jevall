export type Direction = "up" | "down" | "left" | "right";

export type RelativeAction = "turn_left" | "straight" | "turn_right";

export type ActionId = RelativeAction | Direction;

export type Framing = "relative" | "absolute";

export type Point = { x: number; y: number };

export type Speed = "slow" | "normal" | "fast";

export type Mode = "ai" | "human";

export type Phase = "idle" | "running" | "thinking" | "paused" | "over";

export type TurnOutcome = "moved" | "ate" | "wall" | "self" | "board-full";

export type DecisionOption = { id: ActionId; text: string };

export type StatePart =
  | { type: "text"; text: string }
  | { type: "image"; uri: string };

export type DecisionPayload = {
  model: string;
  state: string | StatePart[];
  questions: Array<{
    id: "move";
    type: "choice";
    prompt: string;
    options: DecisionOption[];
  }>;
};

export type DecisionResult = {
  id: string;
  type: string;
  selected: string;
  probabilities: Record<string, number>;
};

export type DecisionResponse = {
  id: string;
  model: string;
  decisions: DecisionResult[];
  usage?: { latency_ms?: number };
  diagnostics?: Record<string, unknown>;
};

export type TurnDiagnostics = {
  queueMs: number | null;
  forwardMs: number | null;
  scoringMs: number | null;
};

export type HistoryEntry = {
  turn: number;
  stateText: string;
  usedImage: boolean;
  options: DecisionOption[];
  rawResponse: DecisionResponse | null;
  /** The action the model chose (relative or absolute, depending on framing). */
  selected: ActionId;
  /** Heading before the move, so relative actions can be resolved later. */
  heading: Direction;
  /** The absolute direction that action resolves to for this turn. */
  applied: Direction;
  probabilities: Record<string, number>;
  selectedProbability: number | null;
  latencyMs: number;
  diagnostics: TurnDiagnostics;
  outcome: TurnOutcome;
  boardBefore: string;
  boardAfter: string;
};

export type RunExport = {
  model: string;
  boardSize: number;
  score: number;
  moves: number;
  survived: number;
  snakeLength: number;
  cause: TurnOutcome | null;
  averageLatencyMs: number | null;
  averageSelectedProbability: number | null;
  history: HistoryEntry[];
};
