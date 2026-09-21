import { buildStateParts, statePartsLabel } from "@/lib/boardImage";
import { createGame } from "@/lib/game";

const IMAGE = "data:image/png;base64,AAAA";

describe("buildStateParts", () => {
  it("returns plain text with the ASCII board when vision is off", () => {
    const game = createGame(12, () => 0);
    const state = buildStateParts(game, { vision: false, imageDataUri: null });

    expect(typeof state).toBe("string");
    expect(state as string).toContain("Board:");
  });

  it("returns text plus image when vision is on", () => {
    const game = createGame(12, () => 0);
    const state = buildStateParts(game, {
      vision: true,
      imageDataUri: IMAGE,
    });

    expect(Array.isArray(state)).toBe(true);
    const parts = state as Array<{ type: string; text?: string; uri?: string }>;
    expect(parts).toHaveLength(2);
    expect(parts[0].type).toBe("text");
    expect(parts[0].text).toContain("attached as an image");
    expect(parts[0].text).not.toContain("Board:\n\n....");
    expect(parts[1]).toEqual({ type: "image", uri: IMAGE });
  });

  it("falls back to text when the image cannot be rendered", () => {
    const game = createGame(12, () => 0);
    const state = buildStateParts(game, { vision: true, imageDataUri: null });

    expect(typeof state).toBe("string");
  });
});

describe("statePartsLabel", () => {
  it("omits the board for the log when vision is on", () => {
    const game = createGame(12, () => 0);
    const label = statePartsLabel(game, { vision: true });

    expect(label).toContain("attached as an image");
    expect(label).not.toContain("Board:");
  });
});
