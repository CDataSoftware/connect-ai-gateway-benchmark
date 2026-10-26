---
type: dataset
catalog: Snowflake_WH
source: Snowflake
---

# REVIEW_QUEUE

Escalation review queue, queried as `[Snowflake_WH].[WH_DATA].[REVIEW_QUEUE]`. One row per account queued for escalation review, with the reason it was queued. An account appears at most once.

## Fields

### ID
Type: Number. Queue entry id, assigned automatically.

### ACCOUNT_NAME
Type: String. Account queued for review; matches Account.Name.

### REASON
Type: String. The account's eligibility reason under the Account health score rules: the first trigger that applies, written exactly as one of "Renewal within 90 days", "ACV above review threshold", or "High urgent ticket volume".

### QUEUED_AT
Type: DateTime. When the entry was added, set automatically.

## Related

- Account health score rules
