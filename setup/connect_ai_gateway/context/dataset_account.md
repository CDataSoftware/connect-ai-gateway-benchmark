---
type: dataset
catalog: Salesforce_CRM
source: Salesforce
---

# Account

Salesforce Account object, queried as `[Salesforce_CRM].[Salesforce].[Account]`. One row per customer account, with contract terms, SLA tier, and customer priority. The inputs to the Account health score rules come from here.

## Fields

### Id
Type: String. Salesforce Account Id.

### Name
Type: String. Account name; matches ServiceNow u_bm_incident.u_company.

### SLA__c
Type: String. SLA tier: Platinum, Gold, Silver, or Bronze.

### CustomerPriority__c
Type: String. High, Medium, or Low.

### AnnualContractValue__c
Type: Double. Annual contract value in USD.

### ContractEndDate__c
Type: DateTime. Contract end (renewal) date.

### Ext_Account_Id__c
Type: String. External account id; joins to the warehouse.

## Join hints

- Account.Ext_Account_Id__c = DIM_ACCOUNT.SFDC_ACCOUNT_ID
- Account.Name = u_bm_incident.u_company
