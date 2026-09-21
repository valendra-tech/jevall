import { createSingleFlight } from "@/lib/singleFlight";

describe("createSingleFlight", () => {
  it("never runs two calls at the same time", async () => {
    let active = 0;
    let maxActive = 0;
    const order: number[] = [];

    const run = createSingleFlight(async (value: number) => {
      active += 1;
      maxActive = Math.max(maxActive, active);
      await new Promise((resolve) => setTimeout(resolve, 5));
      active -= 1;
      order.push(value);
      return value * 2;
    });

    const results = await Promise.all([run(1), run(2), run(3)]);

    expect(maxActive).toBe(1);
    expect(order).toEqual([1, 2, 3]);
    expect(results).toEqual([2, 4, 6]);
  });

  it("keeps serving calls after a failure", async () => {
    let calls = 0;
    const run = createSingleFlight(async (fail: boolean) => {
      calls += 1;
      if (fail) {
        throw new Error("boom");
      }
      return "ok";
    });

    await expect(run(true)).rejects.toThrow("boom");
    await expect(run(false)).resolves.toBe("ok");
    expect(calls).toBe(2);
  });
});
