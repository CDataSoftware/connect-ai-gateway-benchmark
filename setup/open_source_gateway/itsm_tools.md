# ITSM server tool specification

The tools the open-source gateway's ITSM server (alias `servicenow`) publishes. Build them as described in [`../README.md`](../README.md#itsm-server-alias-servicenow-for-example-servicenows-mcp-server-console), then rebuild each to this specification. It is what the ITSM server served from 2026-10-14 13:57 UTC on, which covers 348 of the 405 open-source gateway runs: each description is verbatim, as the model saw it, and those runs hid `list_aging_open_incidents` (see step 4 of the setup guide). The first 57 runs ran while the server was still being finalised (see [`docs/TEST_PLAN.md`](../../docs/TEST_PLAN.md#threats-to-validity)).

## Shared behaviour

- Every response is compact JSON: `{"result": ...}`, and list tools add `total` (all matching rows), `limit` and `offset`.
- `limit` is clamped to 1–200; `offset` to 0 or more. Defaults are in each tool's parameter table.
- `state`, `priority`, `category` and `assignment_group` filters accept one value or a comma-separated list and are case-sensitive. A value outside the valid set returns a tool error naming the bad value and listing the valid ones, for example `invalid priority ['Urgent']; valid values: Critical, High, Moderate, Low`.
- Days to resolve are fractional days between `opened_at` and `resolved_at`, rounded to one decimal place.
- Data comes from `u_bm_incident` (`sys_id`, `u_short_description`, `u_state`, `u_priority`, `u_category`, `u_assignment_group`, `u_company`, `u_company_sys_id`, `u_opened_at`, `u_resolved_at`, `u_reopen_count`) joined to `u_bm_company` (`sys_id`, `u_name`, `u_country`, `u_account_manager`) on `u_company_sys_id`. Tools are read-only.

## `get_support_portfolio_summary`

Description:

```text
Returns totals for the whole incident portfolio: total incidents, distinct companies, and incident counts broken down by state, priority, category and assignment group, plus open incidents by priority. Takes no parameters.
```

No parameters.

Returns: An object: `incidents` (total), `companies` (distinct company names on incidents), and four count maps keyed by value: `by_state`, `by_priority`, `by_category`, `by_assignment_group`, plus `open_by_priority` (open incidents only).

## `lookup_company`

Description:

```text
Finds companies whose name contains the given text (case-insensitive) and returns each company record (sys_id, name, country, account manager) with its total and open incident counts.

    Args:
        name_contains: Text to search for in the company name.
        limit: Rows per page, 1-200 (default 20).
        offset: Rows to skip, for paging (default 0).
```

| Parameter | Type | Default |
|---|---|---|
| `name_contains` | string | required |
| `limit` | integer | `20` |
| `offset` | integer | `0` |

Returns: A list of companies: `sys_id`, `name`, `country`, `account_manager`, `total_incidents`, `open_incidents`.

Order and matching: Name ascending. Matches `name_contains` anywhere in the name, case-insensitive.

## `get_incident`

Description:

```text
Retrieves one incident by its sys_id: short description, state, priority, category, assignment group, company (with country and account manager), opened and resolved timestamps, and reopen count. This instance has no INC number field; incidents are identified by sys_id.

    Args:
        incident_sys_id: The 32-character sys_id of the incident.
```

| Parameter | Type | Default |
|---|---|---|
| `incident_sys_id` | string | required |

Returns: One incident: `sys_id`, `short_description`, `state`, `priority`, `category`, `assignment_group`, `company`, `opened_at`, `resolved_at`, `reopen_count`, `company_country`, `company_account_manager`. An unknown sys_id returns `{"result": null, "error": "No incident with sys_id ..."}`.

## `search_incidents`

Description:

```text
Lists incidents matching any combination of filters, newest first. Every filter is optional. state, priority, category and assignment_group accept one value or a comma-separated list (e.g. "Critical,High").

    Args:
        company_name: Exact company name.
        state: Open or Closed.
        priority: Critical, High, Moderate or Low.
        category: Access, Database, Hardware, Network, Performance, Security or Software.
        assignment_group: DBA, L1-Support, L2-Support, Network-Ops or SecOps.
        opened_after: Only incidents opened on or after this date (YYYY-MM-DD).
        opened_before: Only incidents opened before this date (YYYY-MM-DD).
        limit: Rows per page, 1-200 (default 50).
        offset: Rows to skip, for paging (default 0).
```

| Parameter | Type | Default |
|---|---|---|
| `company_name` | string, optional | none |
| `state` | string, optional | none |
| `priority` | string, optional | none |
| `category` | string, optional | none |
| `assignment_group` | string, optional | none |
| `opened_after` | string, optional | none |
| `opened_before` | string, optional | none |
| `limit` | integer | `50` |
| `offset` | integer | `0` |

Returns: A list of incidents with the same fields as `get_incident`, without the two company fields.

Order and matching: `opened_at` descending, then `sys_id`. `company_name` is an exact match. `opened_after` is inclusive and `opened_before` exclusive.

## `get_company_ticket_profile`

Description:

```text
Returns a support profile for one company: country and account manager, total, open and closed incident counts, open and total counts by priority, reopened incidents, average and longest days to resolve for closed incidents, and first and last incident dates.

    Args:
        company_name: Exact company name.
```

| Parameter | Type | Default |
|---|---|---|
| `company_name` | string | required |

Returns: One company: `company`, `country`, `account_manager`, `total_incidents`, `open_incidents`, `closed_incidents`, `open_critical`, `open_high`, `open_moderate`, `open_low`, `total_critical`, `total_high`, `total_moderate`, `total_low`, `reopened_incidents` (incidents with a reopen count above zero), `avg_days_to_resolve` and `max_days_to_resolve` (closed incidents only), `first_incident` and `last_incident` (dates). An unknown name returns `{"result": null, "error": "No company named '...'; use lookup_company to find the right spelling."}`.

Order and matching: `company_name` is an exact match.

## `list_companies_by_open_incidents`

Description:

```text
Counts open incidents per company and lists companies with at least min_count of them, most first. Optionally counts only the given priorities (one value or a comma-separated list). Each row also gives the open count for each priority, total incidents, country and account manager.

    Args:
        priority: Priorities to count, e.g. "Critical" or "Critical,High". Omit to count all open incidents.
        min_count: Minimum number of matching open incidents a company must have (default 1).
        limit: Rows per page, 1-200 (default 50).
        offset: Rows to skip, for paging (default 0).
```

| Parameter | Type | Default |
|---|---|---|
| `priority` | string, optional | none |
| `min_count` | integer | `1` |
| `limit` | integer | `50` |
| `offset` | integer | `0` |

Returns: A list of companies: `company`, `country`, `account_manager`, `matching_open_incidents` (open incidents of the given priorities, or all open incidents), `open_critical`, `open_high`, `open_moderate`, `open_low`, `total_incidents`.

Order and matching: `matching_open_incidents` descending, then company name. Only companies with at least `min_count` (minimum 1) matching open incidents.

## `get_resolution_performance`

Description:

```text
Reports resolution performance by assignment group: total, open and closed counts, average, fastest and slowest days to resolve, closed incidents within and outside the target number of days, and reopened incidents. Optionally scoped to one company, assignment group or priority. Only closed incidents count toward the timing figures.

    Args:
        target_days: Resolution target in days (default 7).
        company_name: Exact company name.
        assignment_group: DBA, L1-Support, L2-Support, Network-Ops or SecOps.
        priority: Critical, High, Moderate or Low.
```

| Parameter | Type | Default |
|---|---|---|
| `target_days` | number | `7` |
| `company_name` | string, optional | none |
| `assignment_group` | string, optional | none |
| `priority` | string, optional | none |

Returns: A list with one row per assignment group: `assignment_group`, `total_incidents`, `open_incidents`, `closed_incidents`, `avg_days_to_resolve`, `min_days_to_resolve`, `max_days_to_resolve`, `closed_within_target`, `closed_outside_target`, `reopened_incidents`. The envelope also carries `target_days`. Not paged.

Order and matching: Assignment group ascending.

## `list_aging_open_incidents`

Description:

```text
Lists open incidents that have been open at least min_age_days as of a date, oldest first, with age in days, company, priority, category, assignment group and reopen count.

    Args:
        min_age_days: Minimum age in days (default 30).
        as_of_date: Date to measure age against, YYYY-MM-DD. Defaults to today.
        company_name: Exact company name.
        priority: Critical, High, Moderate or Low.
        assignment_group: DBA, L1-Support, L2-Support, Network-Ops or SecOps.
        limit: Rows per page, 1-200 (default 50).
        offset: Rows to skip, for paging (default 0).
```

| Parameter | Type | Default |
|---|---|---|
| `min_age_days` | integer | `30` |
| `as_of_date` | string, optional | none |
| `company_name` | string, optional | none |
| `priority` | string, optional | none |
| `assignment_group` | string, optional | none |
| `limit` | integer | `50` |
| `offset` | integer | `0` |

Returns: A list of open incidents with the same fields as `search_incidents`, plus `age_days` (whole days between the opened date and `as_of_date`). The envelope also carries `as_of_date`.

Order and matching: `age_days` descending, then `sys_id`. Only incidents at least `min_age_days` old.
