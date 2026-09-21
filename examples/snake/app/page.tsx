"use client";

import { useMemo } from "react";

import { Board } from "@/components/Board";
import { Controls } from "@/components/Controls";
import { DebugPanel } from "@/components/DebugPanel";
import { DecisionPanel, LatencyPanel } from "@/components/DecisionPanel";
import { GameOverPanel, HistoryTable, MetricsBar } from "@/components/Summary";
import { useSnakeGame } from "@/hooks/useSnakeGame";
import { buildOptions } from "@/lib/options";
import { downloadRun, MODEL_ID } from "@/lib/export";

export default function Page() {
  const {
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
    vision,
    setSpeed,
    setShowProbabilities,
    setShowHeatmap,
    setVision,
    switchMode,
    start,
    pause,
    resume,
    restart,
  } = useSnakeGame();

  const last = history.at(-1) ?? null;
  const boardOptions = useMemo(
    () => (mode === "ai" ? buildOptions(game) : []),
    [game, mode],
  );

  return (
    <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:py-12">
      <header className="mb-6">
        <h1 className="font-mono text-lg text-zinc-100">Jevall Snake</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Snake controlled one probabilistic decision at a time.
        </p>
        <p className="mt-1 max-w-2xl text-xs text-zinc-500">
          No generated moves. Every step is selected from a probability
          distribution produced by the model.{" "}
          <span className="font-mono text-zinc-400">
            state → probabilities → movement
          </span>
        </p>
        <p className="mt-2 font-mono text-[11px] text-zinc-600">
          model {MODEL_ID}
        </p>
      </header>

      <div className="mb-6 rounded-xl border border-zinc-800 bg-zinc-900/40 p-3">
        <Controls
          mode={mode}
          phase={phase}
          speed={speed}
          thinking={thinking}
          showProbabilities={showProbabilities}
          showCandidates={showHeatmap}
          vision={vision}
          hasHistory={history.length > 0}
          onModeChange={switchMode}
          onSpeedChange={setSpeed}
          onStart={start}
          onPause={pause}
          onResume={resume}
          onRestart={restart}
          onToggleProbabilities={setShowProbabilities}
          onToggleCandidates={setShowHeatmap}
          onToggleVision={setVision}
          onExport={() => downloadRun(game, history)}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-4">
          <Board
            game={game}
            options={boardOptions}
            probabilities={mode === "ai" ? last?.probabilities ?? null : null}
            showProbabilities={showProbabilities && mode === "ai"}
            showCandidates={showHeatmap}
          />
          <p className="font-mono text-[11px] text-zinc-600">
            board {game.size}×{game.size} · score {game.score} · moves{" "}
            {game.moves} · length {game.snake.length}
          </p>
          {phase === "over" ? (
            <GameOverPanel
              game={game}
              history={history}
              mode={mode}
              onRestart={restart}
            />
          ) : null}
        </div>

        <div className="space-y-4">
          <DecisionPanel
            mode={mode}
            thinking={thinking}
            error={error}
            last={last}
            onRetry={resume}
            onRestart={restart}
          />
          <LatencyPanel
            diagnostics={last?.diagnostics ?? null}
            total={last?.latencyMs ?? null}
          />
        </div>
      </div>

      <div className="mt-6 space-y-4">
        <MetricsBar history={history} />
        <HistoryTable history={history} />
        <DebugPanel debug={debug} />
      </div>

      <footer className="mt-10 border-t border-zinc-800 pt-4 text-[11px] text-zinc-600">
        Probabilities are raw model outputs, not calibrated confidences. The
        game never corrects a decision: if the model picks a wall, the snake
        dies.
      </footer>
    </main>
  );
}
