# Prompts and harness implementation

This document covers the prompts the models receive and how the harness runs, limits, prices, and
scores each run. The study design is in `docs/TEST_PLAN.md`. Column definitions for the result
files are in `results/DATA_DICTIONARY.md`.

## Conditions and endpoints

Each task runs under two conditions, one per gateway: Connect AI Gateway and the open-source MCP
gateway. A condition names an entry in the `endpoints:` block of
`config/models.yaml`, and that entry says which URL to use and how to authenticate.

| Condition | Endpoint key | Surface | Auth |
|---|---|---|---|
| `connect_ai_gateway` | `connect_ai_gateway` (R1, R2), `connect_ai_gateway_write` (A1) | Connect AI Gateway's MCP endpoint. Read tools plus `search_context`; the A1 endpoint adds `execute_insert`. URL from `CONNECT_AI_MCP_URL` or `CONNECT_AI_MCP_WRITE_URL`. | `basic`: HTTP Basic with `CDATA_EMAIL` and `CDATA_ACCESS_TOKEN` |
| `open_source_gateway` | `open_source_gateway` (all tasks) | The open-source MCP gateway at `GATEWAY_URL` + `/mcp`, fronting the warehouse, CRM and ITSM MCP servers (20 tools). The same endpoint serves read and write tasks. | `bearer`: header `Authorization: Bearer <GATEWAY_KEY>` |

The `open_source_gateway` entry also sets `require_instructions` to two phrases: "Account health score rules"
(our context) and "customer support incidents and the companies they belong to" (the ITSM server's
own instructions). The
harness checks that both appear in the open-source gateway's server instructions (see below).

The `connect_ai_gateway` runs come from the previous study's with-context condition. A condition
without an `endpoint:` key uses the
endpoint with its own name.

## End-to-end flow

`run_matrix.py` does the following, in order:

1. Loads `config/models.yaml`, then each task's prompt, golden, and optional system prompt. A
   missing file stops the run.
2. Resolves reasoning levels. By default each model runs at its configured `effort` (a value or a
   list). `--effort X` runs every selected model at `X` and stops if any model doesn't support it.
3. Runs the price checks (see [Cost](#cost-and-price-checks)).
4. Builds the plan. It skips a condition that is disabled in the config or whose endpoint is
   missing an environment variable (`mcp_client.missing_env`).
5. Runs the preflight checks (next section). `--dry-run` stops here.
6. Loops models, then reasoning levels, then tasks. Within a task it interleaves conditions round
   robin: run 1 of every condition, then run 2, and so on. Network and provider drift during a
   session then falls on both conditions alike.
7. For each run: resets `REVIEW_QUEUE` (A1 only), opens a fresh MCP session, builds the system
   prompt, runs the provider's tool loop, reads back the result (A1 only), scores it, computes
   cost, and writes the run's JSON. It then sleeps 3 seconds before the next run.
8. Resets `REVIEW_QUEUE` after the last run so the table is left empty.

Useful flags: `--task`, `--model` (both repeatable), `--runs` (override runs per condition),
`--out-dir` (write run JSON somewhere other than `results/matrix/`), `--skip-price-check`.

## Preflight checks

Nothing is spent on models until these pass:

- **Pinned model ids.** An id ending in `latest` stops the run (`pricing.unpinned`).
- **Live prices.** Together and xAI prices must match `models.yaml` (see below).
- **Verifier.** If an A1 condition is in the plan, the verifier counts `REVIEW_QUEUE`, empties it,
  confirms it is empty, and snapshots the row counts of `DIM_ACCOUNT` and `TELEMETRY_EVENTS`. That
  snapshot is the first baseline for off-target write detection.
- **Endpoints.** The harness connects to every endpoint in the plan, sends `initialize`, checks
  `require_instructions`, and lists tools. It prints one line per endpoint, for example:

  ```
  OK  connect_ai_gateway: 7 tools, 0 chars of server instructions
  OK  open_source_gateway: 20 tools, 8632 chars of server instructions
  OK  connect_ai_gateway_write: 8 tools, 0 chars of server instructions
  ```

  Any failure stops the run before the first model call.

## Server instructions and the system prompt

An MCP server can return `instructions` in its `initialize` response. The harness appends them to
the system prompt, as MCP clients such as Claude Desktop and Claude Code do:

```
<task system prompt>

# MCP server instructions

<instructions from initialize>
```

If the response has no instructions, the system prompt is unchanged. Connect AI Gateway's endpoints
return none, so the `connect_ai_gateway` system prompt is exactly the task's system prompt. The
open-source gateway returns the merged instructions of its three servers: the warehouse and CRM context from
`setup/open_source_gateway/context/`, plus the ITSM server's own instructions. That is about 8,600
characters.

The `require_instructions` guard protects against an open-source gateway that has lost its context (for example
after a restart without the instructions loaded). If the instructions lack any required phrase, the
preflight fails. The ITSM phrase matters because the open-source gateway passes that text through from the
upstream server, so it can be missing even when our own context is loaded. The same check runs
again at the start of every
run; a failure there ends that run as an error, so it is retried on the next launch rather than
scored. Each run records the instruction length in `server_instructions_chars`.

## System prompts

R1 and R2 use the shared system prompt `SYSTEM` in `core/runners.py`:

> You are an enterprise data assistant. Use the available tools to answer the user's question by
> querying the data. Return your FINAL answer as a single markdown table with one row per account
> and clearly named columns. Do not invent data; only report what the tools return.

A1 uses `config/system_a1.txt` (set by `system_file` in `models.yaml`):

> You are an enterprise data assistant. Use the available tools to complete the user's request,
> including any changes to data it asks for. Do not invent data; only act on and report what the
> tools return. When you have finished, summarize what you did as a single markdown table with one
> row per account and clearly named columns.

The shared prompt asks the model to answer "by querying the data", which conflicts with a request
to change data. Models that follow it literally report what to queue without writing it, so A1 has
its own system prompt. Each run records which one it used in `system_prompt`.

Neither system prompt mentions `search_context`, the context entries, or any tool. In
`connect_ai_gateway` the model finds `search_context` in its tool list like any other tool. In
`open_source_gateway` the context arrives as server instructions appended to the system prompt.

## Prompt: R1 (read, portfolio health)

`config/prompt.txt`:

> Identify our High-priority accounts in poor health, worst first, considering SLA tier, recent
> product usage, contract renewal timing, and open urgent support tickets. For each, show account
> name, SLA level, health score, health status, and urgent ticket count. For any account with
> CRITICAL status, confirm its review eligibility and state the reason. Return up to 50 rows.

Design notes:

- It names the four signal types (SLA, usage, renewal, tickets) without revealing weights or the
  formula. Both conditions have the health score rules: as a `search_context` entry in
  `connect_ai_gateway`, and in the open-source gateway's instructions in `open_source_gateway`.
- It asks for eligibility and reason only for CRITICAL accounts. This matches the golden: the 50
  worst-health rows, with eligibility and reason populated only where `Health_Status = 'CRITICAL'`.
- "Worst first" sets an ordering requirement, checked separately from set membership.
- "Return up to 50 rows" caps output without revealing the population size.

## Prompt: R2 (read, composition)

`config/prompt_r2.txt` (quoted verbatim):

> Identify our High-priority accounts that are in poor health (AT_RISK or CRITICAL) and showing
> declining product usage — where recent activity is meaningfully down compared to the prior
> period. For each, show account name, SLA level, health status, health score, and the usage trend
> (recent vs. prior period activity, and whether usage is declining, stable, or growing). Order
> worst-first by health score. Return up to 50 rows.

Design notes:

- It uses the same High-priority population as R1. The harder part is composing health with
  usage, not a different set of accounts.
- It gives no window size, formula, or table names. The usage trend definition (windows and
  thresholds) is part of the context in both conditions.
- It does not repeat R1's eligibility sub-task. A1 tests eligibility a different way.

## Prompt: A1 (write, queue reviews)

`config/prompt_a1.txt`:

> Queue a manual review for every High-priority account that is CRITICAL and eligible for review,
> recording the reason for each. Do not queue any account that isn't both CRITICAL and eligible,
> and don't queue the same account more than once.

Design notes:

- The prompt is identical in both conditions.
- "High-priority" keeps the target set at the 21 accounts in the golden. Across all 1,200 accounts,
  44 are CRITICAL and eligible. Without the filter, a model doing what it was asked would write 23
  rows that score as unauthorized.
- It states the "no duplicates" and "only CRITICAL and eligible" constraints explicitly, because
  both are scored on the table's end state.
- The write tools differ. Connect AI Gateway's `execute_insert` takes `parameters` as an object.
  The open-source gateway's warehouse-server `execute_insert` and `execute_update` take `parameters` as a JSON
  string, because the warehouse's generic MCP tools reject object-typed arguments.

## Provider runners

`core/runners.py` runs every provider through the same client-side loop: list the MCP tools,
convert them to the provider's function schema, call the model, dispatch each tool call to MCP,
return the results, and repeat until the model stops calling tools or the turn cap is reached.
Token accounting, timing, and the trace are recorded the same way for every provider. Tool
descriptions are truncated to 1,024 characters for every provider.

| Runner | Used for | API | Notes |
|---|---|---|---|
| `run_anthropic` | Claude models | Messages API, streamed | Prompt caching on the system prompt and the last tool definition. Adaptive thinking (`output_config.effort`) when an effort level is set. Manual thinking (`budget_tokens`) for models with `thinking_budget` (Haiku 4.5), switching to adaptive if the model rejects manual thinking. |
| `run_openai` | GPT models | Responses API | Conversation state carried by `previous_response_id`. `reasoning.effort` when an effort level is set. |
| `run_gemini` | Gemini models | `google-genai` `generate_content` | Tries to create a context cache (10-minute TTL) for the system prompt and tools, and falls back to sending them inline. Automatic function calling is disabled. `thinking_level` when an effort level is set. |
| `run_grok` | Grok models | xAI chat completions (OpenAI-compatible) | `reasoning_effort` when an effort level is set. |
| `run_openai_compat` | Together and Mistral models | OpenAI-compatible chat completions | `reasoning_effort` when an effort level is set. Streams when the model sets `stream: true`. Splits Mistral's list-of-chunks content into answer text and thinking. |

The `effort` value `default` sends no reasoning setting, so the provider's own default applies.

## Limits

Both conditions run under the same harness limits.

### Output cap

| Provider | Cap per model call |
|---|---|
| Anthropic | 64,000 tokens (`ANTHROPIC_MAX_TOKENS`). Requests stream because the SDK refuses non-streaming requests whose `max_tokens` could run past 10 minutes. |
| Together, Mistral (`openai_compat`) | 65,536 tokens (`OPENAI_COMPAT_MAX_TOKENS`), unless a model sets `max_tokens` in `models.yaml` |
| OpenAI, Gemini, Grok | Not set. The provider's default applies. |

The cap is high because runs in `open_source_gateway` combine results from three systems in the
model's own reasoning, which can take tens of thousands of tokens in one turn. Every Together and
Mistral endpoint in the roster accepts 65,536.

The OpenAI-compatible runner sends `max_tokens` explicitly. If the endpoint rejects the request,
it retries without it (see [Temperature](#temperature)). Each run records `max_tokens_requested`
and `max_tokens_applied`.

### Tool-result truncation

Each tool result is flattened to text and truncated before the model sees it:

- 8,000 characters for every tool (`TOOL_RESULT_CHARS`),
- 32,000 characters for any tool whose name ends in `search_context` (`SEARCH_CONTEXT_CHARS`),
  because it returns whole context documents.

A truncated result ends in ` ...[truncated]`. The 8,000 limit is unchanged from the previous study
so the reused Connect AI Gateway runs stay valid. In practice it means the model pages through large
results in both conditions.

### Turn cap

Every condition sets `turn_cap: 40`. A turn is one model call plus the tool calls it requests. A
run that is still calling tools at turn 40 stops with `hit_turn_cap = true`. The global fallback,
used only when a condition omits `turn_cap`, is 12.

### MCP call deadline

Each MCP call has a 30-minute deadline (`CALL_DEADLINE_S = 1800`), covering the full response. A
call past it raises `MCPTimeout`. The run ends as a scored failure with `stop_reason = tool_timeout`,
like hitting the turn cap, and the call in flight is saved in `pending_call`.

## Temperature

`models.yaml` sets `temperature: 0`. Each runner applies it where the provider allows it and
records what took effect in `temperature_applied`:

- **Anthropic:** with thinking on (adaptive or manual), temperature is not sent and
  `temperature_applied` is `provider_default`. Without thinking, the runner sends 0 and drops it if
  the API rejects temperature.
- **OpenAI:** the runner sends 0. If the call fails, it retries without temperature
  (`provider_default`). If that fails too, it retries without the reasoning setting.
- **Gemini:** the runner always sends 0.
- **Grok:** the runner sends 0, then retries without it on failure.
- **OpenAI-compatible:** the runner tries, in order: temperature and `max_tokens`; `max_tokens`
  only; temperature only; neither. The first accepted combination is recorded in
  `temperature_applied` and `max_tokens_applied`.

## Retries and failure handling

- **Model API calls** (`runners._retry`): up to 6 attempts on transient errors (HTTP 429, 500, 502,
  503, 529, or messages such as "overloaded", "rate limit", "timeout", "unavailable"). Back-off is
  exponential from 3 seconds, capped at 60, plus up to 1 second of jitter. The run records
  `model_retries` and `model_retry_backoff_s`. Back-off time is inside `model_time_s`.
- **MCP requests** (`MCPClient._post`): up to 5 attempts on connection errors and socket timeouts,
  backing off from 3 seconds to a cap of 30. Recorded as `mcp_retries` and `mcp_retry_backoff_s`.
- **MCP `initialize`** at the start of a run: up to 3 attempts, 5 seconds apart. The client always
  sends `notifications/initialized` afterwards, as the MCP handshake specifies.
- **Provider refusals:** an error matching "inappropriate content" or "DataInspectionFailed" is a
  provider's content moderation rejecting the conversation. It is recorded as
  `provider_refusal = true` and scored as a failed run, not retried.
- **Post-run verification:** if reading `REVIEW_QUEUE` back fails after a successful model run, the
  run keeps its tokens, cost, and trace, but is marked with an error so the next launch retries it.
- **Scoring errors:** a run that can't be scored is marked `ScoringError`; the matrix continues.

## Resumability and run files

Each run writes `results/matrix/<tag>.json` as soon as it finishes. On relaunch, a run whose JSON
exists without an `error` is skipped, and a run with an error is retried. A crash, sleep, or rate
limit only needs the same command again.

Every task's run files are named `{model}@{effort}__{task}__{condition}__run{n}`. The tag replaces
`/` in model ids with `--`.

## A1 reset and verification

`core/verifier.py` resets and grades A1 runs over CData Connect AI's REST query API
(`CDATA_QUERY_API`, default `https://cloud.cdata.com/api/query`) with the operator's own
credentials. It never uses the endpoint under test, because grading a write with the same access
the model had would be circular. MCP's `execute_insert` can't delete rows; the REST API can.

For every A1 run, in both conditions:

1. **Reset.** `DELETE FROM` the queue table (`REVIEW_QUEUE_TABLE`), then confirm the count is zero.
   If the table isn't empty, the run ends as an error and is retried on the next launch.
2. **Run** the model.
3. **Read back** `ACCOUNT_NAME, REASON` from the queue table. These rows (`queue_rows`) are the
   graded artifact.
4. **Snapshot** the row counts of `DIM_ACCOUNT` and `TELEMETRY_EVENTS` (in the `WH_CONN`
   connection) and compare them with the previous snapshot. Any change is recorded in
   `source_integrity` and printed as an off-target write. The new counts become the baseline for the
   next run, so one dirty run doesn't flag every later run.

A row count is enough because off-target damage can only add rows: Connect AI Gateway's
`execute_insert` accepts only INSERT, and the open-source gateway's write tools run as a warehouse role that can write only
`REVIEW_QUEUE`. The verifier reads the same physical table the open-source gateway's warehouse server writes
to (`BENCHMARK_WH.WH_DATA.REVIEW_QUEUE`).

Verifier queries retry up to 5 times on connection errors and HTTP 502, 503, or 504. A statement
that fails inside an HTTP 200 response raises an error rather than passing silently.

## Cost and price checks

Cost is computed per run from the token counts and the prices in `models.yaml`:

```
cost_usd = (uncached_input × input_price
          + cached_input × cached_price
          + output × output_price) / 1,000,000
```

- `cached_price` is `price_cached_input_per_mtok`, or 10% of the input price if it isn't set.
  Together and Mistral set it equal to the input price because they don't bill cached tokens
  separately.
- For Gemini, `output` plus `reasoning` is billed, because Gemini reports thinking tokens separately
  from output. For OpenAI and xAI, reasoning tokens are already inside `output`. For Anthropic,
  thinking tokens are billed inside `output_tokens`.
- For Anthropic, cache-creation tokens count as uncached input and are priced at the base input
  rate. Cache reads are priced at the cached rate.
- Runs that end in an error have `cost_usd = null`.
- Each run stores the prices it used in `price_per_mtok` and whether they were verified live in
  `price_verified_live`.

Before a matrix starts, `core/pricing.py` fetches live prices from Together (`/v1/models`, input and
output) and xAI (`/v1/language-models`, input, cached and output, standard tier). A difference of
more than 0.5% from `models.yaml`, or a model the provider doesn't list, stops the run unless you
pass `--skip-price-check`. Anthropic, OpenAI, Google and Mistral publish no machine-readable prices,
so their entries are checked by hand.

## Scoring

- **Goldens.** `core/golden.py` and `make_goldens.py` derive the goldens offline from the frozen
  source CSVs: R1 (50 rows), R2 (44), A1 (21). `make_goldens.py` refuses to write R2 or A1 unless it
  first reproduces R1's frozen golden exactly.
- **`core/scorer.py`:**
  - `score()` (R1): set F1 50%, health status 25%, CRITICAL eligibility (flag and reason) 25%. Set
    F1 tolerates accounts tied at the cut-off health score.
  - `score_r2()`: set F1 50%, health status 25%, usage trend label 25%. No tie tolerance. Session
    counts are checked as a diagnostic only.
  - `score_action()` (A1): graded on `REVIEW_QUEUE`'s end state, never the model's prose. Action F1
    70% plus reason accuracy 30%. Unauthorized rows, duplicates, and the wrong set are reported
    separately. `classify_action_outcome()` labels each run `clean`, `unsafe`, `sloppy`,
    `wrong_reasons`, `wrong_set`, or `no_writes`.
  - `write_target_score()`: scans every string argument in the trace for `INSERT INTO`, `UPDATE`,
    `DELETE FROM`, and `MERGE INTO` statements aimed at any table other than `REVIEW_QUEUE`, and
    combines that with the row-count delta from `source_integrity`.
- **Rescoring.** `aggregate.py` and `export_raw.py` re-derive every score from each run's saved
  artifact (`final_answer` or `queue_rows`) through `core/tasks.py`. A scorer fix applies to all
  completed runs without re-running models.
- **Normalized time.** `core/timing.py` prices each tool call at that tool's median latency across
  all runs, and model time with a per-model fit to turns and output tokens, with retry back-off
  removed. Two runs that do the same work get the same value regardless of network speed.

## Running it

```bash
python3 make_goldens.py                       # regenerate and self-check goldens
python3 run_matrix.py --dry-run               # preflight checks and the plan, no model calls
python3 run_matrix.py                         # completed runs are skipped
python3 aggregate.py --effort configured && python3 export_raw.py
```

For a cheap end-to-end smoke test kept out of the real matrix:

```bash
python3 run_matrix.py --task a1 --model grok-4.3 --runs 1 --out-dir results/smoke
```
