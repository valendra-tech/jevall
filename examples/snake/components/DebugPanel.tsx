"use client";

import type { DebugTurn } from "@/hooks/useSnakeGame";

export function DebugPanel({ debug }: { debug: DebugTurn }) {
  if (!debug) {
    return null;
  }

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900/40">
      <details>
        <summary className="cursor-pointer px-4 py-3 text-xs font-medium uppercase tracking-wide text-zinc-500 hover:text-zinc-300">
          Model state and raw response
        </summary>
        <div className="grid gap-4 border-t border-zinc-800 p-4 lg:grid-cols-2">
          <div>
            <h3 className="mb-2 text-[10px] uppercase tracking-wide text-zinc-500">
              Model state
            </h3>
            <pre className="max-h-96 overflow-auto rounded-lg border border-zinc-800 bg-zinc-950/70 p-3 font-mono text-[11px] leading-relaxed text-zinc-400">
              {debug.stateText}
            </pre>
          </div>
          <div>
            <h3 className="mb-2 text-[10px] uppercase tracking-wide text-zinc-500">
              Raw response
            </h3>
            <pre className="max-h-96 overflow-auto rounded-lg border border-zinc-800 bg-zinc-950/70 p-3 font-mono text-[11px] leading-relaxed text-zinc-400">
              {JSON.stringify(debug.rawResponse, null, 2)}
            </pre>
          </div>
        </div>
      </details>
    </section>
  );
}
