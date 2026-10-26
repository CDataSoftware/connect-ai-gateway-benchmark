---
type: dataset
catalog: ServiceNow_ITSM
source: ServiceNow
---

# u_bm_company

ServiceNow customer companies, queried as `[ServiceNow_ITSM].[itsm].[u_bm_company]`. One row per company. Not needed to link incidents to accounts: u_bm_incident.u_company already holds the account name.

## Fields

### sys_id
Type: String. Company record id.

### u_name
Type: String. Company name; equals Account.Name.

### u_country
Type: String. Country.

### u_account_manager
Type: String. Assigned account manager.

## Join hints

- u_bm_company.sys_id = u_bm_incident.u_company_sys_id
- u_bm_company.u_name = Account.Name
