-- Snowflake-managed MCP server with metadata tools that mirror CData Connect AI's MCP tools.
--
--   Connect AI       Snowflake MCP tool   Backed by
--   --------------   ------------------   -----------------------------------------
--   getCatalogs   -> get_catalogs         MCP_BENCH.TOOLS.GET_CATALOGS()
--   getSchemas    -> get_schemas          MCP_BENCH.TOOLS.GET_SCHEMAS(catalog, LIKE)
--   getTables     -> get_tables           MCP_BENCH.TOOLS.GET_TABLES(catalog, schema, LIKE)
--   getColumns    -> get_columns          MCP_BENCH.TOOLS.GET_COLUMNS(catalog, schema, table, LIKE)
--   queryData     -> execute_sql          SYSTEM_EXECUTE_SQL
--   execute_insert-> execute_insert       MCP_BENCH.TOOLS.EXECUTE_INSERT(query, parameters)
--   execute_update-> execute_update       MCP_BENCH.TOOLS.EXECUTE_UPDATE(query, parameters)
--
-- "Catalog" = Snowflake database. Metadata tools return CSV, like Connect AI.
--
-- execute_insert / execute_update take parameters as JSON text, not an object: Snowflake's generic
-- MCP tools reject object-typed arguments ("unsupported parameter type: map[string]interface {}").
--
-- Writes: MCP_BENCH_ROLE (the MCP client's role) is read-only, so execute_sql cannot write.
-- EXECUTE_INSERT / EXECUTE_UPDATE run with owner's rights as MCP_BENCH_WRITER, which can
-- INSERT/UPDATE exactly one table: BENCHMARK_WH.WH_DATA.REVIEW_QUEUE.
--
--   Warehouse:       DEMO_WH (change every DEMO_WH below if yours differs)
--   Data database:   BENCHMARK_WH
--   MCP client user: <MCP_USER>
--
-- Before running, replace <MCP_USER> with the Snowflake user the MCP client logs in as, and
-- <ACCOUNT> with your account identifier. The placeholders fail to parse until you do.

-------------------------------------------------------------------------------
-- 1. Roles
-------------------------------------------------------------------------------
USE ROLE SECURITYADMIN;

CREATE ROLE IF NOT EXISTS MCP_BENCH_ROLE;
GRANT ROLE MCP_BENCH_ROLE TO USER <MCP_USER>;
GRANT ROLE MCP_BENCH_ROLE TO ROLE SYSADMIN;

-- Owns the write procedures; never granted to a user
CREATE ROLE IF NOT EXISTS MCP_BENCH_WRITER;
GRANT ROLE MCP_BENCH_WRITER TO ROLE SYSADMIN;

USE ROLE SYSADMIN;

-------------------------------------------------------------------------------
-- 2. Database and schema for the tools
-------------------------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS MCP_BENCH;
CREATE SCHEMA IF NOT EXISTS MCP_BENCH.TOOLS;
USE SCHEMA MCP_BENCH.TOOLS;
USE WAREHOUSE DEMO_WH;

-------------------------------------------------------------------------------
-- 3. Tool procedures
-------------------------------------------------------------------------------

-- getCatalogs
CREATE OR REPLACE PROCEDURE MCP_BENCH.TOOLS.GET_CATALOGS()
  RETURNS STRING
  LANGUAGE PYTHON
  RUNTIME_VERSION = '3.11'
  PACKAGES = ('snowflake-snowpark-python')
  HANDLER = 'run'
  EXECUTE AS CALLER
AS
$$
import csv, io

def run(session):
    rows = session.sql("SHOW DATABASES").collect()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["TABLE_CATALOG", "COMMENT"])
    for r in rows:
        if r["name"] != "MCP_BENCH":
            w.writerow([r["name"], r["comment"]])
    return out.getvalue()
$$;

-- getSchemas
CREATE OR REPLACE PROCEDURE MCP_BENCH.TOOLS.GET_SCHEMAS(
    CATALOG_NAME STRING,
    SCHEMA_NAME  STRING DEFAULT NULL)
  RETURNS STRING
  LANGUAGE PYTHON
  RUNTIME_VERSION = '3.11'
  PACKAGES = ('snowflake-snowpark-python')
  HANDLER = 'run'
  EXECUTE AS CALLER
AS
$$
import csv, io

def q(name):
    return '"' + name.replace('"', '""') + '"'

def run(session, catalog_name, schema_name=None):
    try:
        rows = session.sql(f"""
            SELECT catalog_name, schema_name, comment
            FROM {q(catalog_name)}.INFORMATION_SCHEMA.SCHEMATA
            WHERE schema_name <> 'INFORMATION_SCHEMA'
              AND schema_name LIKE ?
            ORDER BY schema_name""", params=[schema_name or "%"]).collect()
    except Exception as e:
        return f"ERROR: {e}"
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["TABLE_CATALOG", "TABLE_SCHEMA", "COMMENT"])
    for r in rows:
        w.writerow([r["CATALOG_NAME"], r["SCHEMA_NAME"], r["COMMENT"]])
    return out.getvalue()
$$;

-- getTables
CREATE OR REPLACE PROCEDURE MCP_BENCH.TOOLS.GET_TABLES(
    CATALOG_NAME STRING,
    SCHEMA_NAME  STRING,
    TABLE_NAME   STRING DEFAULT NULL)
  RETURNS STRING
  LANGUAGE PYTHON
  RUNTIME_VERSION = '3.11'
  PACKAGES = ('snowflake-snowpark-python')
  HANDLER = 'run'
  EXECUTE AS CALLER
AS
$$
import csv, io

def q(name):
    return '"' + name.replace('"', '""') + '"'

def run(session, catalog_name, schema_name, table_name=None):
    try:
        rows = session.sql(f"""
            SELECT table_catalog, table_schema, table_name, table_type, row_count, comment
            FROM {q(catalog_name)}.INFORMATION_SCHEMA.TABLES
            WHERE table_schema = ? AND table_name LIKE ?
            ORDER BY table_name""", params=[schema_name, table_name or "%"]).collect()
    except Exception as e:
        return f"ERROR: {e}"
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["TABLE_CATALOG", "TABLE_SCHEMA", "TABLE_NAME", "TABLE_TYPE", "ROW_COUNT", "COMMENT"])
    for r in rows:
        w.writerow([r["TABLE_CATALOG"], r["TABLE_SCHEMA"], r["TABLE_NAME"],
                    r["TABLE_TYPE"], r["ROW_COUNT"], r["COMMENT"]])
    return out.getvalue()
$$;

-- getColumns
CREATE OR REPLACE PROCEDURE MCP_BENCH.TOOLS.GET_COLUMNS(
    CATALOG_NAME STRING,
    SCHEMA_NAME  STRING,
    TABLE_NAME   STRING,
    COLUMN_NAME  STRING DEFAULT NULL)
  RETURNS STRING
  LANGUAGE PYTHON
  RUNTIME_VERSION = '3.11'
  PACKAGES = ('snowflake-snowpark-python')
  HANDLER = 'run'
  EXECUTE AS CALLER
AS
$$
import csv, io

def q(name):
    return '"' + name.replace('"', '""') + '"'

def run(session, catalog_name, schema_name, table_name, column_name=None):
    try:
        rows = session.sql(f"""
            SELECT column_name, data_type, is_nullable, ordinal_position, comment
            FROM {q(catalog_name)}.INFORMATION_SCHEMA.COLUMNS
            WHERE table_schema = ? AND table_name = ? AND column_name LIKE ?
            ORDER BY ordinal_position""",
            params=[schema_name, table_name, column_name or "%"]).collect()
    except Exception as e:
        return f"ERROR: {e}"
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["COLUMN_NAME", "DATA_TYPE", "IS_NULLABLE", "ORDINAL_POSITION", "COMMENT"])
    for r in rows:
        w.writerow([r["COLUMN_NAME"], r["DATA_TYPE"], r["IS_NULLABLE"],
                    r["ORDINAL_POSITION"], r["COMMENT"]])
    return out.getvalue()
$$;

-- Earlier versions took PARAMETERS as VARIANT; drop them so they don't linger as overloads.
DROP PROCEDURE IF EXISTS MCP_BENCH.TOOLS.EXECUTE_INSERT(STRING, VARIANT);
DROP PROCEDURE IF EXISTS MCP_BENCH.TOOLS.EXECUTE_UPDATE(STRING, VARIANT);

-- execute_insert (owner's rights: runs as MCP_BENCH_WRITER after ownership transfer below)
CREATE OR REPLACE PROCEDURE MCP_BENCH.TOOLS.EXECUTE_INSERT(
    QUERY      STRING,
    PARAMETERS STRING DEFAULT NULL)
  RETURNS STRING
  LANGUAGE PYTHON
  RUNTIME_VERSION = '3.11'
  PACKAGES = ('snowflake-snowpark-python')
  HANDLER = 'run'
  EXECUTE AS OWNER
AS
$$
import json, re

def load_params(parameters):
    # PARAMETERS arrives as JSON text (MCP generic tools can't pass an object), or NULL when omitted
    if parameters is None or not str(parameters).strip():
        return {}
    params = json.loads(parameters)
    if not isinstance(params, dict):
        raise ValueError("parameters must be a JSON object")
    return params

def bind(query, parameters):
    # Replace @name placeholders with ? and collect values in order
    params = {(k if k.startswith("@") else "@" + k): v for k, v in parameters.items()}
    values = []
    def sub(m):
        if m.group(0) not in params:
            return m.group(0)
        values.append(params[m.group(0)])
        return "?"
    return re.sub(r"@[A-Za-z_][A-Za-z0-9_]*", sub, query), values

def run(session, query, parameters=None):
    q = query.strip().rstrip(";").strip()
    if not re.match(r"INSERT\s", q, re.IGNORECASE) or re.match(r"INSERT\s+OVERWRITE\b", q, re.IGNORECASE):
        return "ERROR: Only INSERT statements are allowed. Use execute_sql for SELECT and execute_update for UPDATE."
    if ";" in q:
        return "ERROR: Only a single statement is allowed. Pass values through parameters."
    try:
        params = load_params(parameters)
    except ValueError as e:
        return f"ERROR: parameters must be a JSON object, e.g. {{\"@name\": \"Acme\"}}: {e}"
    sql, values = bind(q, params)
    try:
        rows = session.sql(sql, params=values).collect()
    except Exception as e:
        return f"ERROR: {e}"
    return f"Statement executed successfully. Rows affected: {rows[0][0] if rows else 0}."
$$;

-- execute_update (owner's rights: runs as MCP_BENCH_WRITER after ownership transfer below)
CREATE OR REPLACE PROCEDURE MCP_BENCH.TOOLS.EXECUTE_UPDATE(
    QUERY      STRING,
    PARAMETERS STRING DEFAULT NULL)
  RETURNS STRING
  LANGUAGE PYTHON
  RUNTIME_VERSION = '3.11'
  PACKAGES = ('snowflake-snowpark-python')
  HANDLER = 'run'
  EXECUTE AS OWNER
AS
$$
import json, re

def load_params(parameters):
    # PARAMETERS arrives as JSON text (MCP generic tools can't pass an object), or NULL when omitted
    if parameters is None or not str(parameters).strip():
        return {}
    params = json.loads(parameters)
    if not isinstance(params, dict):
        raise ValueError("parameters must be a JSON object")
    return params

def bind(query, parameters):
    # Replace @name placeholders with ? and collect values in order
    params = {(k if k.startswith("@") else "@" + k): v for k, v in parameters.items()}
    values = []
    def sub(m):
        if m.group(0) not in params:
            return m.group(0)
        values.append(params[m.group(0)])
        return "?"
    return re.sub(r"@[A-Za-z_][A-Za-z0-9_]*", sub, query), values

def run(session, query, parameters=None):
    q = query.strip().rstrip(";").strip()
    if not re.match(r"UPDATE\s", q, re.IGNORECASE):
        return "ERROR: Only UPDATE statements are allowed. Use execute_sql for SELECT and execute_insert for INSERT."
    if ";" in q:
        return "ERROR: Only a single statement is allowed. Pass values through parameters."
    try:
        params = load_params(parameters)
    except ValueError as e:
        return f"ERROR: parameters must be a JSON object, e.g. {{\"@name\": \"Acme\"}}: {e}"
    sql, values = bind(q, params)
    try:
        rows = session.sql(sql, params=values).collect()
    except Exception as e:
        return f"ERROR: {e}"
    return f"Statement executed successfully. Rows affected: {rows[0][0] if rows else 0}."
$$;

-------------------------------------------------------------------------------
-- 4. MCP server
-------------------------------------------------------------------------------
CREATE OR REPLACE MCP SERVER MCP_BENCH.TOOLS.SNOWFLAKE_BENCH_MCP
  FROM SPECIFICATION $$
    tools:
      - name: "get_catalogs"
        type: "GENERIC"
        identifier: "MCP_BENCH.TOOLS.GET_CATALOGS"
        title: "Get catalogs"
        description: "Lists available catalogs (Snowflake databases). Returns CSV."
        config:
          type: "procedure"
          warehouse: "DEMO_WH"
          input_schema:
            type: "object"
            properties: {}

      - name: "get_schemas"
        type: "GENERIC"
        identifier: "MCP_BENCH.TOOLS.GET_SCHEMAS"
        title: "Get schemas"
        description: "Lists schemas in a catalog. Returns CSV."
        config:
          type: "procedure"
          warehouse: "DEMO_WH"
          input_schema:
            type: "object"
            properties:
              catalog_name:
                type: "string"
                description: "Catalog (database) name, exactly as returned by get_catalogs."
              schema_name:
                type: "string"
                description: "Optional SQL LIKE filter, e.g. 'SALES%'. Omit to return all schemas."
            required: ["catalog_name"]

      - name: "get_tables"
        type: "GENERIC"
        identifier: "MCP_BENCH.TOOLS.GET_TABLES"
        title: "Get tables"
        description: |
          Lists tables in a schema with type, row count, and comment. Returns CSV.
          Use get_columns to see a table's columns.
        config:
          type: "procedure"
          warehouse: "DEMO_WH"
          input_schema:
            type: "object"
            properties:
              catalog_name:
                type: "string"
                description: "Catalog (database) name."
              schema_name:
                type: "string"
                description: "Schema name."
              table_name:
                type: "string"
                description: "Optional SQL LIKE filter on table name. Omit to return all tables."
            required: ["catalog_name", "schema_name"]

      - name: "get_columns"
        type: "GENERIC"
        identifier: "MCP_BENCH.TOOLS.GET_COLUMNS"
        title: "Get columns"
        description: "Lists columns for a table with data types and comments. Use before writing a query. Returns CSV."
        config:
          type: "procedure"
          warehouse: "DEMO_WH"
          input_schema:
            type: "object"
            properties:
              catalog_name:
                type: "string"
                description: "Catalog (database) name."
              schema_name:
                type: "string"
                description: "Schema name."
              table_name:
                type: "string"
                description: "Table name."
              column_name:
                type: "string"
                description: "Optional SQL LIKE filter, e.g. '%ID%'. Omit to return all columns."
            required: ["catalog_name", "schema_name", "table_name"]

      - name: "execute_sql"
        type: "SYSTEM_EXECUTE_SQL"
        title: "Query data"
        description: |
          Executes a Snowflake SQL SELECT statement and returns the results.
          Prerequisites: use get_catalogs, get_schemas, get_tables, and get_columns to confirm
          the tables and columns exist before querying. Do not guess names.
          Rules:
          - Only SELECT statements. Use execute_insert or execute_update for writes.
          - Use fully qualified names: "DB"."SCHEMA"."TABLE".
          - Snowflake SQL dialect: identifiers are uppercase unless double-quoted; use TRUE/FALSE for booleans;
            date functions include DATE_TRUNC, DATEADD, DATEDIFF.
          - Aggregate in SQL and always include a LIMIT.
          - Before filtering on a categorical column, check its values with SELECT DISTINCT ... LIMIT 20.

      - name: "execute_insert"
        type: "GENERIC"
        identifier: "MCP_BENCH.TOOLS.EXECUTE_INSERT"
        title: "Insert rows"
        description: |
          Executes a Snowflake SQL INSERT statement. Only INSERT statements are allowed; SELECT and UPDATE
          are rejected (use execute_sql or execute_update). Use fully qualified names: "DB"."SCHEMA"."TABLE".
          Pass values through parameters (e.g. VALUES (@name, @amount)); do not build values inline.
          Returns a confirmation message with the affected-row count.
        config:
          type: "procedure"
          warehouse: "DEMO_WH"
          input_schema:
            type: "object"
            properties:
              query:
                type: "string"
                description: "The INSERT statement, using @name placeholders for values."
              parameters:
                type: "string"
                description: "A JSON object, as text, of parameter names (starting with @) and their values, e.g. {\"@name\": \"Acme\", \"@amount\": 100}."
            required: ["query"]

      - name: "execute_update"
        type: "GENERIC"
        identifier: "MCP_BENCH.TOOLS.EXECUTE_UPDATE"
        title: "Update rows"
        description: |
          Executes a Snowflake SQL UPDATE statement. Only UPDATE statements are allowed; SELECT and INSERT
          are rejected (use execute_sql or execute_insert). Use fully qualified names: "DB"."SCHEMA"."TABLE".
          Pass values through parameters (e.g. SET status = @status WHERE id = @id); do not build values inline.
          Returns a confirmation message with the affected-row count.
        config:
          type: "procedure"
          warehouse: "DEMO_WH"
          input_schema:
            type: "object"
            properties:
              query:
                type: "string"
                description: "The UPDATE statement, using @name placeholders for values."
              parameters:
                type: "string"
                description: "A JSON object, as text, of parameter names (starting with @) and their values, e.g. {\"@status\": \"Closed\", \"@id\": 42}."
            required: ["query"]
  $$;

-------------------------------------------------------------------------------
-- 5. Grants
-------------------------------------------------------------------------------
GRANT USAGE ON WAREHOUSE DEMO_WH TO ROLE MCP_BENCH_ROLE;
GRANT USAGE ON DATABASE MCP_BENCH TO ROLE MCP_BENCH_ROLE;
GRANT USAGE ON SCHEMA MCP_BENCH.TOOLS TO ROLE MCP_BENCH_ROLE;
GRANT USAGE ON MCP SERVER MCP_BENCH.TOOLS.SNOWFLAKE_BENCH_MCP TO ROLE MCP_BENCH_ROLE;
GRANT USAGE ON PROCEDURE MCP_BENCH.TOOLS.GET_CATALOGS() TO ROLE MCP_BENCH_ROLE;
GRANT USAGE ON PROCEDURE MCP_BENCH.TOOLS.GET_SCHEMAS(STRING, STRING) TO ROLE MCP_BENCH_ROLE;
GRANT USAGE ON PROCEDURE MCP_BENCH.TOOLS.GET_TABLES(STRING, STRING, STRING) TO ROLE MCP_BENCH_ROLE;
GRANT USAGE ON PROCEDURE MCP_BENCH.TOOLS.GET_COLUMNS(STRING, STRING, STRING, STRING) TO ROLE MCP_BENCH_ROLE;
GRANT USAGE ON PROCEDURE MCP_BENCH.TOOLS.EXECUTE_INSERT(STRING, STRING) TO ROLE MCP_BENCH_ROLE;
GRANT USAGE ON PROCEDURE MCP_BENCH.TOOLS.EXECUTE_UPDATE(STRING, STRING) TO ROLE MCP_BENCH_ROLE;

-- Benchmark data: SELECT only
GRANT USAGE ON DATABASE BENCHMARK_WH TO ROLE MCP_BENCH_ROLE;
GRANT USAGE ON ALL SCHEMAS IN DATABASE BENCHMARK_WH TO ROLE MCP_BENCH_ROLE;
GRANT SELECT ON ALL TABLES IN DATABASE BENCHMARK_WH TO ROLE MCP_BENCH_ROLE;
GRANT SELECT ON ALL VIEWS IN DATABASE BENCHMARK_WH TO ROLE MCP_BENCH_ROLE;

-- Writer role: read access plus INSERT/UPDATE on the one writable table
GRANT USAGE ON DATABASE MCP_BENCH TO ROLE MCP_BENCH_WRITER;
GRANT USAGE ON SCHEMA MCP_BENCH.TOOLS TO ROLE MCP_BENCH_WRITER;
GRANT USAGE ON DATABASE BENCHMARK_WH TO ROLE MCP_BENCH_WRITER;
GRANT USAGE ON ALL SCHEMAS IN DATABASE BENCHMARK_WH TO ROLE MCP_BENCH_WRITER;
GRANT SELECT ON ALL TABLES IN DATABASE BENCHMARK_WH TO ROLE MCP_BENCH_WRITER;
GRANT SELECT ON ALL VIEWS IN DATABASE BENCHMARK_WH TO ROLE MCP_BENCH_WRITER;
GRANT INSERT, UPDATE ON TABLE BENCHMARK_WH.WH_DATA.REVIEW_QUEUE TO ROLE MCP_BENCH_WRITER;

-- Hand the write procedures to the writer role so they execute with its rights
GRANT OWNERSHIP ON PROCEDURE MCP_BENCH.TOOLS.EXECUTE_INSERT(STRING, STRING) TO ROLE MCP_BENCH_WRITER COPY CURRENT GRANTS;
GRANT OWNERSHIP ON PROCEDURE MCP_BENCH.TOOLS.EXECUTE_UPDATE(STRING, STRING) TO ROLE MCP_BENCH_WRITER COPY CURRENT GRANTS;

-- Future grants (need SECURITYADMIN or MANAGE GRANTS)
USE ROLE SECURITYADMIN;
GRANT USAGE ON FUTURE SCHEMAS IN DATABASE BENCHMARK_WH TO ROLE MCP_BENCH_ROLE;
GRANT SELECT ON FUTURE TABLES IN DATABASE BENCHMARK_WH TO ROLE MCP_BENCH_ROLE;
GRANT SELECT ON FUTURE VIEWS IN DATABASE BENCHMARK_WH TO ROLE MCP_BENCH_ROLE;

-------------------------------------------------------------------------------
-- 6. Smoke test as the MCP role
-------------------------------------------------------------------------------
USE ROLE MCP_BENCH_ROLE;
USE WAREHOUSE DEMO_WH;

CALL MCP_BENCH.TOOLS.GET_CATALOGS();
CALL MCP_BENCH.TOOLS.GET_SCHEMAS('BENCHMARK_WH');
CALL MCP_BENCH.TOOLS.GET_TABLES('BENCHMARK_WH', 'WH_DATA');
CALL MCP_BENCH.TOOLS.GET_COLUMNS('BENCHMARK_WH', 'WH_DATA', 'REVIEW_QUEUE');

-- Writes: this should FAIL (MCP_BENCH_ROLE is read-only)...
-- INSERT INTO BENCHMARK_WH.WH_DATA.REVIEW_QUEUE (<COL>) VALUES ('test');
-- ...and this should SUCCEED (goes through the writer role):
-- CALL MCP_BENCH.TOOLS.EXECUTE_INSERT(
--   'INSERT INTO BENCHMARK_WH.WH_DATA.REVIEW_QUEUE (<COL>) VALUES (@v)',
--   PARSE_JSON('{"@v": "test"}'));

SHOW MCP SERVERS IN SCHEMA MCP_BENCH.TOOLS;
DESCRIBE MCP SERVER MCP_BENCH.TOOLS.SNOWFLAKE_BENCH_MCP;

-- MCP endpoint for the client:
-- https://<ACCOUNT>.snowflakecomputing.com/api/v2/databases/MCP_BENCH/schemas/TOOLS/mcp-servers/SNOWFLAKE_BENCH_MCP
