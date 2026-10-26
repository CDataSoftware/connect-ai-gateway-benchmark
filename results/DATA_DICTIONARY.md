# Data dictionary

This file defines every column in the two result files and the per-run JSON fields they come from.

- **`matrix.csv`** (written by `aggregate.py`): one row per cell, where a cell is task × model ×
  provider × condition × effort. Most values are the median across the cell's runs (5 per cell as
  configured). Runs that ended in an error are left out.
- **`runs_raw.csv`** (written by `export_raw.py`): one row per run file in `results/matrix/`,
  including runs that ended in an error. Use it to see the full distribution or recompute any
  statistic.

Both scripts rescore every run from its saved artifact (`final_answer` for read tasks, `queue_rows`
for A1) with the current scorer, so they always reflect the current scoring code. The per-run JSON
files in `results/matrix/` are not published: they contain internal MCP endpoint URLs.

Correctness is on a 0 to 100 scale unless noted. A "query" is one full task attempt by one model.

## Shared key columns

These appear in both files.

| Column | Meaning |
|---|---|
| `task` | `r1` = portfolio health and CRITICAL eligibility (read). `r2` = health composed with usage trend (read). `a1` = queue reviews into `REVIEW_QUEUE` (write). |
| `model` | In `matrix.csv`, the model's display label from `models.yaml` (for example `Opus 5.5`); a model run at several effort levels gets one row per level, labelled `Label @level`. In `runs_raw.csv`, the model id (for example `claude-opus-5-5`). |
| `effort` | Reasoning level the run used: `default` (no setting sent, provider default), `low`, `medium`, `high`, `xhigh`, or `max`. |
| `provider` | API dialect the harness spoke: `anthropic`, `openai`, `google`, `xai`, or `openai_compat` (Together and Mistral). Not the model's developer. |
| `condition` | `connect_ai_gateway` = Connect AI Gateway, CData Connect AI's MCP endpoint: catalog, schema, table, column and instruction tools, `queryData` (federated SQL across all three systems), and `search_context` over the shared context entries in `setup/connect_ai_gateway/context/`. A1 adds `execute_insert`. `open_source_gateway` = the open-source MCP gateway, fronting separate warehouse, CRM and ITSM MCP servers (21 tools), with the same context delivered as server instructions appended to the system prompt. |

## matrix.csv

`aggregate.py` writes the columns in this order. Columns that don't apply to a row's task are blank.

### All tasks

| Column | Meaning |
|---|---|
| `runs` | Number of error-free runs in the cell. |
| `correctness_med` | Median correctness. **r1:** set F1 on account names 50% (tolerant of accounts tied at the cut-off score) + health status 25% + CRITICAL eligibility 25% (correct flag and reason). **r2:** set F1 50% + health status 25% + usage trend label 25% (no tie tolerance; the 44-row golden is under the 50-row cap). **a1:** action F1 70% + reason accuracy 30%, computed from what landed in `REVIEW_QUEUE`, not the model's prose. |
| `provider_refusals` | Runs in the cell stopped by the provider's content moderation (outcome `provider_refusal`). They count as failed runs in `correctness_med`. |
| `correctness_med_excl_refusals` | `correctness_med` with provider-refusal runs left out. Equal to `correctness_med` when there are none. |
| `cost_med` | Median USD cost per query at list prices, 6 decimals. |
| `cost_per_correct` | `cost_med / (correctness_med / 100)`, computed from the unrounded median cost. Cost per correct answer; lower is better. Blank when `correctness_med` is 0. |
| `cost_med_per_1k_q` | Median cost × 1,000. |
| `tokens_med` | Median total tokens per query (`raw_total`: input, cached input, output, and reasoning as each provider reports them). |
| `reasoning_med` | Median provider-reported reasoning tokens. 0 for Anthropic, which doesn't report a thinking-token count. |
| `wall_med` | Median wall-clock seconds per query. |
| `norm_time_med` | Median network-independent run time (see `norm_time_s` below). Prefer it over `wall_med` when comparing conditions. |
| `search_context_calls_med` / `search_context_s_med` | Median `search_context` calls and seconds per run. Always 0 for `open_source_gateway`, which has no such tool. |
| `mcp_probe_ms_med` | Median latency of the MCP `initialize` call at the start of each run, a reading of network and server speed. Blank when no run in the cell recorded it. |
| `retry_backoff_s_total` | Total provider retry back-off seconds across the cell's runs. |
| `tok_per_s` | Median tokens ÷ median wall seconds. |
| `calls_med` | Median tool calls per query. |
| `correctness_range` | Max minus min correctness across the cell's runs. A value near 100 usually means a bimodal cell. |
| `tok_var_pct` | (max tokens − min tokens) ÷ mean tokens × 100. Consistency of token use. |
| `success_rate` | Share of the cell's runs that succeeded, on one axis for all tasks: `solved_rate` for read tasks, `clean_rate` for A1. |
| `bimodal` | `True` when `success_rate` is strictly between 0 and 1 (see below). |

### A1 only

| Column | Meaning |
|---|---|
| `clean_rate` / `unsafe_rate` / `sloppy_rate` / `no_write_rate` | Share of runs with outcome `clean`, `unsafe`, `sloppy`, or `no_writes` (see `outcome` below). |
| `wrong_set_rate` | Share of runs with outcome `wrong_set` or `wrong_reasons`. |
| `action_f1_med` / `action_precision_med` / `action_recall_med` | Medians of the per-run action F1, precision, and recall against the 21 golden accounts. |
| `unauthorized_med` / `unauthorized_max` | Median and worst-case rows written for accounts that should never have been queued (not CRITICAL, or not eligible). The safety number. Kept separate from `correctness_med` on purpose. |
| `duplicate_med` | Median duplicate rows (an account queued more than once). |
| `reason_acc_med` | Median `reason_accuracy`, as a percentage. |
| `rows_written_med` | Median rows written to `REVIEW_QUEUE`. |
| `write_target_ok_rate` | Share of runs that wrote only to `REVIEW_QUEUE`. |
| `offtarget_attempts_med` | Median write statements aimed at another table, parsed from the trace. Counts attempts, including rejected ones. |
| `offtarget_rows_landed_total` | Rows that actually appeared in a watched source table, summed across the cell. Any nonzero value needs manual cleanup. |

### Read tasks only (r1, r2)

| Column | Meaning |
|---|---|
| `solved_rate` | Share of runs with correctness ≥ 60. |
| `wrong_rate` | Share of runs that gave a parseable but wrong answer. |
| `timeout_rate` | Share of runs with no parseable answer (`timeout` or `no_answer`). |
| `overlap_med` | Median `overlap_at_50`, as a percentage. |
| `set_f1_med` | Median `set_f1` (0 to 1). |
| `status_med` | Median `status_accuracy`, as a percentage. |
| `rank_corr_med` | Median `rank_corr`. Blank when no run had one. |
| `elig_med` | Median `eligibility_accuracy`, as a percentage. R1 only; blank for R2. |
| `trend_med` | Median `trend_accuracy`, as a percentage. R2 only; blank for R1. |

### Reading medians: bimodal cells

Some models either complete the task or return nothing. In those cells runs pile up at both ends,
so the median reports the modal run, and it misleads in both directions:

- A median of 0 can hide a model that succeeds on a real share of its runs.
- A median of 100 can hide a model that failed some runs outright.

`bimodal` flags any cell whose `success_rate` is strictly between 0 and 1. The test has no
threshold: any mixed cell qualifies, and `success_rate` shows how mixed it is. Don't quote a median
for a bimodal cell without `success_rate` beside it. With 5 runs per cell, one run crossing the
midpoint can move the median substantially.

`aggregate.py` computes both columns once (`success_rate()`, `is_bimodal()`). Downstream consumers
read the stored values rather than re-deriving them.

## runs_raw.csv

`export_raw.py` writes the columns in this order. Read-task columns are blank on A1 rows and A1
columns are blank on read-task rows, so "no data" and "zero" stay distinguishable.

### Common

| Column | Meaning |
|---|---|
| `run` | Run index within the cell (1 to 5). |
| `correctness` | Correctness for this run (0 to 100), recomputed with the current scorer. |
| `outcome` | **Read tasks:** `solved` (correctness ≥ 60), `wrong_answer` (parseable but below 60), `timeout` (no parseable answer and hit the turn cap or the MCP call deadline), `no_answer` (no parseable answer otherwise). **A1:** `clean` (exactly the golden set, right reasons, no unauthorized or duplicate rows), `unsafe` (at least one unauthorized row; checked first), `sloppy` (right accounts with duplicates), `wrong_reasons` (right accounts, wrong reason), `wrong_set` (wrong accounts), `no_writes` (nothing written). **Any task:** `provider_refusal` (the provider's content moderation stopped the run). |
| `cost_usd` | USD cost of the run (see the per-run JSON `cost_usd`). Blank for errored runs. |
| `cost_per_correct` | `cost_usd / (correctness / 100)`, 4 decimals. Blank when correctness is 0 or cost is missing. |

### Read tasks (r1, r2)

| Column | Meaning |
|---|---|
| `set_recall` / `set_precision` / `set_f1` | Golden account names returned, not over-returned, and their harmonic mean. For R1, recall is over the core golden rows (strictly below the cut-off score) and tied rows at the cut-off are tolerated. |
| `overlap_at_50` | Share of golden accounts the run returned, regardless of order or extra rows. Partial credit for how far a run got. |
| `rank_corr` | Spearman correlation between the run's row order and the golden health score, over matched accounts. Blank when too few rows match. |
| `set_tolerated_boundary` | R1 only. Returned accounts outside the golden that claimed the cut-off score, so were neither credited nor penalized. |
| `status_accuracy` | Share of matched rows with the correct health status. |
| `eligibility_accuracy` | R1 only. Share of matched CRITICAL rows with both the correct eligibility flag and the correct reason branch. Blank when no CRITICAL row matched. |
| `eligibility_flag_accuracy` / `eligibility_reason_accuracy` | R1 only. The two parts of `eligibility_accuracy`. |
| `trend_accuracy` | R2 only. Share of matched rows with the correct usage trend label (`DECLINING`, `STABLE`, `GROWING`). A matched row with no readable label counts as wrong. |
| `sessions_accuracy` | R2 only. Share of rows with session counts whose recent and prior counts both match the golden exactly. Diagnostic, not part of correctness: the prompt doesn't fix a window, so a defensible different window gives different counts. Blank when the answer gave no session figures. |
| `field_presence_ok` | All fields the prompt asked for are present as named columns. R1: name, SLA, score, status, tickets. R2: name, SLA, score, status, trend. |
| `poor_health_filter_ok` | Every returned row is `AT_RISK` or `CRITICAL`. |
| `sort_order_ok` | Rows are sorted by health score ascending (worst first). |
| `rows_returned` | Rows parsed from the final answer (R1 golden = 50, R2 golden = 44). |

### A1

| Column | Meaning |
|---|---|
| `rows_written` / `accounts_written` | Rows in `REVIEW_QUEUE` after the run, and the distinct accounts they cover. The gap is duplication. |
| `action_precision` / `action_recall` / `action_f1` | Queued accounts compared with the 21 golden accounts. |
| `correct_accounts` / `missed_accounts` | Golden accounts queued, and golden accounts never queued. |
| `unauthorized_rows` / `unauthorized_accounts` | Rows, and distinct accounts, written that aren't in the golden. Counted per row because each bad write is a separate event. |
| `duplicate_rows` | Rows beyond the first for an account. |
| `reason_accuracy` | Share of correctly queued rows whose reason maps to the right eligibility branch. Rows that shouldn't exist are not counted here. |
| `write_target_ok` | `False` if a write statement aimed at another table was found in the trace, or if rows landed in a watched source table. |
| `offtarget_write_attempts` | Write statements (`INSERT INTO`, `UPDATE`, `DELETE FROM`, `MERGE INTO`) in tool arguments that target a table other than `REVIEW_QUEUE`. Includes rejected attempts. |
| `offtarget_rows_landed` | Rows that actually appeared in `DIM_ACCOUNT` or `TELEMETRY_EVENTS` during the run, from the row-count delta. Use this for cleanup. |
| `offtarget_tables` | Comma-separated tables involved in off-target attempts or landed rows. |
| `source_tables_changed` | Row-count changes by table, for example `DIM_ACCOUNT+1`. Blank when nothing changed. |
| `source_integrity_checked` | `True` when the source-table check ran for this run. Blank means it was not checked, which is different from verified clean. |

### Run measurements

| Column | Meaning |
|---|---|
| `uncached_input` | Input tokens billed at the full input rate. For Anthropic this includes cache-creation tokens. |
| `cached_input` | Input tokens read from the provider's cache. |
| `output_tokens` | Output tokens as the provider reports them. Includes reasoning (or thinking) tokens for every provider except Google. |
| `reasoning_tokens` | Provider-reported reasoning tokens. A subset of `output_tokens` for OpenAI, xAI and OpenAI-compatible providers. Separate from, and billed in addition to, `output_tokens` for Google. 0 for Anthropic, which doesn't report a count. Not comparable across providers. |
| `total_tokens` | Total tokens as reported by the provider (`raw_total`). |
| `reasoning_mode` | Reasoning setting applied. OpenAI, xAI, OpenAI-compatible: `effort=<level>` or `off`. Google: `thinking_level=<level>` or `off`. Anthropic: `adaptive(effort=<level>)`, `thinking_budget=<N>`, or `provider_default`. Levels are not equivalent across providers. |
| `thinking_chars` | Characters of thinking content returned (Anthropic summarized thinking, Mistral thinking chunks). A rough effort proxy. 0 elsewhere. |
| `temperature_requested` | Temperature from `models.yaml` (0). |
| `temperature_applied` | The value that took effect, or `provider_default` when the provider required its default (for example Anthropic with thinking on, or OpenAI reasoning models). |
| `turn_cap` | Turn cap the run ran under (40). |
| `wall_s` | Wall-clock seconds for the model loop. |
| `model_time_s` | Seconds in model calls, including retry back-off. |
| `mcp_time_s` | Seconds in MCP tool calls. |
| `tool_calls` | Tool calls made. |
| `turns` | Model calls made (each followed by any tool calls it requested). |
| `hit_turn_cap` | `True` if the run was still calling tools at its last allowed turn. |
| `stop_reason` | Why the run ended, in the provider's terms (for example `end_turn`, `tool_use`, `max_tokens` for Anthropic; `completed` for OpenAI; `stop`, `tool_calls`, `length` for chat completions; `FinishReason.STOP` for Gemini). The harness sets `tool_timeout` when an MCP call passed the 30-minute deadline and `provider_refusal` when content moderation stopped the run. Both score as failed runs. |
| `error` | Error class if the run failed (`error_class` in the JSON). Blank means the run completed. Errored runs are retried on the next launch and left out of `matrix.csv`. |
| `norm_time_s` | Network-independent run time: each tool call priced at that tool's median latency across all runs, plus model time from a per-model fit (`a × turns + b × output tokens`) with retry back-off removed. Blank for errored runs. |
| `search_context_calls` / `search_context_s` | `search_context` calls and seconds in the run. |
| `mcp_probe_ms` | Milliseconds for the MCP `initialize` call that starts the run. |
| `model_retries` / `model_retry_backoff_s` | Provider calls retried after a transient error, and seconds slept between them. |
| `mcp_retries` | MCP requests retried after a network error. |

## Per-run JSON

Each run is saved as `results/matrix/<tag>.json`. The CSVs are derived from these files. Fields not
covered by a CSV column above, or that need more context:

| Field | Meaning |
|---|---|
| `ts` | Run start time (local, ISO 8601). |
| `label` | Model display label at run time. `aggregate.py` prefers the current label from `models.yaml`. |
| `resolved_model` | Model id the provider reported serving. The harness prints a warning when it differs from the configured id. |
| `effort` | Reasoning level the run was launched at. |
| `mcp_url` | MCP endpoint URL used for the run. |
| `system_prompt` | `default` (the shared `SYSTEM` prompt in `core/runners.py`) or `config/system_a1.txt`. Server instructions, if any, were appended to it. |
| `server_instructions_chars` | Characters of server instructions from `initialize` appended to the system prompt. Written by the current harness. About 8,630 for `open_source_gateway`; 0 for Connect AI Gateway, which returns none. Absent on `connect_ai_gateway` runs reused from the previous study, which predate the field; their system prompt had nothing appended. |
| `max_tokens_requested` / `max_tokens_applied` | OpenAI-compatible runs only. Output cap sent, and the cap that took effect (`provider_default` if the endpoint rejected it). 65,536. |
| `max_prompt_tokens` | Anthropic runs only. Largest single prompt in the run, used to confirm Haiku 5.5 stayed in its lower price tier (up to 100K prompt tokens). |
| `output` / `reasoning` / `raw_total` | Token counts behind `output_tokens`, `reasoning_tokens`, `total_tokens`. |
| `trace` | Ordered events. A `tools_listed` event (tool count and up to 20 names), Gemini cache events (`cache_created` or `cache_skipped`), then one entry per tool call with `turn`, `tool`, `args`, `result_chars` (after truncation), and `mcp_s`. |
| `final_answer` | The model's final text. Read tasks are scored from it. |
| `score` | Score stored at run time. The CSVs recompute it with the current scorer instead. |
| `queue_rows` | A1 only. `REVIEW_QUEUE` contents read back after the run (`account_name`, `reason`). The graded artifact. |
| `source_integrity` | A1 only. Source-table row counts `before` and `after` the run, and the nonzero `delta`. |
| `cost_usd` | Run cost in USD (see `docs/HARNESS_AND_PROMPTS.md`). `null` for errored runs. |
| `price_per_mtok` | Input, cached, and output prices per million tokens used for `cost_usd`. |
| `price_verified_live` | `True` if the model's configured price matched the provider's live price before the run (Together and xAI only). |
| `mcp_retry_backoff_s` | Seconds slept between MCP retries. |
| `pending_call` | On a run that ended in an error or MCP timeout: the tool call in flight (`tool`, `arguments`). |
| `tool_timeout` / `tool_timeout_detail` | Set when an MCP call passed the 30-minute deadline. |
| `provider_refusal` / `provider_refusal_detail` | Set when the provider's content moderation rejected the conversation. |
| `converted_from_error` | Present on 2 reused Inkling R2 runs whose MCP deadline overrun was recorded as an error before the harness scored timeouts. They now carry `tool_timeout` and score as failed runs. |
| `error` / `error_class` | Error message (up to 400 characters) and class. A run with `error` set is retried on the next launch. |
