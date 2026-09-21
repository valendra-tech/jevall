/**
 * Minimal validation for the decision payloads the demo accepts. The upstream
 * gateway validates the full contract; this only rejects obvious garbage.
 */
export function isValidDecisionPayload(value: unknown): boolean {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  if (typeof candidate.model !== "string" || candidate.model.length === 0) {
    return false;
  }
  if (!Array.isArray(candidate.questions) || candidate.questions.length === 0) {
    return false;
  }
  return isState(candidate.state);
}

function isState(state: unknown): boolean {
  if (typeof state === "string") {
    return state.length > 0;
  }
  if (!Array.isArray(state) || state.length === 0) {
    return false;
  }
  return state.every(isStatePart);
}

function isStatePart(part: unknown): boolean {
  if (typeof part !== "object" || part === null) {
    return false;
  }
  const candidate = part as Record<string, unknown>;
  if (candidate.type === "text") {
    return typeof candidate.text === "string" && candidate.text.length > 0;
  }
  if (candidate.type === "image" || candidate.type === "video") {
    return typeof candidate.uri === "string" && candidate.uri.length > 0;
  }
  return false;
}
