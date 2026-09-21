import {
  buildAbsoluteOptions,
  buildRelativeOptions,
  isOffered,
  MOVE_PROMPT,
} from "@/lib/options";

describe("buildRelativeOptions", () => {
  it("offers the three relative actions", () => {
    const options = buildRelativeOptions();

    expect(options.map((option) => option.id)).toEqual([
      "turn_left",
      "straight",
      "turn_right",
    ]);
    expect(options.map((option) => option.text)).toEqual([
      "Turn left",
      "Keep going straight",
      "Turn right",
    ]);
  });

  it("cannot offer the reversal because it is not an action", () => {
    const options = buildRelativeOptions();

    expect(isOffered(options, "turn_left")).toBe(true);
    expect(isOffered(options, "behind")).toBe(false);
    expect(isOffered(options, "up")).toBe(false);
  });
});

describe("buildAbsoluteOptions", () => {
  it("offers every direction except the reversal", () => {
    expect(buildAbsoluteOptions("right").map((option) => option.id)).toEqual([
      "up",
      "down",
      "right",
    ]);
    expect(buildAbsoluteOptions("up").map((option) => option.id)).toEqual([
      "up",
      "left",
      "right",
    ]);
  });
});

describe("MOVE_PROMPT", () => {
  it("asks for a movement without requesting reasoning", () => {
    expect(MOVE_PROMPT).toContain("What should the snake do next");
    expect(MOVE_PROMPT.toLowerCase()).not.toContain("explain");
    expect(MOVE_PROMPT.toLowerCase()).not.toContain("reason");
  });
});
