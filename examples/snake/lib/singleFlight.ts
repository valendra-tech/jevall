/**
 * Serialise async calls so a caller can never run two of them at once.
 * The game loop relies on this to guarantee a single in-flight decision.
 */
export function createSingleFlight<Args extends unknown[], Result>(
  fn: (...args: Args) => Promise<Result>,
): (...args: Args) => Promise<Result> {
  let tail: Promise<unknown> = Promise.resolve();

  return (...args: Args): Promise<Result> => {
    const result = tail.then(() => fn(...args));
    tail = result.catch(() => undefined);
    return result;
  };
}
