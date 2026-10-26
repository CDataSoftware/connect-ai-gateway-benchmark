---
type: dataset
catalog: Snowflake_WH
source: Snowflake
---

# TELEMETRY_EVENTS

Product usage events, queried as `[Snowflake_WH].[WH_DATA].[TELEMETRY_EVENTS]`. One row per usage event per account; sessions for the Account usage trend rules come from here. Filter time windows on EVENT_TIMESTAMP, not INGESTED_AT.

## Fields

### ACCOUNT_SK
Type: Number. Warehouse account key; joins to DIM_ACCOUNT.ACCOUNT_SK.

### EVENT_TIMESTAMP
Type: DateTime. When the usage happened; use this for date windows.

### SESSION_COUNT
Type: Number. Sessions in the event; sum it for session totals.

### EVENT_TYPE
Type: String. Kind of usage event.

### EVENT_SK
Type: Number. Event key.

### INGESTED_AT
Type: DateTime. When the event was loaded into the warehouse; not the usage time.

## Join hints

- TELEMETRY_EVENTS.ACCOUNT_SK = DIM_ACCOUNT.ACCOUNT_SK
