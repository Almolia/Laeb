# Alert rule (document only — Alertmanager optional)

## Rule: trading match cycle SLA

- **Metric:** `trading_match_cycle_duration_seconds` (emitted by trading-worker / B2)
- **Condition:** value `> 240` for 1 evaluation
- **Why:** Matching must finish inside the 5-minute window (NFR-05). Alert before cycles overlap.
- **Action:** page on-call / stop overlapping schedulers / scale trading-worker

Grafana panel is provisioned empty until B2 implements the metric; leave the panel in place.
