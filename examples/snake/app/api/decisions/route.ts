import { NextResponse } from "next/server";

import { isValidDecisionPayload } from "@/lib/payload";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * The upstream endpoint rejects browser preflights (no CORS headers), so the
 * demo always talks to this proxy. The URL lives only here and in the env.
 */
const DEFAULT_API_URL =
  "https://ba5bu9e1oib70a-8000.proxy.runpod.net/v1/decisions";
const DEFAULT_TIMEOUT_MS = 8000;

function upstreamUrl(): string {
  const configured = process.env.DECISIONS_API_URL?.trim();
  return configured && configured.length > 0 ? configured : DEFAULT_API_URL;
}

function upstreamTimeoutMs(): number {
  const configured = Number(process.env.DECISIONS_API_TIMEOUT_MS);
  return Number.isFinite(configured) && configured > 0
    ? configured
    : DEFAULT_TIMEOUT_MS;
}

export async function POST(request: Request) {
  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }

  if (!isValidDecisionPayload(payload)) {
    return NextResponse.json(
      { error: "model, state and questions are required" },
      { status: 400 },
    );
  }

  try {
    const upstream = await fetch(upstreamUrl(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
      signal: AbortSignal.timeout(upstreamTimeoutMs()),
    });

    const text = await upstream.text();

    if (!upstream.ok) {
      return NextResponse.json(
        {
          error: `decision API returned ${upstream.status}`,
          detail: text.slice(0, 500),
        },
        { status: upstream.status === 504 ? 504 : 502 },
      );
    }

    return new NextResponse(text, {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    const timedOut =
      error instanceof Error &&
      (error.name === "TimeoutError" || error.name === "AbortError");
    return NextResponse.json(
      { error: timedOut ? "decision API timeout" : "decision API unavailable" },
      { status: timedOut ? 504 : 502 },
    );
  }
}
