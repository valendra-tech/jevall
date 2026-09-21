"use client";

import type { Mode, Phase, Speed } from "@/lib/types";

type ControlsProps = {
  mode: Mode;
  phase: Phase;
  speed: Speed;
  thinking: boolean;
  showProbabilities: boolean;
  showCandidates: boolean;
  vision: boolean;
  hasHistory: boolean;
  onModeChange: (mode: Mode) => void;
  onSpeedChange: (speed: Speed) => void;
  onStart: () => void;
  onPause: () => void;
  onResume: () => void;
  onRestart: () => void;
  onToggleProbabilities: (value: boolean) => void;
  onToggleCandidates: (value: boolean) => void;
  onToggleVision: (value: boolean) => void;
  onExport: () => void;
};

const PHASE_LABEL: Record<Phase, string> = {
  idle: "idle",
  running: "running",
  thinking: "thinking",
  paused: "paused",
  over: "game over",
};

export function Controls({
  mode,
  phase,
  speed,
  thinking,
  showProbabilities,
  showCandidates,
  vision,
  hasHistory,
  onModeChange,
  onSpeedChange,
  onStart,
  onPause,
  onResume,
  onRestart,
  onToggleProbabilities,
  onToggleCandidates,
  onToggleVision,
  onExport,
}: ControlsProps) {
  const live = phase === "running" || phase === "thinking";

  return (
    <div className="flex flex-wrap items-center gap-3">
      <Segmented
        label="Mode"
        options={[
          { value: "ai", label: "AI" },
          { value: "human", label: "Human" },
        ]}
        value={mode}
        onChange={(value) => onModeChange(value as Mode)}
      />

      <Segmented
        label="Speed"
        options={[
          { value: "slow", label: "Slow" },
          { value: "normal", label: "Normal" },
          { value: "fast", label: "Fast" },
        ]}
        value={speed}
        onChange={(value) => onSpeedChange(value as Speed)}
      />

      <div className="flex items-center gap-2">
        {live ? (
          <button
            type="button"
            onClick={onPause}
            className="rounded-md border border-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-300 hover:border-zinc-500"
          >
            Pause
          </button>
        ) : phase === "paused" ? (
          <button
            type="button"
            onClick={onResume}
            className="rounded-md bg-zinc-100 px-3 py-1.5 text-xs font-medium text-zinc-900 hover:bg-white"
          >
            Resume
          </button>
        ) : (
          <button
            type="button"
            onClick={onStart}
            disabled={phase === "over"}
            className="rounded-md bg-zinc-100 px-3 py-1.5 text-xs font-medium text-zinc-900 hover:bg-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            Start
          </button>
        )}
        <button
          type="button"
          onClick={onRestart}
          className="rounded-md border border-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-300 hover:border-zinc-500"
        >
          Restart
        </button>
        <button
          type="button"
          onClick={onExport}
          disabled={!hasHistory}
          className="rounded-md border border-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-300 hover:border-zinc-500 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Export run
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-4 text-xs text-zinc-400">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={showProbabilities}
            onChange={(event) => onToggleProbabilities(event.target.checked)}
            className="h-3.5 w-3.5 accent-emerald-500"
          />
          Show probabilities on board
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={showCandidates}
            onChange={(event) => onToggleCandidates(event.target.checked)}
            className="h-3.5 w-3.5 accent-sky-500"
          />
          Candidate cells
        </label>
        <label className="flex items-center gap-2" title="Send the board as a PNG image instead of ASCII art (native vision)">
          <input
            type="checkbox"
            checked={vision}
            onChange={(event) => onToggleVision(event.target.checked)}
            className="h-3.5 w-3.5 accent-emerald-500"
          />
          Send board as image
        </label>
      </div>

      <span className="ml-auto flex items-center gap-2 font-mono text-xs text-zinc-500">
        <span
          className={`h-1.5 w-1.5 rounded-full ${
            thinking
              ? "animate-pulse bg-sky-400"
              : phase === "over"
                ? "bg-rose-500"
                : phase === "paused"
                  ? "bg-amber-400"
                  : live
                    ? "bg-emerald-400"
                    : "bg-zinc-600"
          }`}
        />
        {thinking ? "thinking" : PHASE_LABEL[phase]}
      </span>
    </div>
  );
}

function Segmented({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: Array<{ value: string; label: string }>;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] uppercase tracking-wide text-zinc-500">
        {label}
      </span>
      <div className="flex rounded-md border border-zinc-800 p-0.5">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            className={`rounded px-2.5 py-1 text-xs font-medium ${
              option.value === value
                ? "bg-zinc-800 text-zinc-100"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}
