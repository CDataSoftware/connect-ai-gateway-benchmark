# Setup: reproducing both conditions

The repo holds the harness, prompts, goldens and synthetic dataset. It does not hold the systems the
benchmark runs against. This guide recreates them for both conditions:

- **Connect AI Gateway** (`connect_ai_gateway`): CData Connect AI's MCP endpoint, with the shared
  context entries in `setup/connect_ai_gateway/context/` available through `search_context`.
- **The open-source MCP gateway** (`open_source_gateway`): a gateway fronting three MCP servers
  (the cloud data warehouse, the CRM and the ITSM system), with the same context loaded as server
  `instructions` from `setup/open_source_gateway/context/`.

Both conditions read the same physical data. Work through the steps in order.

## 1. Data and Connect AI connections

1. **Create three connections in Connect AI**, named exactly as below. The context entries, prompts
   and verifier refer to them by these names.

   | Connection name | Source | Tables used |
   |---|---|---|
   | `Salesforce_CRM` | The CRM (for example, Salesforce) | `Account` (custom fields `SLA__c`, `CustomerPriority__c`, `AnnualContractValue__c`, `ContractEndDate__c`, `Ext_Account_Id__c`), `Contact` |
   | `Snowflake_WH` | The cloud data warehouse (for example, Snowflake), database `BENCHMARK_WH`, schema `WH_DATA` | `DIM_ACCOUNT`, `TELEMETRY_EVENTS`, `REVIEW_QUEUE` |
   | `ServiceNow_ITSM` | The ITSM system (for example, ServiceNow) | `u_bm_incident`, `u_bm_company` |

   Point the warehouse connection at database `BENCHMARK_WH` and schema `WH_DATA`, so its metadata
   tools list only the benchmark tables.

   The context entries name the ITSM tables `[ServiceNow_ITSM].[itsm].[...]`. For the runs made
   for this study, the ITSM connection read a mirror of the instance's `u_bm_incident` and `u_bm_company` tables
   whose schema is `itsm`. A live connection to the ITSM system exposes the same tables under schema
   `ServiceNow`; if you use one, change the five `itsm` references in `connect_ai_gateway/context/` to `ServiceNow`.

2. **Create the warehouse database, schema and tables** with [`data/warehouse_tables.sql`](data/warehouse_tables.sql). It creates
   `BENCHMARK_WH.WH_DATA` with `DIM_ACCOUNT`, `TELEMETRY_EVENTS` and the `REVIEW_QUEUE` write target.
   Run it before the warehouse MCP scripts in step 3, which grant rights on `REVIEW_QUEUE`.

   If you place `REVIEW_QUEUE` in a different schema, set `REVIEW_QUEUE_TABLE` in `.env` to the full
   path (for example `Snowflake_WH.CUSTOMER_OPS.REVIEW_QUEUE`). Then update
   `setup/connect_ai_gateway/context/dataset_review_queue.md`, `setup/connect_ai_gateway/context/cross_connection_query_rules.md`,
   `setup/open_source_gateway/context/warehouse.md` and the `REVIEW_QUEUE` grant in `warehouse_mcp_server.sql` to
   match. A wrong path fails the A1 preflight, not partway through the matrix.

3. **Load the synthetic data** from `synthetic-data/` into the three sources. The scripts in
   `data-loader/` load rows through Connect AI's REST Query API (see `data-loader/README.md`). The
   CRM org must hold only the dataset's 1,200 accounts, so remove any sample accounts it was created
   with.

4. **Add the shared context entries** in Connect AI from `setup/connect_ai_gateway/context/`, one entry per file, with the
   text exactly as written:

   | File | Entry | Layer |
   |---|---|---|
   | `dataset_account.md`, `dataset_contact.md` | Datasets on `Salesforce_CRM` | System context |
   | `dataset_dim_account.md`, `dataset_telemetry_events.md`, `dataset_review_queue.md` | Datasets on `Snowflake_WH` | System context |
   | `dataset_u_bm_incident.md`, `dataset_u_bm_company.md` | Datasets on `ServiceNow_ITSM` | System context |
   | `account_health_score_rules.md` | Glossary entry (business rule) | Semantic definitions |
   | `account_usage_trend.md` | Metric | Semantic definitions |
   | `cross_connection_query_rules.md` | Glossary entry (query guidance) | Company knowledge |

   The Connect AI Gateway condition reads these entries on demand through `search_context`. The
   open-source gateway's files in `setup/open_source_gateway/context/` copy the semantic definitions from them
   word for word, apart from table names. Changing the text in either place changes what the
   benchmark measures.

## 2. Connect AI Gateway endpoint

Copy `.env.example` to `.env` and set `CDATA_EMAIL` and `CDATA_ACCESS_TOKEN` (a Connect AI personal
access token). The harness authenticates to Connect AI Gateway with HTTP Basic auth built from these two
values.

The two Connect AI Gateway URLs need no changes. Both are Connect AI Gateway's standard endpoint with an `?ops=`
allowlist:

| Variable | Used by | Tools |
|---|---|---|
| `CONNECT_AI_MCP_URL` | R1, R2 | `get_catalogs`, `get_schemas`, `get_tables`, `get_columns`, `get_instructions`, `queryData`, `search_context` |
| `CONNECT_AI_MCP_WRITE_URL` | A1 | The same, plus `execute_insert` |

Set `WH_CONN` to your warehouse connection's name, and `REVIEW_QUEUE_TABLE` to
`<that name>.WH_DATA.REVIEW_QUEUE`. With the connection names from step 1, that's `WH_CONN=Snowflake_WH`
and `REVIEW_QUEUE_TABLE=Snowflake_WH.WH_DATA.REVIEW_QUEUE`, matching the context entries. The verifier (`core/verifier.py`) uses them to reset and read `REVIEW_QUEUE`
through Connect AI's REST query API, never through the endpoint under test.

## 3. The open-source MCP gateway

### Run the open-source MCP gateway: for example, LiteLLM

Use the open-source gateway's Docker quickstart, which runs the proxy with a database that stores MCP servers,
gateway keys and spend logs:

```bash
mkdir mcp-gateway && cd mcp-gateway
curl -sSLO https://github.com/BerriAI/litellm/raw/main/docker/docker-compose.quickstart.yml
printf 'LITELLM_MASTER_KEY=sk-%s\nLITELLM_SALT_KEY=sk-%s\n' "$(openssl rand -hex 32)" "$(openssl rand -hex 32)" > .env
docker compose -f docker-compose.quickstart.yml up -d
```

The proxy listens on port 4000, with an admin UI at `/ui`. Keep the open-source gateway's `.env`: regenerating
`LITELLM_SALT_KEY` makes the credentials already stored in the database unreadable. For anything
beyond local evaluation, pin the image to a release tag.

Add the three MCP servers below in the admin UI. Use these exact aliases: the open-source gateway
prefixes each tool name with its server's alias (for example `snowflake-execute_sql`), and the context in
`setup/open_source_gateway/context/` refers to tools by those names.

### Warehouse server, alias `snowflake`: for example, a Snowflake-managed MCP server

[`open_source_gateway/warehouse_mcp_server.sql`](open_source_gateway/warehouse_mcp_server.sql) builds a warehouse-managed MCP server (the warehouse's own MCP server
feature) whose tools mirror Connect AI Gateway's:

| Connect AI Gateway tool | Open-source gateway tool | Notes |
|---|---|---|
| `getCatalogs`, `getSchemas`, `getTables`, `getColumns` | `get_catalogs`, `get_schemas`, `get_tables`, `get_columns` | Caller's-rights procedures. Return CSV, like Connect AI Gateway. |
| `queryData` | `execute_sql` | The warehouse's built-in `SYSTEM_EXECUTE_SQL`. Returns the warehouse's JSON result, not CSV. |
| `execute_insert`, `execute_update` | `execute_insert`, `execute_update` | Owner's-rights procedures. `parameters` is a JSON string, not an object, because the warehouse's generic MCP tools reject object-typed arguments. |

The client role, `MCP_BENCH_ROLE`, is read-only, so `execute_sql` cannot write. The write procedures
run as `MCP_BENCH_WRITER`, which can `INSERT` and `UPDATE` only `BENCHMARK_WH.WH_DATA.REVIEW_QUEUE`.

1. In both SQL files, replace `<MCP_USER>` with the warehouse user the MCP client logs in as, and
   `<ACCOUNT>` with your account identifier. The files do not parse until you do.
2. If your compute warehouse is not `DEMO_WH`, change every `DEMO_WH` in `warehouse_mcp_server.sql`.
3. Run `warehouse_mcp_server.sql`. It creates the roles, the `MCP_BENCH.TOOLS` schema, the tool
   procedures, the `SNOWFLAKE_BENCH_MCP` server and the grants, then smoke-tests the tools as
   `MCP_BENCH_ROLE`.
4. Run [`open_source_gateway/warehouse_mcp_token.sql`](open_source_gateway/warehouse_mcp_token.sql). It adds an authentication policy so the user can use a programmatic
   access token (PAT) without a network policy, then creates a PAT restricted to `MCP_BENCH_ROLE`.
   Run the `ADD PROGRAMMATIC ACCESS TOKEN` statement by itself and copy `TOKEN_SECRET` at once: you
   cannot retrieve it later. The token expires after 30 days, so rotate it before a long run if it is
   close to expiry.
5. In the open-source gateway, add a server with alias `snowflake`, HTTP transport, URL
   `https://<ACCOUNT>.snowflakecomputing.com/api/v2/databases/MCP_BENCH/schemas/TOOLS/mcp-servers/SNOWFLAKE_BENCH_MCP`,
   and bearer auth set to the PAT.

The script does not change the MCP user's default role or warehouse, because other applications may
use the same user. The PAT's role restriction pins MCP sessions to `MCP_BENCH_ROLE`.

### CRM server, alias `salesforce`: for example, Salesforce's hosted MCP server

Add the CRM's hosted MCP server (the `sobject-reads` server) with alias `salesforce` and OAuth2
auth. Complete the OAuth sign-in so the open-source gateway holds a refresh token, which keeps the connection
alive through a long run. The server exposes `find` (the CRM's text search), `getObjectSchema`,
`getRelatedRecords`, `getUserInfo`, `listRecentSobjectRecords` and `soqlQuery`. Sign in as a user who
can read `Account`, `Contact` and the custom fields listed in step 1.

Use the CRM's own hosted MCP server with its default tools, and build nothing on top of it: the
benchmark is probabilistic, so the model works out each query itself. To reproduce the published
runs exactly, use the same server and the six tools above. A different CRM, or a different MCP
server for the same CRM, is a variation: its tools change what the model can do in one call, so
expect the open-source gateway's results to move. Connect AI Gateway reaches the CRM through its
own connection, so this choice doesn't affect that condition in the same way.

### ITSM server, alias `servicenow`: for example, ServiceNow's MCP Server Console

The ITSM platform's MCP server console publishes MCP tools from your instance. Table API access can't
be published as a tool, so build the use-case tools as a scripted REST API and publish its resources:

1. Install **MCP Server Console** from the ITSM platform's store. It requires Now Assist. See the
   [release notes](https://www.servicenow.com/docs/r/release-notes/mcp-server-console-rn.html)
   and the [MCP Server Console FAQ](https://www.servicenow.com/community/servicenow-otto-articles/mcp-server-console-faq/ta-p/3550125).
2. Create a scripted REST API with one GET resource per tool below, reading `u_bm_incident` and
   `u_bm_company` with `GlideRecord` and `GlideAggregate`. Scripted REST wraps each response in
   `{"result": ...}`. List resources take `limit` (maximum 200; default 50, or 20 for `lookup_company`)
   and `offset`, and return `total` alongside the page.
3. In MCP Server Console, create a server and add each resource as a tool with the name below. Use
   the descriptions, parameters, defaults, response fields and ordering in
   [`open_source_gateway/itsm_tools.md`](open_source_gateway/itsm_tools.md). If the server can return
   instructions, set the text shown after the table.
4. Register the server's MCP URL in the open-source gateway with alias `servicenow`, using credentials that
   won't expire during a long unattended run. Hide `list_aging_open_incidents` in the open-source
   gateway's tool permissions for this server, so the model sees the other seven tools, as in the
   published runs.

| Tool | Parameters | Returns |
|---|---|---|
| `get_support_portfolio_summary` | none | Total incidents and companies, counts by state, priority, category and assignment group, and open incidents by priority |
| `lookup_company` | `name_contains`, `limit`, `offset` | Companies whose name contains the text (case-insensitive): sys_id, name, country, account manager, total and open incidents |
| `get_incident` | `incident_sys_id` | One incident, with its company's country and account manager |
| `search_incidents` | `company_name`, `state`, `priority`, `category`, `assignment_group`, `opened_after`, `opened_before`, `limit`, `offset` | Incidents, newest first. The four value filters accept a comma-separated list |
| `get_company_ticket_profile` | `company_name` | One company: total, open and closed counts, open and total counts by priority, reopened incidents, average and longest days to resolve, first and last incident dates |
| `list_companies_by_open_incidents` | `priority`, `min_count`, `limit`, `offset` | Companies by number of open incidents (optionally only the given priorities), most first, with open counts per priority and total incidents |
| `get_resolution_performance` | `target_days`, `company_name`, `assignment_group`, `priority` | Per assignment group: counts, average, fastest and slowest days to resolve, closed within and outside the target, reopened |
| `list_aging_open_incidents` | `min_age_days`, `as_of_date` (defaults to today), `company_name`, `priority`, `assignment_group`, `limit`, `offset` | Open incidents at least that old, oldest first, with age in days |

Tool descriptions state what each tool returns and nothing about the benchmark: no urgent-ticket
definition, thresholds or reference date. Those come only from the context. Server instructions
(set them exactly as written):

```text
This server exposes the ServiceNow ITSM support system: customer support incidents and the companies they belong to. It is read-only and holds no CRM, contract, revenue or product-usage data.

Company names are exact and match the account names used in other systems. If a name returns nothing, use lookup_company to find the right spelling.

Valid field values (case-sensitive):
- state: Open, Closed
- priority: Critical, High, Moderate, Low
- category: Access, Database, Hardware, Network, Performance, Security, Software
- assignment_group: DBA, L1-Support, L2-Support, Network-Ops, SecOps

List tools return a page of results with total, limit and offset. Use offset to fetch the next page.
```

For the published runs, these tools were served by a stand-in MCP server that implements the same
tool contract and instructions over a mirror of the instance's `u_bm_incident` and `u_bm_company`
tables. Connect AI Gateway's ITSM connection read the same mirror in the runs made for this study; the
runs reused from the context benchmark read the live instance, whose two tables the mirror copies.

These instructions can reach the model from either place. The model sees the same text either way.

- **From the ITSM MCP server,** if it returns instructions from `initialize`. The open-source gateway
  passes them through. Don't also set the open-source gateway's `instructions` field on this server: that field replaces the
  upstream text.
- **From the open-source gateway,** if the server can't return instructions. The same text is in
  [`open_source_gateway/context/itsm.md`](open_source_gateway/context/itsm.md); load it with the instructions loader in
  step 4.

### Create an open-source gateway key

In the admin UI, create a gateway key with access to the three MCP servers. Then set these in this
repo's `.env`:

```bash
GATEWAY_URL=http://localhost:4000   # the proxy's base URL; the harness appends /mcp
GATEWAY_KEY=sk-...                  # the open-source gateway key, sent as "Authorization: Bearer <GATEWAY_KEY>"
```

Through `/mcp`, the open-source gateway should list 20 tools: 7 from `snowflake`, 6 from `salesforce` and 7 from
`servicenow`. The ITSM server publishes eight; hide `list_aging_open_incidents` in the open-source gateway's tool
permissions for that server, as in the published runs.

## 4. Load the open-source gateway's context

The open-source gateway has no context store like Connect AI Gateway's. The closest native feature is a per-server
`instructions` field, which the open-source gateway merges into its MCP `initialize` response. The harness appends
those instructions to the system prompt under `# MCP server instructions`, as Claude Desktop and
Claude Code do.

`gateway_instructions.py` sets the field on the `snowflake` and `salesforce` servers from
`setup/open_source_gateway/context/warehouse.md` and `crm.md`. It reads `GATEWAY_URL` from this repo's `.env`,
and the open-source gateway's admin key from `GATEWAY_ADMIN_KEY` in the same `.env`:

```bash
python3 setup/open_source_gateway/gateway_instructions.py           # show the change
python3 setup/open_source_gateway/gateway_instructions.py --apply   # write it
```

To read the admin key from the open-source gateway's own env file instead, pass `--gateway-env`
(there is no default path). The script then uses the admin key variable the open-source gateway
itself defines there
(for example, LiteLLM's `LITELLM_MASTER_KEY`):

```bash
python3 setup/open_source_gateway/gateway_instructions.py --gateway-env /path/to/mcp-gateway/.env --apply
```

Use `--clear` to remove the instructions.

The script finds servers by alias through `GET /v1/mcp/server`. Some gateway builds return an empty
list there, even for the admin key. If the script reports no server for an alias, pass each server's
ID from the admin UI:

```bash
python3 setup/open_source_gateway/gateway_instructions.py --apply \
  --id snowflake=<WAREHOUSE_SERVER_ID> --id salesforce=<CRM_SERVER_ID>
```

By default the script sets `snowflake` and `salesforce` only, leaving the ITSM instructions to the
ITSM server (step 3). To serve them from the open-source gateway instead, pass all three
mappings:

```bash
python3 setup/open_source_gateway/gateway_instructions.py --apply \
  --map snowflake=warehouse.md --map salesforce=crm.md --map servicenow=itsm.md
```

With all three servers in place, the open-source gateway returns about 8,600 characters of merged instructions.

## 5. Verify

1. Run `python3 make_goldens.py`. It confirms the offline golden model reproduces
   `config/golden_result.csv`, then regenerates the R2 and A1 goldens. It refuses to write anything
   if the R1 golden does not match.
2. Run a dry run for one model:

   ```bash
   python3 run_matrix.py --task r1 --model <model-id> --dry-run
   ```

   The dry run checks model IDs and live prices, prints the plan, then connects to every endpoint in
   the plan without calling a model. Look for both endpoint lines:

   - `OK  connect_ai_gateway: ... tools, 0 chars of server instructions`
   - `OK  open_source_gateway: 20 tools, ... chars of server instructions`

   If a condition's variables are missing from `.env`, the dry run prints a `skipping` line and leaves
   that condition out of the plan. The `open_source_gateway` check requires two phrases in the
   open-source gateway's instructions: `Account health score rules` (from the context loaded in step 4) and
   `customer support incidents and the companies they belong to` (from the ITSM server's
   instructions). If either is missing, the check fails and tells you to run
   `gateway_instructions.py --apply`, or check the server.

3. Optionally, run one model end to end on the write task, kept out of the real matrix:

   ```bash
   python3 run_matrix.py --task a1 --model <model-id> --runs 1 --out-dir results/smoke
   ```

**A1 resets `REVIEW_QUEUE`.** Any run or dry run that includes A1 runs the verifier preflight, which
deletes every row in `REVIEW_QUEUE`. Each A1 run also resets the table before it starts. Do not keep
anything you need in that table.

## 6. Permissions

| Where | Who | Needs |
|---|---|---|
| Connect AI, `Snowflake_WH` | The user behind `CDATA_EMAIL` | Select, Insert (the Connect AI Gateway condition's A1 writes) and Delete (the verifier's reset of `REVIEW_QUEUE`) |
| Connect AI, `Salesforce_CRM` and `ServiceNow_ITSM` | The same user | Select |
| Warehouse, setup | Whoever runs the SQL files | `SECURITYADMIN` and `SYSADMIN` for `warehouse_mcp_server.sql`. `ACCOUNTADMIN` for the authentication policy in `warehouse_mcp_token.sql`. |
| Warehouse, runtime | `MCP_BENCH_ROLE` (granted by the script) | Usage on `DEMO_WH`, the `MCP_BENCH.TOOLS` procedures and the MCP server. Select on `BENCHMARK_WH`. No write rights. |
| Warehouse, writes | `MCP_BENCH_WRITER` (owns the write procedures, never granted to a user) | Insert and Update on `BENCHMARK_WH.WH_DATA.REVIEW_QUEUE` only |
| CRM | The user who completes the OAuth sign-in | API access and read access to `Account`, `Contact` and the benchmark's custom fields |
| Open-source gateway | `gateway_instructions.py` | The open-source gateway's admin key (`GATEWAY_ADMIN_KEY`), to update servers |
| Open-source gateway | The harness | An open-source gateway key (`GATEWAY_KEY`) with access to the three MCP servers |

Loading the data needs more: native admin rights for the CRM custom fields and the ITSM custom
tables, and `CREATE` rights in the warehouse for `data/warehouse_tables.sql`. See `data-loader/README.md`.

## Reference date

The business rules and golden formulas use `2026-07-16` as a frozen reference date, matching the
synthetic dataset. If you adapt this benchmark to live data with a different reference date, update the
dates in `account_health_score_rules.md`, `account_usage_trend.md` and
`cross_connection_query_rules.md`, in `setup/open_source_gateway/context/` (including the CRM query cutoffs in
`crm.md`), and in `core/golden.py`. Then re-run `make_goldens.py` to regenerate the goldens.
