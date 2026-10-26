---
type: dataset
catalog: Snowflake_WH
source: Snowflake
---

# DIM_ACCOUNT

Warehouse account dimension, queried as `[Snowflake_WH].[WH_DATA].[DIM_ACCOUNT]`. One row per customer account; it links Salesforce accounts to warehouse usage data. Monthly job volume for the Account health score rules comes from here.

## Fields

### ACCOUNT_SK
Type: Number. Warehouse account key; joins to TELEMETRY_EVENTS.ACCOUNT_SK.

### SFDC_ACCOUNT_ID
Type: String. Salesforce external account id; equals Account.Ext_Account_Id__c (not the Salesforce Account.Id).

### ACCOUNT_NAME
Type: String. Account name.

### MONTHLY_JOBS_L90
Type: Number. Monthly job volume over the trailing 90 days.

### ACTIVE_SEATS
Type: Number. Active licensed seats.

### PLAN_CODE
Type: String. Subscription plan.

## Join hints

- DIM_ACCOUNT.SFDC_ACCOUNT_ID = Account.Ext_Account_Id__c
- DIM_ACCOUNT.ACCOUNT_SK = TELEMETRY_EVENTS.ACCOUNT_SK
