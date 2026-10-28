# CData Connect AI benchmark: Connect AI Gateway vs. an open-source MCP gateway

A reproducible benchmark that asks:

> **Given the same context, does Connect AI Gateway's federated, on-demand-context MCP surface beat an open-source MCP gateway on correctness, cost, tool calls and time?**

Twenty-seven models from twelve developers run the same governed-data tasks through the two gateways (same context, different gateway):

- **Connect AI Gateway.** CData Connect AI's MCP endpoint. One SQL statement (`queryData`) can span all three systems, and `search_context` returns shared context entries when the model asks for them.
- **The open-source MCP gateway.** It fronts three separate MCP servers (warehouse, CRM, ITSM). The same context reaches the model as the servers' `instructions`.

This study builds on the [Connect AI context benchmark](https://github.com/CDataSoftware/connect-ai-context-benchmark) (October 2026), which compared raw access with raw access plus context on Connect AI. 250 of the 405 Connect AI Gateway runs here are that study's with-context runs, for 17 models. The other 155 were run for this study: every run of the ten models served through OpenAI-compatible APIs, which this study streams, plus five runs redone for other models. [`docs/TEST_PLAN.md`](docs/TEST_PLAN.md#threats-to-validity) lists what differs between the two sets. For the raw-access results, see that repo.

## The tasks

All tasks span three systems, joined on divergent keys: a CRM (accounts), a cloud data warehouse (product telemetry) and an ITSM system (support incidents). Every model gets the same prompt. Answers are scored against a golden set derived **offline** from the frozen source CSVs (`core/golden.py`).

| Task | Question | Scored on |
|---|---|---|
| **R1** | Customer health: which High-priority accounts are at risk, and is each CRITICAL account review-eligible? | answer vs. golden |
| **R2** | Composition: poor-health accounts **whose product usage is also declining** | answer vs. golden |
| **A1** | Write-back: queue a review for every eligible CRITICAL account, and nobody else | the **database end state** |

## Context

Both gateways carry the same three layers of context:

| Layer | What it covers | Connect AI Gateway entries in [`setup/connect_ai_gateway/context/`](setup/connect_ai_gateway/context/) |
|---|---|---|
| System context | Schemas, objects and relationships | Seven table entries (`dataset_*.md`) that describe columns, keys and how records join |
| Semantic definitions | Metric definitions and business terminology | `account_health_score_rules.md`, `account_usage_trend.md` |
| Company knowledge | Team know-how | One entry, `cross_connection_query_rules.md`: how to query across the three systems (join keys, date handling, which SQL works and which fails) |

Connect AI Gateway serves these ten entries on demand through `search_context`. The open-source gateway carries the same semantic definitions, and the system context for the warehouse and CRM tables, as server instructions organized by system (`setup/open_source_gateway/context/warehouse.md` and `crm.md`). The ITSM server describes its own data through its tools and its own instructions (`itsm.md`). The open-source gateway's company knowledge is the same know-how written for each system's own tools: for example, that the CRM's query language can't join to the other systems or do date arithmetic, so the model queries each system and combines the results itself.

### A probabilistic setup

This benchmark is probabilistic: the model works out how to complete each task and writes its own queries on every run. Connect AI Gateway had nothing built in: no derived views, virtual schemas or custom tools. On the open-source gateway, the ITSM server publishes use-case tools (for example, per-company ticket counts). They encode no benchmark rules, and they favour that gateway (see [Fairness differences](#fairness-differences)).

A deterministic setup builds the how into the gateway with derived views, virtual schemas and custom tools. The [Connect AI model benchmark](https://github.com/CDataSoftware/connect-ai-model-benchmark) (September 2026) measured that setup. This study and the context benchmark reuse its tasks, synthetic dataset, goldens and scoring.

## Conditions

| Condition | Endpoint | Tools | How context arrives |
|---|---|---|---|
| **Connect AI Gateway** (`connect_ai_gateway`) | Connect AI's standard MCP endpoint with an `?ops=` allowlist. Basic auth (email and personal access token). | `get_catalogs`, `get_schemas`, `get_tables`, `get_columns`, `get_instructions`, `queryData`, `search_context`. A1 adds `execute_insert`. | On demand: `search_context` over the ten entries in [`setup/connect_ai_gateway/context/`](setup/connect_ai_gateway/context/). |
| **The open-source MCP gateway** (`open_source_gateway`) | The open-source gateway's `/mcp` endpoint, authenticated with an open-source gateway key (`Authorization: Bearer`). | 20 tools from three servers (below), the same set on every task. | Up front: about 8,600 characters of server `instructions`, appended to the system prompt in every session. |

The open-source gateway's three servers (the open-source gateway prefixes each tool name with its server's alias):

| Server | What it is | Tools | Auth |
|---|---|---|---|
| Warehouse | A warehouse-managed MCP server built to mirror Connect AI's tools ([`setup/open_source_gateway/warehouse_mcp_server.sql`](setup/open_source_gateway/warehouse_mcp_server.sql)) | `get_catalogs`, `get_schemas`, `get_tables`, `get_columns`, `execute_sql`, `execute_insert`, `execute_update` | Warehouse access token ([`setup/open_source_gateway/warehouse_mcp_token.sql`](setup/open_source_gateway/warehouse_mcp_token.sql)) |
| CRM | The CRM's hosted MCP server (record reads) | Six tools: record search, object schema, related records, user info, recent records, and the CRM's query tool | OAuth 2 with refresh token |
| ITSM | An ITSM MCP server publishing use-case tools (from the ITSM platform's MCP server console, over a scripted REST API). The published runs used a stand-in with the same tool contract; see [`setup/README.md`](setup/README.md) | `get_support_portfolio_summary`, `lookup_company`, `get_incident`, `search_incidents`, `get_company_ticket_profile`, `list_companies_by_open_incidents`, `get_resolution_performance`, `list_aging_open_incidents` | Per your instance |

The warehouse server's client role is read-only. `execute_insert` and `execute_update` run with owner's rights as a writer role that can insert into and update only `BENCHMARK_WH.WH_DATA.REVIEW_QUEUE`.

The open-source gateway's context lives in [`setup/open_source_gateway/context/`](setup/open_source_gateway/context/): `warehouse.md` (the warehouse system context, both semantic definitions, and the cross-system company knowledge), `crm.md` (the CRM system context and how to query it), and `itsm.md`. The semantic definitions are copied word for word from `setup/connect_ai_gateway/context/`; only table names change. The ITSM instructions (about 700 characters: what the data covers, valid field values, paging) come from the ITSM server itself, which the open-source gateway passes through, or from the open-source gateway's own `instructions` field if the server can't return them.

The harness appends any `instructions` from the MCP initialize response to the system prompt under `# MCP server instructions`, as Claude Desktop and Claude Code do. Connect AI Gateway returns none, so its runs are unaffected. If the open-source gateway's instructions lack either the health-score rules or the ITSM server's own instructions, the run stops before it starts.

## What is held equal

- Tasks, prompts, goldens and scoring.
- Models, at the same reasoning effort.
- Turn cap of 40.
- Tool results truncated at 8,000 characters (`search_context` at 32,000).
- Output cap of 64,000 tokens (Anthropic) or 65,536 (Together and Mistral). OpenAI, Google and xAI models run at their provider defaults.
- Temperature 0 where the provider allows it.
- A1's system prompt (`config/system_a1.txt`), the `REVIEW_QUEUE` reset before each run, and the read-back for grading.

## Fairness differences

The two gateways can't be made identical. These differences remain, in both directions:

1. **Federation.** Connect AI Gateway joins the CRM, warehouse and ITSM system in one SQL statement. Through the open-source gateway, the model must query each system and combine the results itself.
2. **Context delivery.** The AI gateway retrieves entries on demand through `search_context`. The open-source gateway sends all of its context in every session's system prompt.
3. **ITSM tools.** Behind the open-source gateway, the ITSM system is an MCP server with use-case tools, including per-company counts of open incidents by priority. That is what a customer would publish through the ITSM platform's MCP server console; the ITSM platform's out-of-the-box MCP servers don't ship aggregate tools like these. This favours the open-source gateway. The Connect AI Gateway condition gets general SQL over the raw tables.
4. **Result format.** The warehouse server's `execute_sql` returns the warehouse's raw JSON, not CSV. That costs more tokens per result and disfavours the open-source gateway.
5. **Write parameters.** The warehouse server's `execute_insert` takes `parameters` as JSON text, because the warehouse's generic MCP tools reject object arguments. Connect AI Gateway's takes an object.
6. **Write tools on read tasks.** The open-source gateway exposes `execute_insert` and `execute_update` on R1 and R2 too. The Connect AI Gateway read condition has no write tools.
7. **Timing and location.** The Connect AI Gateway runs come from the previous study, completed 2026-10-09 from a workstation. The open-source gateway runs ran from 2026-10-14, most of them from a cloud VM. Any provider-side change in between shows up as a gap between conditions, and wall-clock times include different network paths; normalized time (`core/timing.py`) reduces but doesn't remove that.
8. **Character decoding.** In the previous study, the harness decoded MCP responses as ISO-8859-1 for every model except Haiku 5.5. The minus sign in "Bronze −5" reached those Connect AI Gateway runs garbled. The harness now decodes UTF-8, so the open-source gateway runs receive it intact.

[`docs/TEST_PLAN.md`](docs/TEST_PLAN.md) covers these in more detail.

## Runs

Five runs per model, task and condition: 27 models x 3 tasks x 2 conditions x 5 runs = **810 runs**. The Connect AI Gateway runs come from the previous study's with-context condition, run with the same harness and settings. The open-source gateway runs are new.

**Reasoning effort.** Each model runs at medium where its provider offers that level. Models without a medium setting run at their nearest documented level (high). Models with no reasoning control run at the provider default. `effort` and `effort_levels` in `config/models.yaml` record the level used and the levels each model supports.

## Models (27 models, 12 developers)

| Developer | Models | Served by |
|---|---|---|
| **Anthropic** | Haiku 4.5, Haiku 5.5, Sonnet 5.5, Fable 5, Fable 5.1, Opus 5.5 | Anthropic |
| **OpenAI** | GPT-6 Astra, GPT-6 Sol, GPT-6 Luna | OpenAI |
| **Google** | Gemini 3.1 Flash-Lite, Gemini 3.8 Flash | Google |
| **xAI** | Grok 4.3, Grok 4.7 | xAI |
| **Mistral AI** | Mistral Small 4, Mistral Large 3, Mistral Large 4 | Mistral AI |
| **Alibaba** | Qwen 3.5 9B, Qwen 3.7 Max, Qwen 3.8 Flash | Together.ai |
| **DeepSeek** | DeepSeek V4 Flash, DeepSeek V4 Pro | Together.ai |
| **Z.ai** | GLM-5.3, GLM-5.3 Flash | Together.ai |
| **Meta** | Muse Glimmer 30B | Together.ai |
| **Moonshot AI** | Kimi K3 | Together.ai |
| **MiniMax** | MiniMax M3 | Together.ai |
| **Thinking Machines** | Inkling | Together.ai |

In `models.yaml` and `matrix.csv`, `provider` names the API dialect the harness speaks, not the model's developer. Models served by Together and Mistral report `openai_compat`. A hosted open-weight result measures that deployment of the model, not the weights in general.

All providers run through the same client-side tool loop for token-accounting parity, with provider-aware token billing at list prices. Together and xAI prices are checked live before each run. The rest are entered by hand.

## Scoring

Scoring is deterministic: every score is computed from a run's saved artifacts against a frozen golden set, with no generative step in the scoring path.

- **Correctness (read tasks):** **R1:** set F1 of account names (50%, tolerant at the score-cut tie), health status (25%), and CRITICAL eligibility (25%, flag **and** reason). **R2:** set F1 (50%), health status (25%), usage-trend label (25%).
- **Correctness (write task):** graded on what actually landed in `REVIEW_QUEUE`. `core/verifier.py` reads the table back through Connect AI's REST query API, never through the endpoint under test. Action F1 (70%) plus reason correctness (30%). The open-source gateway's warehouse server and the verifier see the same physical table: test inserts through the open-source gateway were read back by the verifier.
- **Safety (write task), reported separately:** unauthorized rows, duplicate rows, and off-target writes. Off-target writes are detected from `DIM_ACCOUNT` and `TELEMETRY_EVENTS` row counts before and after each run, plus a scan of the run's write statements.
- **Success:** correctness of 60 or more on R1 and R2; a clean write on A1 (correct accounts, no unauthorized or duplicate rows).
- **Effort:** tool calls and turns (model round trips) per run, tokens, and normalized time, a network-independent run time (`core/timing.py`).
- **Failed runs, not errors:** a run that hits the turn cap, a tool call that runs past the 30-minute MCP call deadline (`tool_timeout`), and a provider's content filter rejecting the conversation (`provider_refusal`) all count as failures. They are not retried.

[`results/DATA_DICTIONARY.md`](results/DATA_DICTIONARY.md) defines every column.

## Results

_Results pending: all runs are complete; the results write-up is in progress._

When the run completes, `results/matrix.csv` will hold per-model results and `results/runs_raw.csv` every run. Raw per-run JSON is not published. `aggregate.py` and `export_raw.py` recompute every score from each run's saved answer or write-target snapshot, so they always reflect the current scorer.

## Running it

1. `pip install -r requirements.txt`.
2. Recreate the data environment as described in [`setup/README.md`](setup/README.md): three Connect AI connections, the warehouse tables, the synthetic data, and the context entries.
3. Set up the open-source gateway:
   - The open-source MCP gateway, with its three servers registered under the aliases given in [`setup/README.md`](setup/README.md).
   - The ITSM MCP server, as described in [`setup/README.md`](setup/README.md).
   - The warehouse MCP server: run [`setup/open_source_gateway/warehouse_mcp_server.sql`](setup/open_source_gateway/warehouse_mcp_server.sql) and [`setup/open_source_gateway/warehouse_mcp_token.sql`](setup/open_source_gateway/warehouse_mcp_token.sql) after replacing the `<MCP_USER>` and `<ACCOUNT>` placeholders.
   - The context: `python3 setup/open_source_gateway/gateway_instructions.py` shows what would change, and `--apply` writes it. The script reads `GATEWAY_URL` and `GATEWAY_ADMIN_KEY` (the open-source gateway's admin key) from `.env`, or the admin key from the open-source gateway's own env file with `--gateway-env`. If the open-source gateway lists no servers, pass each server's id with `--id ALIAS=<id>` for the warehouse and CRM servers.
4. Copy `.env.example` to `.env` and fill in `CDATA_EMAIL`, `CDATA_ACCESS_TOKEN`, `GATEWAY_URL`, `GATEWAY_KEY`, and the provider API keys for the models you plan to run. The two Connect AI Gateway MCP URLs (`CONNECT_AI_MCP_URL`, `CONNECT_AI_MCP_WRITE_URL`) need no changes.
5. `python3 make_goldens.py` regenerates the R2 and A1 goldens. It refuses to write anything unless it first reproduces R1's frozen golden exactly.
6. `python3 run_matrix.py --dry-run` confirms the plan before you spend anything. It connects to every MCP endpoint in the plan and prints each one's tool count and instruction length.
7. `python3 run_matrix.py` runs the full matrix. It is resumable and skips completed runs. Scope it with `--task r2` or `--model gpt-6-sol`, or smoke-test cheaply with `--runs 1 --out-dir results/smoke`. `--effort X` runs every selected model at one reasoning level instead of its configured level.
8. `python3 aggregate.py --effort configured`, then `python3 export_raw.py`.
9. `python3 charts.py` renders the five figures used in the whitepaper (tokens to reach the same correct answer, for each model-and-task pair both gateways got right; effort per run across all runs; cost per correct task vs. success rate; success rate by model; read-task outcomes), plus the executive summary's Figure 1 (tokens for the typical correct answer), from `results/runs_raw.csv` into `results/charts/`.

Write-task runs reset `REVIEW_QUEUE` before each run. The harness verifies read and reset access before the matrix starts, so a permissions problem surfaces immediately rather than dozens of ungradable runs later.

## Repo layout

```
.
├── run_matrix.py        # matrix orchestrator: models x tasks x conditions (resumable)
├── make_goldens.py      # regenerate R2/A1 goldens; self-checks against R1's frozen golden
├── aggregate.py         # per-run JSONs -> results/matrix.csv (medians, per task)
├── export_raw.py        # per-run JSONs -> results/runs_raw.csv (no aggregation)
├── charts.py            # results/runs_raw.csv -> the whitepaper's five figures in results/charts/
├── core/                # mcp_client, runners, scorer, golden, verifier, tasks, timing, pricing
├── config/              # models.yaml, prompt*.txt, system_a1.txt, rubric.yaml, golden_*.csv
├── setup/               # reproduction guide (README.md) and what each part needs
│   ├── data/                    # warehouse_tables.sql: the benchmark tables (both gateways)
│   ├── connect_ai_gateway/
│   │   └── context/             # the ten Connect AI context entries
│   └── open_source_gateway/
│       ├── context/             # the same context as open-source gateway server instructions
│       ├── gateway_instructions.py
│       ├── warehouse_mcp_server.sql, warehouse_mcp_token.sql
│       └── itsm_tools.md        # the ITSM server's tool specification
├── synthetic-data/      # the frozen synthesized dataset + golden result set
├── data-loader/         # loads synthetic-data/ into your connections via Connect AI itself
├── docs/                # TEST_PLAN.md, HARNESS_AND_PROMPTS.md
└── results/             # matrix.csv, runs_raw.csv, charts/
    └── DATA_DICTIONARY.md   # defines every column in matrix.csv and runs_raw.csv
```
