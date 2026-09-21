import { buildOptions, isOffered, MOVE_PROMPT } from "@/lib/options";

describe("buildOptions", () => {
  it("offers the current direction and both turns, never the reversal", () => {
    const options = buildOptions({ direction: "right" });

    expect(options.map((option) => option.id)).toEqual(["up", "down", "right"]);
    expect(options.map((option) => option.text)).toEqual([
      "Move up",
      "Move down",
      "Move right",
    ]);
    expect(isOffered(options, "left")).toBe(false);
  });

  it("keeps options that would collide", () => {
    const options = buildOptions({ direction: "up" });

    expect(options.map((option) => option.id)).toEqual(["up", "left", "right"]);
  });
});

describe("MOVE_PROMPT", () => {
  it("asks for a movement without requesting reasoning", () => {
    expect(MOVE_PROMPT).toContain("What should the snake do next");
    expect(MOVE_PROMPT.toLowerCase()).not.toContain("explain");
    expect(MOVE_PROMPT.toLowerCase()).not.toContain("reason");
  });
});
