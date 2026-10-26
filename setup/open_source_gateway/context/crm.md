# CRM data (Salesforce)

Query with salesforce-soqlQuery (SOQL). The inputs to the Account health score rules (see the Snowflake instructions) come from Account.

## Account

One row per customer account, with contract terms, SLA tier, and customer priority.

- Id (String): Salesforce Account Id.
- Name (String): account name; matches the ServiceNow company name.
- SLA__c (String): SLA tier: Platinum, Gold, Silver, or Bronze.
- CustomerPriority__c (String): High, Medium, or Low.
- AnnualContractValue__c (Double): annual contract value in USD.
- ContractEndDate__c (DateTime): contract end (renewal) date.
- Ext_Account_Id__c (String): external account id; joins to the warehouse (DIM_ACCOUNT.SFDC_ACCOUNT_ID).

## Contact

One row per person at a customer account. Not used by the Account health score or usage trend rules.

- Id (String): Salesforce Contact Id.
- AccountId (String): the contact's account; equals Account.Id (the Salesforce Id, not Ext_Account_Id__c).
- FirstName, LastName, Title, Email (String).

## Querying

- SOQL reads Salesforce only; it cannot join to Snowflake or ServiceNow. Combine results from the other systems yourself, using the keys in the Snowflake instructions.
- SOQL has no date arithmetic. Days to renewal are counted from the reference date 2026-07-16: day 30 is 2026-08-15 and day 90 is 2026-10-14.
