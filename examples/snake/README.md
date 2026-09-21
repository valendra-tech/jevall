# Jevall Snake

A browser Snake game whose every movement is a real decision returned by the
Jevall typed-decision API. There is no generated text and no local pathfinding:
the browser keeps the game rules, sends an ASCII description of the board, and
applies the returned action verbatim.

```
game state → decision API → P(up/down/left/right) → selected movement → next state
```

## Requirements

- Node.js 20 or newer
- A reachable decision endpoint (defaults to the public RunPod proxy below)

## Running

```bash
cd examples/snake
npm install
cp .env.example .env.local   # optional, the defaults point at the public endpoint
npm run dev                  # http://localhost:3000
```

Production:

```bash
npm run build
npm run start
```

Checks:

```bash
npm run test       # vitest, pure game/API-adjacent logic
npm run lint       # eslint (next config)
npm run typecheck  # tsc --noEmit
```

## Environment

| Variable                   | Default                                                          | Purpose                          |
| -------------------------- | ---------------------------------------------------------------- | -------------------------------- |
| `DECISIONS_API_URL`        | `https://ba5bu9e1oib70a-8000.proxy.runpod.net/v1/decisions`       | Upstream decision endpoint       |
| `DECISIONS_API_TIMEOUT_MS` | `8000`                                                           | Upstream timeout in milliseconds |

Both are read only by the proxy route, so the URL never ships to the browser
and there is a single place to change it.

## Why a proxy

The upstream endpoint answers `POST` but rejects browser preflights
(`OPTIONS` returns `405` with no `Access-Control-Allow-*` headers), so a direct
`fetch` from the page cannot work. `app/api/decisions/route.ts` is a thin proxy:
it validates the payload, forwards it with a timeout, and maps failures to
`502` (unreachable) or `504` (timeout) with a small JSON error.

## Architecture

| Path                              | Responsibility                                              |
| --------------------------------- | ----------------------------------------------------------- |
| `app/page.tsx`                    | Layout: board, decision panel, metrics, history, debug       |
| `app/api/decisions/route.ts`      | Proxy with timeout and error mapping                         |
| `hooks/useSnakeGame.ts`           | Game loop, modes, speed, history, single-flight decisions    |
| `lib/game.ts`                     | Pure rules: collisions, growth, food spawn, `step()`         |
| `lib/stateText.ts`                | ASCII board + prompt sent to the model                       |
| `lib/options.ts`                  | Dynamic options (never the 180° reversal)                    |
| `lib/api.ts`                      | Client for the proxy, latency and diagnostics extraction     |
| `lib/singleFlight.ts`             | Serialises calls so two decisions can never overlap          |
| `lib/stats.ts`, `lib/export.ts`   | Metrics and run export                                       |
| `components/*`                    | Board, decision bars, metrics, history, debug, controls      |

## Game loop

1. Build the state text from the current board.
2. Build the options for the current direction.
3. `POST /api/decisions` with one `choice` question (`move`).
4. Read `decisions[0].selected` and the probability map.
5. Apply exactly that direction with `step()`; collisions are not corrected.
6. Record the turn, update metrics, repeat.

Only one request is ever in flight: the loop awaits each decision before
building the next state, and every call goes through `createSingleFlight`, which
is unit tested. While waiting, the UI shows `Evaluating…`.

Speed is a minimum delay between moves: `Slow` 800 ms, `Normal` 400 ms, `Fast`
0 ms (the next move starts as soon as the API answers, whatever that takes).
The delay is measured from the previous move, so real latency is never hidden.

## Modes

- **AI** (default): the model decides every movement; probabilities, latency,
  history and export are collected.
- **Human**: arrow keys or WASD. Decision statistics are not collected.

## State sent to the model

Generated every turn from the live board; no future information is included.
The default is the ASCII board with relative actions
(`turn_left` / `straight` / `turn_right`). The `Send board as image` toggle
replaces the ASCII grid with a PNG of the board (drawn with an offscreen canvas,
sent as a `data:` URI) and switches the actions to absolute directions, because
that is the combination that measured best (see *Known model behaviour*).

The image costs about 20 ms of extra forward time (67 ms vs 47 ms p50 total on
the public endpoint).

```
SNAKE GAME

Board size: 12x12
Coordinates: x increases left-to-right, y increases top-to-bottom.

You control the snake in the game below.

Your priorities, in order, are:
1. Avoid immediate death by hitting the wall.
2. Avoid hitting the snake body.
3. Move toward the food when safe.
4. Preserve future movement space.
5. Survive for as long as possible.

Inspect the board and choose the best next movement.
Do not assume any information not represented in the state.

Current direction: RIGHT

Legend:
. = empty
H = snake head
S = snake body
F = food

Board:

............
............
.......F....
............
....SSSH....
...

Snake head: (7,4)
Snake body: [(6,4),(5,4),(4,4)]
Food: (7,2)

Choose the best next movement.
```

## Known model behaviour

The demo shows a real failure mode of `Qwen/Qwen3.5-4B`: **it trades survival for
food**. When the food lies in the direction of the wall it walks into the wall;
when the food is elsewhere it avoids the wall. Verified with direct API probes on
a fixed critical position (head at the right edge, wall ahead, body behind):
five food layouts x three runs per variant.

| Board representation | Actions | Safe picks |
| -------------------- | ------- | ---------- |
| ASCII board | relative (`turn_left`/`straight`/`turn_right`) | **9/15** |
| ASCII board | absolute (`up`/`down`/`right`) | 0/15 |
| Board image | relative | 0/15 |
| Board image | absolute | **9/15** |

Each combination is deterministic per position (ten runs give the same answer),
so the framing decides which prior wins. The two winning combinations fail only
on the layouts where the food sits behind the wall. Because of that interaction
the demo couples them: text mode uses relative actions, image mode uses absolute
actions. The mixed combinations are not reachable from the UI.

Live runs, same model and endpoint:

- Text mode: six moves straight into the right wall (`WALL COLLISION`).
- Image mode: fourteen moves, turning left along the wall, then a wall collision.

What does not help (all measured): row/column indices, a bordered board, a
"check each option" instruction, a shorter preamble, removing the current
direction line, explicit edge rules ("a move outside the grid ends the game",
"cell (11,6) is the last of row 6"), and board sizes from 6x6 to 12x12. The
prompt already states the rule; the model does not apply it when the food pulls
the other way.

The reference project [`siroccomask/snake-jev`](https://github.com/siroccomask/snake-jev)
avoids this by not asking the model to read the board: the game computes numeric
sensors (distance to wall/body, food offset) and asks nine yes/no questions
(`turn_left`/`straight`/`turn_right` x `wall`/`body`/`food`), then composes the
action in code among the answers it judged collision-free. That is more reliable
but it precomputes perception and decides in code, which this demo deliberately
does not do.

Nothing in the demo corrects or filters the model's choice either way.


## API contract

Request:

```json
{
  "model": "Qwen/Qwen3.5-4B",
  "state": "...",
  "questions": [
    {
      "id": "move",
      "type": "choice",
      "prompt": "What should the snake do next to survive and move toward the food?",
      "options": [
        { "id": "up", "text": "Move up" },
        { "id": "down", "text": "Move down" },
        { "id": "right", "text": "Move right" }
      ]
    }
  ]
}
```

Response (abridged):

```json
{
  "id": "dec_...",
  "model": "Qwen/Qwen3.5-4B",
  "decisions": [
    {
      "id": "move",
      "type": "choice",
      "selected": "right",
      "probabilities": { "up": 0.1, "down": 0.04, "right": 0.86 }
    }
  ],
  "usage": { "latency_ms": 75 },
  "diagnostics": { "queue_ms": 8, "forward_ms": 45, "scoring_ms": 20 }
}
```

The displayed probabilities are exactly the returned values. They are raw model
outputs, not calibrated confidences, and the UI labels them as an average
selected probability.

## Why the options are dynamic

Snake forbids a 180° reversal. In relative mode the reversal is not even
representable (`turn_left` / `straight` / `turn_right`); in absolute mode the
reverse direction is filtered out. Every other option stays on the table,
including ones that would hit a wall or the body: detecting danger is the
model's job, not the browser's. If the model picks a fatal move, the snake dies
— that is the point of the demo.

## Failure handling

If the proxy cannot reach the endpoint, the game pauses and shows
`Decision API unavailable` with `Retry` and `Restart`. No local heuristic picks
a move and there is no infinite spinner. An invalid response (a `selected`
value that was not offered) is treated the same way.

## Exporting a run

`Export run` downloads a JSON file with the whole game: model, board size,
score, moves, survived moves, final cause, latency and probability aggregates,
plus every turn with the exact state sent, the options, the raw response, the
selected movement, latency, outcome and the board before/after the move.

```json
{
  "model": "Qwen/Qwen3.5-4B",
  "score": 5,
  "moves": 67,
  "history": [
    {
      "turn": 1,
      "stateText": "...",
      "options": [{ "id": "up", "text": "Move up" }],
      "rawResponse": { "decisions": [{ "selected": "right" }] },
      "selected": "right",
      "selectedProbability": 0.862,
      "latencyMs": 71,
      "outcome": "moved",
      "boardBefore": "...",
      "boardAfter": "..."
    }
  ]
}
```

## Deliberate non-goals

- No BFS, A*, shortest path or any local search that could replace the model.
- No interception or correction of dangerous movements.
- No claim that probabilities are calibrated.
