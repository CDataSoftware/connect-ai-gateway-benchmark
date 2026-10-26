---
type: glossary
title: Connect AI cross-connection query rules
semanticType: query_guidance
synonyms:
  - how to query across Salesforce, Snowflake and ServiceNow
  - cross-connection join
  - federated query
  - join Salesforce to Snowflake
  - join Salesforce to ServiceNow
  - SQL dialect
  - table names
  - date arithmetic
  - DATEDIFF
  - query failed
  - table does not exist
---

# Connect AI cross-connection query rules

How to write one SQL statement that reads the Salesforce, Snowflake and ServiceNow connections together.

- Name every table as [Connection].[Schema].[Table]. The connections are Salesforce_CRM, Snowflake_WH and ServiceNow_ITSM:
  - [Salesforce_CRM].[Salesforce].[Account], [Salesforce_CRM].[Salesforce].[Contact]
  - [Snowflake_WH].[WH_DATA].[DIM_ACCOUNT], [Snowflake_WH].[WH_DATA].[TELEMETRY_EVENTS], [Snowflake_WH].[WH_DATA].[REVIEW_QUEUE]
  - [ServiceNow_ITSM].[itsm].[u_bm_incident], [ServiceNow_ITSM].[itsm].[u_bm_company]
- The first part is the Connect AI connection name. Do not use the underlying Snowflake database name (BENCHMARK_WH), which can appear in error messages, and do not use a catalog named Global.
- One statement can join all three connections. Aggregate each connection in its own subquery first, then join the results: count incidents per u_company inside a ServiceNow subquery, and sum SESSION_COUNT per ACCOUNT_SK inside a Snowflake subquery.
- Join keys:
  - Salesforce to Snowflake: Account.Ext_Account_Id__c = DIM_ACCOUNT.SFDC_ACCOUNT_ID. Prefer this to matching names.
  - Snowflake usage to accounts: TELEMETRY_EVENTS.ACCOUNT_SK = DIM_ACCOUNT.ACCOUNT_SK.
  - Salesforce to ServiceNow: Account.Name = u_bm_incident.u_company.
- Dates: business rules use the fixed reference date 2026-07-16, never CURRENT_DATE. Days between dates: DATEDIFF(day, '2026-07-16', a.ContractEndDate__c). Date windows: EVENT_TIMESTAMP >= '2026-04-17'.
- Conditional totals: SUM(CASE WHEN ... THEN SESSION_COUNT ELSE 0 END), not FILTER (WHERE ...).
- CASE, COALESCE, LEAST, BETWEEN, subqueries in FROM, ORDER BY and LIMIT all work.
- Do not use WITH (common table expressions) in a statement that reads more than one connection: it fails with a misleading error, "The schema name 'WH_DATA' is invalid", although the schema exists. Use subqueries in FROM instead. WITH works within a single connection.
- Filter and aggregate in SQL rather than returning raw rows; tool results are size-limited.

## Related

- Account health score rules
- Account usage trend
