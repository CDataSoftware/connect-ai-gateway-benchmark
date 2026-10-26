-- Programmatic access token (PAT) for unattended benchmark scripts to call the
-- SNOWFLAKE_BENCH_MCP server as <MCP_USER>, restricted to MCP_BENCH_ROLE.
--
-- Run AFTER snowflake_mcp_server.sql.
--
-- Before running, replace <MCP_USER> with the Snowflake user the MCP client logs in as, and
-- <ACCOUNT> with your account identifier. The placeholders fail to parse until you do.

-------------------------------------------------------------------------------
-- 1. User defaults: intentionally NOT changed
-- The PAT's ROLE_RESTRICTION already pins MCP sessions to MCP_BENCH_ROLE.
-- The MCP user may also be used by other apps (e.g. CData Connect AI via key-pair
-- auth); changing its DEFAULT_ROLE/DEFAULT_WAREHOUSE would change their access.
-------------------------------------------------------------------------------

-------------------------------------------------------------------------------
-- 2. Network requirement
-- By default Snowflake only accepts a PAT for a user covered by a network policy.
-- This authentication policy removes that requirement for <MCP_USER>.
-- On a rerun, the ALTER USER fails with "already has a AUTHENTICATION_POLICY":
-- that means it's already applied, so skip it.
-------------------------------------------------------------------------------
USE ROLE ACCOUNTADMIN;

CREATE AUTHENTICATION POLICY IF NOT EXISTS MCP_BENCH.TOOLS.MCP_BENCH_AUTH_POLICY
  PAT_POLICY = (NETWORK_POLICY_EVALUATION = ENFORCED_NOT_REQUIRED)
  COMMENT = 'Allows MCP benchmark PATs without a network policy';

ALTER USER <MCP_USER> SET AUTHENTICATION POLICY MCP_BENCH.TOOLS.MCP_BENCH_AUTH_POLICY;

-------------------------------------------------------------------------------
-- 3. Create the token
-- The TOKEN_SECRET column in the output is shown ONCE. Copy it into the
-- benchmark's .env (e.g. SNOWFLAKE_PAT=...) immediately; it cannot be retrieved later.
-- Run this statement BY ITSELF (select it, then run) so its output isn't replaced
-- by the output of a later statement.
-------------------------------------------------------------------------------
USE ROLE SECURITYADMIN;

ALTER USER <MCP_USER> ADD PROGRAMMATIC ACCESS TOKEN MCP_BENCH_PAT
  ROLE_RESTRICTION = 'MCP_BENCH_ROLE'
  DAYS_TO_EXPIRY = 30
  COMMENT = 'Connect AI vs Snowflake MCP benchmark';

-------------------------------------------------------------------------------
-- 4. Manage the token
-------------------------------------------------------------------------------
SHOW USER PROGRAMMATIC ACCESS TOKENS FOR USER <MCP_USER>;

-- Lost the secret? Rotate (run alone; returns a new secret, old one stops working now):
-- ALTER USER <MCP_USER> ROTATE PROGRAMMATIC ACCESS TOKEN MCP_BENCH_PAT
--   EXPIRE_ROTATED_TOKEN_AFTER_HOURS = 0;

-- Revoke when the benchmark is done:
-- ALTER USER <MCP_USER> REMOVE PROGRAMMATIC ACCESS TOKEN MCP_BENCH_PAT;

-------------------------------------------------------------------------------
-- 5. Test from a shell (lists the MCP tools)
-------------------------------------------------------------------------------
-- curl -s -X POST \
--   "https://<ACCOUNT>.snowflakecomputing.com/api/v2/databases/MCP_BENCH/schemas/TOOLS/mcp-servers/SNOWFLAKE_BENCH_MCP" \
--   -H "Authorization: Bearer $SNOWFLAKE_PAT" \
--   -H "Content-Type: application/json" \
--   -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}'
