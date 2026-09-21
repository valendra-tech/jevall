"use client";

import { useMemo } from "react";

import {
  actionSymbol,
  directionSymbol,
  keyOf,
  nextPoint,
  resolveDirection,
  type GameState,
} from "@/lib/game";
import type { DecisionOption } from "@/lib/types";

type BoardProps = {
  game: GameState;
  options: DecisionOption[];
  probabilities: Record<string, number> | null;
  showProbabilities: boolean;
  showCandidates: boolean;
};

export function Board({
  game,
  options,
  probabilities,
  showProbabilities,
  showCandidates,
}: BoardProps) {
  const cells = useMemo(() => {
    const body = new Set(game.snake.slice(1).map(keyOf));
    const head = game.snake[0];
    const rows: Array<Array<"empty" | "head" | "body" | "food">> = [];
    for (let y = 0; y < game.size; y += 1) {
      const row: Array<"empty" | "head" | "body" | "food"> = [];
      for (let x = 0; x < game.size; x += 1) {
        const point = { x, y };
        if (head.x === x && head.y === y) {
          row.push("head");
        } else if (body.has(keyOf(point))) {
          row.push("body");
        } else if (game.food.x === x && game.food.y === y) {
          row.push("food");
        } else {
          row.push("empty");
        }
      }
      rows.push(row);
    }
    return rows;
  }, [game]);

  // Each relative action resolved to the absolute cell it would occupy.
  const candidates = useMemo(() => {
    const head = game.snake[0];
    const occupied = new Set(game.snake.slice(1).map(keyOf));
    return options.map((option) => {
      const direction = resolveDirection(option.id, game.direction);
      const point = nextPoint(head, direction);
      const inside =
        point.x >= 0 &&
        point.y >= 0 &&
        point.x < game.size &&
        point.y < game.size;
      return {
        id: option.id,
        direction,
        point,
        inside,
        blocked: inside && occupied.has(keyOf(point)),
      };
    });
  }, [game, options]);

  const candidateByKey = useMemo(
    () =>
      new Map(
        candidates.filter((c) => c.inside).map((c) => [keyOf(c.point), c]),
      ),
    [candidates],
  );

  const cellPercent = 100 / game.size;
  const head = game.snake[0];
  const labels = candidates
    .filter((candidate) => probabilities && candidate.id in probabilities)
    .map((candidate) => {
      const dx = candidate.direction === "left" ? -1 : candidate.direction === "right" ? 1 : 0;
      const dy = candidate.direction === "up" ? -1 : candidate.direction === "down" ? 1 : 0;
      const x = Math.min(96, Math.max(4, (head.x + 0.5 + dx * 0.62) * cellPercent));
      const y = Math.min(96, Math.max(4, (head.y + 0.5 + dy * 0.62) * cellPercent));
      return {
        id: candidate.id,
        direction: candidate.direction,
        x,
        y,
        value: probabilities?.[candidate.id] ?? 0,
      };
    });

  return (
    <div className="relative aspect-square w-full overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/40">
      <div
        className="grid h-full w-full"
        style={{
          gridTemplateColumns: `repeat(${game.size}, minmax(0, 1fr))`,
          gridTemplateRows: `repeat(${game.size}, minmax(0, 1fr))`,
        }}
      >
        {cells.map((row, y) =>
          row.map((cell, x) => {
            const candidate = candidateByKey.get(`${x},${y}`);
            return (
              <div
                key={`${x},${y}`}
                className={[
                  "relative border-[0.5px] border-zinc-800/60",
                  cell === "head"
                    ? "bg-emerald-400"
                    : cell === "body"
                      ? "bg-emerald-600/80"
                      : cell === "food"
                        ? "bg-amber-400"
                        : "bg-transparent",
                  showCandidates && candidate && cell === "empty"
                    ? candidate.blocked
                      ? "bg-rose-500/25 ring-1 ring-inset ring-rose-500/50"
                      : "bg-sky-500/10 ring-1 ring-inset ring-sky-500/30"
                    : "",
                ].join(" ")}
              />
            );
          }),
        )}
      </div>

      {showProbabilities && labels.length > 0 ? (
        <div className="pointer-events-none absolute inset-0">
          {labels.map((label) => (
            <span
              key={label.id}
              className="absolute -translate-x-1/2 -translate-y-1/2 rounded border border-zinc-700 bg-zinc-950/85 px-1 py-0.5 font-mono text-[10px] text-zinc-300"
              style={{ left: `${label.x}%`, top: `${label.y}%` }}
              title={`${actionSymbol(label.id)} ${label.id} → ${label.direction}`}
            >
              {directionSymbol(label.direction)} {(label.value * 100).toFixed(0)}%
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}
