---
type: dataset
catalog: ServiceNow_ITSM
source: ServiceNow
---

# u_bm_incident

ServiceNow support incidents, queried as `[ServiceNow_ITSM].[itsm].[u_bm_incident]`. One row per incident. Urgent open tickets for the Account health score rules are incidents with u_priority 'Critical' or 'High' and u_state 'Open'.

## Fields

### u_company
Type: String. Customer company name; equals Account.Name.

### u_priority
Type: String. Critical, High, Moderate, or Low.

### u_state
Type: String. Open or Closed.

### u_company_sys_id
Type: String. Company record id; equals u_bm_company.sys_id.

### u_category
Type: String. Incident category.

### u_short_description
Type: String. Short summary of the incident.

### u_opened_at
Type: DateTime. When the incident was opened.

### u_resolved_at
Type: DateTime. When the incident was resolved; empty while open.

## Join hints

- u_bm_incident.u_company = Account.Name
- u_bm_incident.u_company_sys_id = u_bm_company.sys_id
