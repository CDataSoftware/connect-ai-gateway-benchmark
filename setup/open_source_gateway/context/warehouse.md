# Warehouse data (Snowflake)

The warehouse tables live in database BENCHMARK_WH, schema WH_DATA. Name them fully: BENCHMARK_WH.WH_DATA.DIM_ACCOUNT, BENCHMARK_WH.WH_DATA.TELEMETRY_EVENTS, BENCHMARK_WH.WH_DATA.REVIEW_QUEUE. Read with snowflake-execute_sql (Snowflake SQL, SELECT only). Write REVIEW_QUEUE with snowflake-execute_insert.

## DIM_ACCOUNT

Warehouse account dimension. One row per customer account; it links Salesforce accounts to warehouse usage data. Monthly job volume for the Account health score rules comes from here.

- ACCOUNT_SK (Number): warehouse account key; joins to TELEMETRY_EVENTS.ACCOUNT_SK.
- SFDC_ACCOUNT_ID (String): Salesforce external account id; equals Salesforce Account.Ext_Account_Id__c (not the Salesforce Account.Id).
- ACCOUNT_NAME (String): account name.
- MONTHLY_JOBS_L90 (Number): monthly job volume over the trailing 90 days.
- ACTIVE_SEATS (Number): active licensed seats.
- PLAN_CODE (String): subscription plan.

## TELEMETRY_EVENTS

Product usage events. One row per usage event per account; sessions for the Account usage trend come from here. Filter time windows on EVENT_TIMESTAMP, not INGESTED_AT.

- ACCOUNT_SK (Number): warehouse account key; joins to DIM_ACCOUNT.ACCOUNT_SK.
- EVENT_TIMESTAMP (DateTime): when the usage happened; use this for date windows.
- SESSION_COUNT (Number): sessions in the event; sum it for session totals.
- EVENT_TYPE (String): kind of usage event.
- EVENT_SK (Number): event key.
- INGESTED_AT (DateTime): when the event was loaded into the warehouse; not the usage time.

## REVIEW_QUEUE

Escalation review queue. One row per account queued for escalation review, with the reason it was queued. An account appears at most once.

- ID (Number): queue entry id, assigned automatically.
- ACCOUNT_NAME (String): account queued for review; matches Salesforce Account.Name.
- REASON (String): the account's eligibility reason under the Account health score rules: the first trigger that applies, written exactly as one of "Renewal within 90 days", "ACV above review threshold", or "High urgent ticket volume".
- QUEUED_AT (DateTime): when the entry was added, set automatically.

## Account health score rules

This is a calculation rule, not a table or view. There is no account health score table to query: compute the score, status, review eligibility, and eligibility reason from the source data listed below. Use it for questions about account health, at-risk or critical accounts, and which accounts need an escalation review.

The rule applies to High-priority accounts (Salesforce Account.CustomerPriority__c = 'High') that have a matching warehouse record with a non-null MONTHLY_JOBS_L90.

All date math uses the fixed reference date 2026-07-16, never today's date.

Inputs and where they live:
- SLA tier: Salesforce Account.SLA__c (Platinum, Gold, Silver, Bronze).
- Monthly jobs: BENCHMARK_WH.WH_DATA.DIM_ACCOUNT.MONTHLY_JOBS_L90, matched on Salesforce Account.Ext_Account_Id__c = DIM_ACCOUNT.SFDC_ACCOUNT_ID.
- Days to renewal: days from 2026-07-16 to Salesforce Account.ContractEndDate__c; negative means the contract has already ended.
- Annual contract value: Salesforce Account.AnnualContractValue__c, in USD.
- Urgent open tickets: ServiceNow incidents for the company whose name equals Account.Name, with priority Critical or High and state Open; 0 if none.

Health score: start at 100, then
- SLA tier: Platinum +10, Gold +5, Silver 0, Bronze −5.
- Monthly jobs: under 41 subtract 25; 41 to 150 subtract 10; over 150 subtract 0.
- Days to renewal: 30 or fewer (including negative) subtract 25; 31 to 90 subtract 10; more than 90 subtract 0.
- Urgent open tickets: subtract 5 per ticket, at most 25.

Health status: CRITICAL below 40, AT_RISK 40 to 59, MONITOR 60 to 79, HEALTHY 80 and above. Poor health means AT_RISK or CRITICAL.

Review eligibility: an account is ELIGIBLE if any of these holds, otherwise NOT ELIGIBLE: days to renewal is between 0 and 90 inclusive; annual contract value is 250,000 or more; urgent open tickets is 5 or more.

Eligibility reason: the first trigger that applies, checked in this order: "Renewal within 90 days", "ACV above review threshold", "High urgent ticket volume". If none applies: "No escalation trigger met".

## Account usage trend

The usage trend compares an account's product sessions in the current 90 days with the 90 days before that. This is a calculation, not a table: compute it from the source tables below.

- Rows: BENCHMARK_WH.WH_DATA.TELEMETRY_EVENTS, one row per usage event.
- Amount: SESSION_COUNT, summed per ACCOUNT_SK.
- Current window: EVENT_TIMESTAMP on or after 2026-04-17.
- Prior window: EVENT_TIMESTAMP from 2026-01-17 up to, but not including, 2026-04-17.
- Both windows are fixed to the reference date 2026-07-16, never today's date. Filter on EVENT_TIMESTAMP, not INGESTED_AT.
- Account: TELEMETRY_EVENTS.ACCOUNT_SK = DIM_ACCOUNT.ACCOUNT_SK, then DIM_ACCOUNT.SFDC_ACCOUNT_ID = Salesforce Account.Ext_Account_Id__c gives Account.Name.

Usage trend: DECLINING when current sessions are below 80% of prior sessions; GROWING when above 120%; otherwise STABLE. With no prior sessions, any current sessions count as GROWING; no sessions in either window is STABLE.

The trend applies to every account regardless of priority. For accounts in poor health with declining usage, take accounts whose health status under the Account health score rules is AT_RISK or CRITICAL and whose usage trend is DECLINING.

## Working across Salesforce, Snowflake and ServiceNow

- Each system is reached through its own tools: salesforce-* (SOQL), snowflake-* (Snowflake SQL), servicenow-* (purpose-built support tools; see the ServiceNow instructions). No single query can read more than one system: query each, then combine the results yourself.
- Match records across systems with these keys:
  - Salesforce to Snowflake: Account.Ext_Account_Id__c = DIM_ACCOUNT.SFDC_ACCOUNT_ID. Prefer this to matching names.
  - Snowflake usage to accounts: TELEMETRY_EVENTS.ACCOUNT_SK = DIM_ACCOUNT.ACCOUNT_SK.
  - Salesforce to ServiceNow: Account.Name = the ServiceNow company name.
- Dates: business rules use the fixed reference date 2026-07-16, never CURRENT_DATE. In Snowflake SQL: DATEDIFF(day, '2026-07-16', some_date). Date windows: EVENT_TIMESTAMP >= '2026-04-17'.
- Filter and aggregate inside each system rather than returning raw rows; tool results are size-limited. Sum SESSION_COUNT per ACCOUNT_SK in Snowflake, and filter Salesforce accounts to CustomerPriority__c = 'High' in SOQL.
