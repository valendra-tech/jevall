"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { DecisionApiError, requestDecision, type DecisionOutcome } from "@/lib/api";
import { MODEL_ID } from "@/lib/export";
import { createGame, isFatal, step, type GameState } from "@/lib/game";
import { buildOptions, isOffered, MOVE_PROMPT } from "@/lib/options";
import { createSingleFlight } from "@/lib/singleFlight";
import { buildStateText, renderBoard } from "@/lib/stateText";
import type {
  DecisionOption,
  Direction,
  HistoryEntry,
  Mode,
  Phase,
  Speed,
} from "@/lib/types";

export const BOARD_SIZE = 12;
export const HISTORY_LIMIT = 200;

const MIN_DELAY_MS: Record<Speed, number> = { slow: 800, normal: 400, fast: 0 };
const HUMAN_TICK_MS: Record<Speed, number> = { slow: 260, normal: 130, fast: 90 };
const KEY_DIRECTIONS: Record<string, Direction> = {
  ArrowUp: "up",
  ArrowDown: "down",
  ArrowLeft: "left",
  ArrowRight: "right",
  w: "up",
  a: "left",
  s: "down",
  d: "right",
};

export type DebugTurn = {
  stateText: string;
  options: DecisionOption[];
  rawResponse: unknown;
} | null;

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function useSnakeGame() {
  const [game, setGame] = useState<GameState>(() => createGame(BOARD_SIZE));
  const [phase, setPhase] = useState<Phase>("idle");
  const [thinking, setThinking] = useState(false);
  const [mode, setMode] = useState<Mode>("ai");
  const [speed, setSpeed] = useState<Speed>("normal");
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [debug, setDebug] = useState<DebugTurn>(null);
  const [showProbabilities, setShowProbabilities] = useState(true);
  const [showHeatmap, setShowHeatmap] = useState(false);

  const gameRef = useRef(game);
  gameRef.current = game;
  const lastMoveAt = useRef(0);
  const humanQueue = useRef<Direction | null>(null);

  // Every decision goes through a single-flight wrapper: two API calls can
  // never overlap, even if a future refactor forgets to await.
  const decide = useMemo(
    () => createSingleFlight((stateText: string, options: DecisionOption[]) =>
      requestDecision({
        model: MODEL_ID,
        state: stateText,
        questions: [
          { id: "move", type: "choice", prompt: MOVE_PROMPT, options },
        ],
      }),
    ),
    [],
  );

  const applyDecision = useCallback(
    (
      current: GameState,
      outcome: DecisionOutcome,
      stateText: string,
      options: DecisionOption[],
    ) => {
      const boardBefore = renderBoard(current);
      const next = step(current, outcome.selected);
      const entry: HistoryEntry = {
        turn: current.moves + 1,
        stateText,
        options,
        rawResponse: outcome.response,
        selected: outcome.selected,
        probabilities: outcome.probabilities,
        selectedProbability:
          outcome.probabilities[outcome.selected] ?? null,
        latencyMs: outcome.latencyMs,
        diagnostics: outcome.diagnostics,
        outcome: next.outcome ?? "moved",
        boardBefore,
        boardAfter: renderBoard(next),
      };

      lastMoveAt.current = performance.now();
      setHistory((entries) => [...entries, entry].slice(-HISTORY_LIMIT));
      setDebug({ stateText, options, rawResponse: outcome.response });
      // The loop reads gameRef synchronously, so it must not wait for a render.
      gameRef.current = next;
      setGame(next);
      if (isFatal(next.outcome)) {
        setPhase("over");
      }
    },
    [],
  );

  // AI loop: one decision at a time, applied verbatim.
  useEffect(() => {
    if (mode !== "ai" || phase !== "running") {
      return;
    }
    let cancelled = false;

    const loop = async () => {
      while (!cancelled) {
        const current = gameRef.current;
        if (isFatal(current.outcome)) {
          return;
        }

        const waitFor = Math.max(
          0,
          MIN_DELAY_MS[speed] - (performance.now() - lastMoveAt.current),
        );
        if (waitFor > 0) {
          await delay(waitFor);
        }
        if (cancelled) {
          return;
        }

        const stateText = buildStateText(current);
        const options = buildOptions(current);
        setThinking(true);
        try {
          const outcome = await decide(stateText, options);
          if (cancelled) {
            return;
          }
          if (!isOffered(options, outcome.selected)) {
            throw new DecisionApiError(
              `model selected "${outcome.selected}", which was not offered`,
              "invalid",
            );
          }
          applyDecision(current, outcome, stateText, options);
        } catch (caught) {
          if (cancelled) {
            return;
          }
          setThinking(false);
          setError(
            caught instanceof Error ? caught.message : "decision API failed",
          );
          setPhase("paused");
          return;
        }
        setThinking(false);
      }
    };

    void loop();
    return () => {
      cancelled = true;
    };
  }, [applyDecision, decide, mode, phase, speed]);

  // Human loop: applies the queued direction on a fixed cadence.
  useEffect(() => {
    if (mode !== "human" || phase !== "running") {
      return;
    }
    let cancelled = false;

    const loop = async () => {
      while (!cancelled) {
        await delay(HUMAN_TICK_MS[speed]);
        if (cancelled) {
          return;
        }
        const current = gameRef.current;
        if (isFatal(current.outcome)) {
          return;
        }
        const direction = humanQueue.current ?? current.direction;
        humanQueue.current = null;
        lastMoveAt.current = performance.now();
        const next = step(current, direction);
        gameRef.current = next;
        setGame(next);
        if (isFatal(next.outcome)) {
          setPhase("over");
          return;
        }
      }
    };

    void loop();
    return () => {
      cancelled = true;
    };
  }, [mode, phase, speed]);

  // Keyboard control for human mode.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (mode !== "human") {
        return;
      }
      const direction = KEY_DIRECTIONS[event.key];
      if (direction) {
        event.preventDefault();
        humanQueue.current = direction;
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [mode]);

  const start = useCallback(() => {
    setError(null);
    setPhase((current) => (current === "over" ? current : "running"));
  }, []);

  const pause = useCallback(() => {
    setPhase((current) => (current === "running" ? "paused" : current));
  }, []);

  const resume = useCallback(() => {
    if (error) {
      setError(null);
    }
    setPhase((current) => (current === "paused" ? "running" : current));
  }, [error]);

  const restart = useCallback(() => {
    const fresh = createGame(BOARD_SIZE);
    gameRef.current = fresh;
    setGame(fresh);
    setHistory([]);
    setDebug(null);
    setError(null);
    setThinking(false);
    humanQueue.current = null;
    lastMoveAt.current = 0;
    setPhase("running");
  }, []);

  const switchMode = useCallback((next: Mode) => {
    setMode(next);
    setError(null);
    setThinking(false);
  }, []);

  return {
    game,
    phase,
    thinking,
    mode,
    speed,
    history,
    error,
    debug,
    showProbabilities,
    showHeatmap,
    setSpeed,
    setShowProbabilities,
    setShowHeatmap,
    switchMode,
    start,
    pause,
    resume,
    restart,
  };
}
