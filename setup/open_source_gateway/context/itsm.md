This server exposes the ServiceNow ITSM support system: customer support incidents and the companies they belong to. It is read-only and holds no CRM, contract, revenue or product-usage data.

Company names are exact and match the account names used in other systems. If a name returns nothing, use lookup_company to find the right spelling.

Valid field values (case-sensitive):
- state: Open, Closed
- priority: Critical, High, Moderate, Low
- category: Access, Database, Hardware, Network, Performance, Security, Software
- assignment_group: DBA, L1-Support, L2-Support, Network-Ops, SecOps

List tools return a page of results with total, limit and offset. Use offset to fetch the next page.
