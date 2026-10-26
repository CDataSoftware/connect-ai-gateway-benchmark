---
type: glossary
title: Account health score rules
semanticType: business_rule
synonyms:
  - account health
  - account health score
  - customer health score
  - health score
  - health status
  - at-risk accounts
  - critical accounts
  - poor health
  - accounts needing review
  - escalation review
  - review eligibility
  - renewal risk
---

# Account health score rules

This is a calculation rule, not a table or view. There is no account health score table to query: compute the score, status, review eligibility, and eligibility reason from the source tables listed below. Use it for questions about account health, at-risk or critical accounts, and which accounts need an escalation review.

The rule applies to High-priority accounts (Account.CustomerPriority__c = 'High') that have a matching warehouse record with a non-null MONTHLY_JOBS_L90.

All date math uses the fixed reference date 2026-07-16, never today's date.

Inputs and where they live:
- SLA tier: Salesforce_CRM.Salesforce.Account.SLA__c (Platinum, Gold, Silver, Bronze).
- Monthly jobs: Snowflake_WH.WH_DATA.DIM_ACCOUNT.MONTHLY_JOBS_L90, joined on Account.Ext_Account_Id__c = DIM_ACCOUNT.SFDC_ACCOUNT_ID.
- Days to renewal: days from 2026-07-16 to Account.ContractEndDate__c; negative means the contract has already ended.
- Annual contract value: Account.AnnualContractValue__c, in USD.
- Urgent open tickets: count of ServiceNow_ITSM.itsm.u_bm_incident rows where u_company = Account.Name, u_priority is 'Critical' or 'High', and u_state = 'Open'; 0 if none.

Health score: start at 100, then
- SLA tier: Platinum +10, Gold +5, Silver 0, Bronze −5.
- Monthly jobs: under 41 subtract 25; 41 to 150 subtract 10; over 150 subtract 0.
- Days to renewal: 30 or fewer (including negative) subtract 25; 31 to 90 subtract 10; more than 90 subtract 0.
- Urgent open tickets: subtract 5 per ticket, at most 25.

Health status: CRITICAL below 40, AT_RISK 40 to 59, MONITOR 60 to 79, HEALTHY 80 and above. Poor health means AT_RISK or CRITICAL.

Review eligibility: an account is ELIGIBLE if any of these holds, otherwise NOT ELIGIBLE: days to renewal is between 0 and 90 inclusive; annual contract value is 250,000 or more; urgent open tickets is 5 or more.

Eligibility reason: the first trigger that applies, checked in this order: "Renewal within 90 days", "ACV above review threshold", "High urgent ticket volume". If none applies: "No escalation trigger met".

Querying: these inputs live in three connections, so compute this in one statement built from subqueries in FROM, not WITH. WITH fails across connections with a misleading error, "The schema name 'WH_DATA' is invalid". See Connect AI cross-connection query rules for the rest.

## Related

- Account usage trend
- Connect AI cross-connection query rules
- Salesforce_CRM.Salesforce.Account
- Snowflake_WH.WH_DATA.DIM_ACCOUNT
- ServiceNow_ITSM.itsm.u_bm_incident
