---
type: metric
title: Account usage trend
semanticType: kpi
synonyms:
  - usage trend
  - account usage trend
  - product usage
  - declining usage
  - usage drop
  - usage decline
  - engagement trend
  - session trend
  - sessions
  - current vs prior 90 days
  - quarter over quarter usage
---

# Account usage trend

The usage trend compares an account's product sessions in the current 90 days with the 90 days before that. This is a calculation, not a table: compute it from the source tables below.

- Rows: [Snowflake_WH].[WH_DATA].[TELEMETRY_EVENTS], one row per usage event.
- Amount: SESSION_COUNT, summed per ACCOUNT_SK.
- Current window: EVENT_TIMESTAMP on or after 2026-04-17.
- Prior window: EVENT_TIMESTAMP from 2026-01-17 up to, but not including, 2026-04-17.
- Both windows are fixed to the reference date 2026-07-16, never today's date. Filter on EVENT_TIMESTAMP, not INGESTED_AT.
- Account: TELEMETRY_EVENTS.ACCOUNT_SK = DIM_ACCOUNT.ACCOUNT_SK, then DIM_ACCOUNT.SFDC_ACCOUNT_ID = [Salesforce_CRM].[Salesforce].[Account].Ext_Account_Id__c gives Account.Name.

Usage trend: DECLINING when current sessions are below 80% of prior sessions; GROWING when above 120%; otherwise STABLE. With no prior sessions, any current sessions count as GROWING; no sessions in either window is STABLE.

The trend applies to every account regardless of priority. For accounts in poor health with declining usage, take accounts whose health status under the Account health score rules is AT_RISK or CRITICAL and whose usage trend is DECLINING.

## Related

- Account health score rule
- Connect AI cross-connection query rules
- [Snowflake_WH].[WH_DATA].[TELEMETRY_EVENTS]
- [Snowflake_WH].[WH_DATA].[DIM_ACCOUNT]
