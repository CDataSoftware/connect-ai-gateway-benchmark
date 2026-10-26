# Benchmark test plan: Connect AI Gateway vs. the open-source MCP gateway, both with context

Status: all 810 runs complete (2026-10-17). Results write-up pending.

## Motivation

The [Connect AI context benchmark](https://github.com/CDataSoftware/connect-ai-context-benchmark) (completed 2026-10-09) found that shared context, read through `search_context`, brought most models from near-zero success on raw access to a working answer. That study ran entirely on Connect AI. It did not show whether the gain comes from the context itself or from the surface that delivers it.

A generic MCP gateway can carry the same context. The open-source MCP gateway lets each MCP server publish `instructions`, which reach the model in the MCP initialize response. This study gives the open-source gateway the same context and asks whether Connect AI Gateway's federated, on-demand-context surface still does better on correctness, cost, tool calls and time.

## Design

Two conditions, the same tasks, models and limits: same context, different gateway.

"Same context" means all three layers:

| Layer | What it covers | Connect AI Gateway entries in `setup/connect_ai_gateway/context/` |
|---|---|---|
| System context | Schemas, objects and relationships | Seven table entries (`dataset_*.md`) that describe columns, keys and how records join |
| Semantic definitions | Metric definitions and business terminology | `account_health_score_rules.md`, `account_usage_trend.md` |
| Company knowledge | Team know-how | One entry, `cross_connection_query_rules.md`: how to query across the three systems (join keys, date handling, which SQL works and which fails) |

The setup is probabilistic: the model works out how to complete each task and writes its own queries on every run. Connect AI Gateway had nothing built in: no derived views, virtual schemas or custom tools. On the open-source gateway, the ITSM server publishes use-case tools (for example, per-company ticket counts); they encode no benchmark rules, and they favour that gateway (see [Threats to validity](#threats-to-validity)). A deterministic setup builds the how into the gateway with derived views, virtual schemas and custom tools. The [Connect AI model benchmark](https://github.com/CDataSoftware/connect-ai-model-benchmark) measured that setup, and this study reuses its tasks and goldens.

| Condition | Endpoint | Data access | Context |
|---|---|---|---|
| `connect_ai_gateway` (Connect AI Gateway) | Connect AI Gateway's standard MCP endpoint, `?ops=get_catalogs,get_schemas,get_tables,get_columns,get_instructions,queryData,search_context`. A1 adds `execute_insert`. Basic auth. | One SQL dialect over all three connections. `queryData` can join across systems in one statement. | Ten entries in `setup/connect_ai_gateway/context/`, read on demand through `search_context`. |
| `open_source_gateway` (the open-source MCP gateway) | The open-source gateway's `/mcp` endpoint, open-source gateway key in `Authorization: Bearer`. 20 tools on every task. | Three separate servers: a warehouse-managed MCP server (mirrors Connect AI's metadata tools, plus `execute_sql`, `execute_insert`, `execute_update`), the CRM's hosted MCP server (the CRM's query and search languages, and record lookups), and an ITSM MCP server publishing use-case tools from a scripted REST API through the ITSM platform's MCP server console. No cross-system join. | Server `instructions` from `setup/open_source_gateway/context/` plus the ITSM server's own, about 8,600 characters merged, in every session's system prompt. |

The `connect_ai_gateway` runs are the previous study's completed with-context runs. That study's raw-access `baseline` condition is not part of this one.

### The open-source gateway's context

`setup/open_source_gateway/context/warehouse.md` (about 6,500 characters) covers the warehouse system context, both semantic definitions (the account health score rules and the account usage trend), and the company knowledge for working across systems. `crm.md` (about 1,300 characters) covers the CRM system context and how to query the CRM. `setup/open_source_gateway/gateway_instructions.py --apply` loads both through the open-source gateway's management API.

The warehouse and CRM system context matches `setup/connect_ai_gateway/context/`, and the semantic definitions are copied word for word apart from table names. The company knowledge is the same know-how written for each system's own tools. It tells the model that no single query can read more than one system, so it queries each system and combines the results itself. It also notes that the CRM's query language has no date arithmetic, and gives the day 30 (2026-08-15) and day 90 (2026-10-14) cutoffs to use instead.

The ITSM instructions (about 700 characters: what the data covers, the valid field values, and how paging works) can come from either the ITSM MCP server, which the open-source gateway passes through, or the open-source gateway's `instructions` field for that server, loaded from `setup/open_source_gateway/context/itsm.md`. The text is the same either way. Use one or the other: setting the open-source gateway's field replaces the upstream text.

The harness appends any server instructions to the system prompt under `# MCP server instructions` and records `server_instructions_chars` per run. Connect AI Gateway returns no instructions, so its runs are unaffected. The `open_source_gateway` endpoint sets `require_instructions` to "Account health score rules" (our context) and "customer support incidents and the companies they belong to" (the ITSM server's own instructions): if the open-source gateway's instructions lack either, the run stops.

### Tasks

The three tasks from the previous studies, unchanged, with their goldens:

| Task | Prompt intent | Golden |
|---|---|---|
| R1 | High-priority accounts at risk, with review eligibility for CRITICAL accounts | 50 rows |
| R2 | Poor-health accounts whose product usage is also declining | 44 rows |
| A1 | Queue a review for every eligible CRITICAL account, with its reason, and nobody else | 21 rows in `REVIEW_QUEUE` |

A1 gets a system prompt that asks for the changes the task requests (`config/system_a1.txt`). The default system prompt asks for a report, which led some models to describe the writes rather than make them.

## Controlled variables and limits

Both conditions share these settings:

- **Turn cap:** 40 model round trips.
- **Tool results:** truncated at 8,000 characters before they reach the model. `search_context` gets 32,000 so it returns whole entries.
- **Output cap:** 64,000 tokens for Anthropic models (streamed) and 65,536 for Together and Mistral, so models that compute an answer in their own reasoning aren't cut off. OpenAI, Google and xAI models run without an explicit cap, at the provider default.
- **Temperature:** 0 where the provider allows it. Reasoning-on OpenAI and thinking-on Anthropic models force the provider default, and each run records `temperature_applied`.
- **Reasoning effort:** medium where the provider offers it. Otherwise the nearest documented level (high), or the provider default where there is no control.
- **MCP call deadline:** 30 minutes. A call past it ends the run as a scored failure (`tool_timeout`). A provider's content filter rejecting the conversation does the same (`provider_refusal`).
- **A1 state:** `REVIEW_QUEUE` is reset before every run and read back afterwards by `core/verifier.py` through Connect AI's REST query API, never through the endpoint under test. Test inserts through the open-source gateway were read back by the verifier on 2026-10-13, confirming both see the same physical table.
- **Pricing:** list prices with provider-aware token billing. Together and xAI prices are checked live before each run.

## Model roster

27 models from 12 developers, defined in `config/models.yaml`:

| Developer | Models | Served by |
|---|---|---|
| Anthropic | Haiku 4.5, Haiku 5.5, Sonnet 5.5, Fable 5, Fable 5.1, Opus 5.5 | Anthropic |
| OpenAI | GPT-6 Astra, GPT-6 Sol, GPT-6 Luna | OpenAI |
| Google | Gemini 3.1 Flash-Lite, Gemini 3.8 Flash | Google |
| xAI | Grok 4.3, Grok 4.7 | xAI |
| Mistral AI | Mistral Small 4, Mistral Large 3, Mistral Large 4 | Mistral AI |
| Alibaba | Qwen 3.5 9B, Qwen 3.7 Max, Qwen 3.8 Flash | Together.ai |
| DeepSeek | DeepSeek V4 Flash, DeepSeek V4 Pro | Together.ai |
| Z.ai | GLM-5.3, GLM-5.3 Flash | Together.ai |
| Meta | Muse Glimmer 30B | Together.ai |
| Moonshot AI | Kimi K3 | Together.ai |
| MiniMax | MiniMax M3 | Together.ai |
| Thinking Machines | Inkling | Together.ai |

Effort levels: 15 models at medium, 7 at high, 5 at the provider default.

## Run counts

| | Connect AI Gateway | The open-source MCP gateway |
|---|---|---|
| Runs per condition | 27 models x 3 tasks x 5 runs = 405 | 405 |

Total: 162 cells, 810 runs. The Connect AI Gateway runs come from the previous study's with-context condition, run with the same harness and settings. Run files for every task are named `{model}@{effort}__{task}__{condition}__run{n}`.

## Measures

- **Outcome:** correctness against the golden, success rate, and solved, wrong and no-answer rates.
- **Effort:** tool calls, turns and tokens.
- **Cost:** cost per run, total spend, cost per success.
- **Time:** wall time, and normalized time, which prices each run's work at typical speeds so network conditions don't distort it (`core/timing.py`).
- **A1 safety:** unauthorized rows, duplicates, and off-target writes. Off-target writes are detected from `DIM_ACCOUNT` and `TELEMETRY_EVENTS` row counts before and after each A1 run, plus a scan of the run's write statements.

## Threats to validity

- **Federation is part of the treatment.** Connect AI Gateway can join all three systems in one statement. The open-source gateway can't. Results compare the two gateways as a whole, not context delivery alone.
- **Context delivery differs.** The AI gateway retrieves entries on demand. The open-source gateway sends all of its context in every session, which costs input tokens on every turn but saves the model from searching.
- **The ITSM server favours the open-source gateway.** Its ITSM server has use-case tools of the kind a customer publishes through the ITSM platform's MCP server console, including per-company counts of open incidents by priority. The Connect AI Gateway condition gets general SQL over the raw tables. The tools return the ITSM platform's JSON shape (`{"result": ...}`) with `limit`/`offset` paging, and encode no benchmark rules: which priorities count as urgent, the thresholds and the reference date come only from the context.
- **Warehouse results favour Connect AI Gateway.** The warehouse server's `execute_sql` returns the warehouse's raw JSON rather than CSV, so each result costs more tokens and hits the 8,000-character cap sooner.
- **Write tools on read tasks.** The open-source gateway exposes `execute_insert` and `execute_update` on R1 and R2. The Connect AI Gateway read condition has no write tools.
- **Different run dates and locations.** The Connect AI Gateway runs finished by 2026-10-09, run from a workstation. The open-source gateway runs ran from 2026-10-14, most of them from a cloud VM. Provider-side model or infrastructure changes in between would show up as a difference between conditions, and wall-clock times include different network paths. Normalized time (`core/timing.py`) reduces but doesn't remove the network effect, so compare effort through tool calls, turns and tokens first.
- **Character decoding in the reused runs.** In the previous study, the harness decoded MCP responses as ISO-8859-1, so the minus sign in "Bronze −5" reached the Connect AI Gateway runs garbled for every model except Haiku 5.5. The harness now decodes UTF-8, and the open-source gateway runs receive the rule intact. The previous study found 9 of 342 runs that applied a Bronze adjustment used a value other than −5.
- **ITSM mirror and stand-in.** The open-source gateway read the ITSM data from a mirror of the ITSM instance's incident and company tables, through a stand-in MCP server that implements the documented tool contract and instructions, not through the ITSM platform's MCP server console. Connect AI Gateway's ITSM connection read the same mirror in the 155 runs made for this study, and the live instance in the 250 reused runs (below). The mirror copies the instance's two tables, so the data is the same. Tool behaviour follows the contract; latency and error handling may differ from a live instance or a console-hosted server.
- **The CRM's MCP server.** The open-source gateway reached the CRM through the CRM's own hosted MCP server, with its six default read tools and nothing built on top. A different CRM, or a different MCP server for the same CRM, would expose different tools and change the open-source gateway's results. A server with aggregate queries, for example, would let the model count and filter in one call. Connect AI Gateway reaches the CRM through its own connection.
- **Reused Connect AI Gateway runs.** 250 of the 405 Connect AI Gateway runs, for 17 models, come from the context benchmark (2026-10-01 to 2026-10-09) and were made with its harness. They read the ITSM data from the live instance and ran with an output cap of 16,384 tokens or the provider default; none reached the cap. The other 155 Connect AI Gateway runs (every run of the ten models served through OpenAI-compatible APIs, streamed, plus four Sonnet 5.5 R2 runs and one Qwen 3.7 Max A1 run) and all 405 open-source gateway runs read the mirror and ran with the 64K cap.
- **Tool list in 57 early open-source gateway runs.** The first 57 open-source gateway runs (Haiku 4.5, Haiku 5.5 and Sonnet 5.5 in full, and 12 Gemini 3.1 Flash-Lite runs, all on 2026-10-14) listed the ITSM server's `list_aging_open_incidents` and not the warehouse server's `execute_update`. Every other run listed the 20 tools in the Conditions table. No run called `list_aging_open_incidents`, and A1 needs only inserts.
- **One set of context text.** Results measure these entries and these instructions. Better or worse text would give different numbers. Both versions are published so others can test their own.
- **Hosted open-weight models** measure one provider's deployment of the model, not the weights in general.

## Results

_Results pending: all runs are complete; the results write-up is in progress._
