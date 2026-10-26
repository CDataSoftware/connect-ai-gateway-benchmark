---
type: dataset
catalog: Salesforce_CRM
source: Salesforce
---

# Contact

Salesforce Contact object, queried as `[Salesforce_CRM].[Salesforce].[Contact]`. One row per person at a customer account. Not used by the Account health score or usage trend rules.

## Fields

### Id
Type: String. Salesforce Contact Id.

### AccountId
Type: String. The contact's account; equals Account.Id (the Salesforce Id, not Ext_Account_Id__c).

### FirstName
Type: String. First name.

### LastName
Type: String. Last name.

### Title
Type: String. Job title.

### Email
Type: String. Email address.

## Join hints

- Contact.AccountId = Account.Id
