import { isValidDecisionPayload } from "@/lib/payload";

const question = {
  id: "move",
  type: "choice",
  prompt: "p",
  options: [{ id: "up", text: "Move up" }],
};

function payload(state: unknown) {
  return { model: "Qwen/Qwen3.5-4B", state, questions: [question] };
}

describe("isValidDecisionPayload", () => {
  it("accepts a text state", () => {
    expect(isValidDecisionPayload(payload("SNAKE GAME"))).toBe(true);
  });

  it("accepts a text plus image state", () => {
    const state = [
      { type: "text", text: "SNAKE GAME" },
      { type: "image", uri: "data:image/png;base64,AAAA" },
    ];

    expect(isValidDecisionPayload(payload(state))).toBe(true);
  });

  it("rejects an empty or malformed state", () => {
    expect(isValidDecisionPayload(payload(""))).toBe(false);
    expect(isValidDecisionPayload(payload([]))).toBe(false);
    expect(isValidDecisionPayload(payload([{ type: "text" }]))).toBe(false);
    expect(isValidDecisionPayload(payload([{ type: "image", uri: "" }]))).toBe(
      false,
    );
    expect(isValidDecisionPayload(payload([{ type: "audio", uri: "x" }]))).toBe(
      false,
    );
  });

  it("rejects missing models or questions", () => {
    expect(isValidDecisionPayload({ state: "x", questions: [question] })).toBe(
      false,
    );
    expect(isValidDecisionPayload({ model: "m", state: "x" })).toBe(false);
    expect(isValidDecisionPayload(payload("x"))).toBe(true);
    expect(
      isValidDecisionPayload({ model: "m", state: "x", questions: [] }),
    ).toBe(false);
  });
});
