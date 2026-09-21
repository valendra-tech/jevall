import type {
  DecisionPayload,
  DecisionResponse,
  Direction,
  TurnDiagnostics,
} from "./types";

export type DecisionApiErrorKind = "timeout" | "upstream" | "invalid";

export class DecisionApiError extends Error {
  readonly kind: DecisionApiErrorKind;
  readonly status: number | null;

  constructor(
    message: string,
    kind: DecisionApiErrorKind,
    status: number | null = null,
  ) {
    super(message);
    this.name = "DecisionApiError";
    this.kind = kind;
    this.status = status;
  }
}

export type DecisionOutcome = {
  response: DecisionResponse;
  selected: Direction;
  probabilities: Record<string, number>;
  latencyMs: number;
  diagnostics: TurnDiagnostics;
};

const CLIENT_TIMEOUT_MS = 12_000;

function numberOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/**
 * One decision call through the local proxy. The proxy owns the upstream URL
 * and its timeout, so this stays a thin client.
 */
export async function requestDecision(
  payload: DecisionPayload,
): Promise<DecisionOutcome> {
  const started = performance.now();
  let response: Response;
  try {
    response = await fetch("/api/decisions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(CLIENT_TIMEOUT_MS),
    });
  } catch (error) {
    const timedOut =
      error instanceof DOMException && error.name === "TimeoutError";
    throw new DecisionApiError(
      timedOut ? "client timeout" : "network error",
      timedOut ? "timeout" : "upstream",
    );
  }

  const latencyMs = performance.now() - started;

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = (await response.json()) as { error?: string };
      if (typeof body.error === "string") {
        detail = body.error;
      }
    } catch {
      // keep the HTTP status as the message
    }
    throw new DecisionApiError(
      detail,
      response.status === 504 ? "timeout" : "upstream",
      response.status,
    );
  }

  const body = (await response.json()) as DecisionResponse;
  const decision = body?.decisions?.[0];
  if (!decision || typeof decision.selected !== "string") {
    throw new DecisionApiError("malformed decision response", "invalid");
  }

  return {
    response: body,
    selected: decision.selected as Direction,
    probabilities: decision.probabilities ?? {},
    latencyMs,
    diagnostics: {
      queueMs: numberOrNull(body.diagnostics?.queue_ms),
      forwardMs: numberOrNull(body.diagnostics?.forward_ms),
      scoringMs: numberOrNull(body.diagnostics?.scoring_ms),
    },
  };
}
