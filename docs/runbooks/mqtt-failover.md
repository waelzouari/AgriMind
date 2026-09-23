# MQTT failover runbook

HiveMQ Cloud remains primary. Local Mosquitto is used only when failover is
explicitly enabled and the configured failure threshold and delay are met.
Only one broker owns the pump-command subscription at a time.

| Scenario | State / broker | Telemetry and outbox | Commands, ACK, and pump safety |
|---|---|---|---|
| A Cloud available | `CLOUD_ACTIVE` / HiveMQ | Publish Cloud; mark delivered after PUBACK | Cloud subscription; normal handler and safety gate |
| B Cloud down, local up | `FAILOVER_PENDING` then `LOCAL_FALLBACK` | Persist Cloud-pending; mirror locally without marking Cloud delivered | Local subscription; same handler and processed-command register |
| C Both down | `OFFLINE` | Buffer in SQLite for at most 24 h | No MQTT command; local safety remains operational |
| D Cloud returns | `CLOUD_RECOVERY` then `CLOUD_ACTIVE` | Disconnect local, activate Cloud, drain pending after PUBACK | Local subscription removed before Cloud subscription |
| E Restart in fallback | Start from Cloud-first selection | Existing outbox remains pending | Stored commands are never executed; duplicates only replay ACKs |
| F Same command across brokers | Active broker only | ACK stays Cloud-pending if received locally | Exact duplicate does not actuate; changed payload conflicts |

## Supervised validation

1. Provision Mosquitto from `deploy/mosquitto/` with authentication and the
   exact farm/device ACL. Validate with `mosquitto -c ... -t`.
2. Start with Cloud reachable. Confirm retained ONLINE and the exact QoS 1
   pump subscription only on Cloud.
3. Block Cloud connectivity. Confirm `FAILOVER_PENDING`, then local activation
   only after the configured threshold and delay.
4. Publish one short, valid command locally using `FakePump`. Confirm accepted
   and completed ACKs locally and no second actuation.
5. Stop Mosquitto too. Confirm `OFFLINE` and increasing SQLite pending rows.
6. Restore Cloud. Confirm the stability window, local disconnect, Cloud
   subscription restoration, and ordered outbox drain.
7. Re-send the same `command_id` after the switch. Confirm ACK replay only.

Never run this procedure with the physical pump unless a separately supervised
hardware test has secured the water path. Logs and evidence must not include
credentials or payloads.
## Supervised AGM-013 recovery validation

Use `agrimind-offline-sync-validate --env-file .env` only with protected
runtime credentials and a disposable SQLite path. Observe the initial local
pending count and stable message IDs, interrupt Internet access, capture
telemetry, then restore connectivity. Confirm the original payloads replay,
AGM-012 logs `inserted` or `duplicate`, matching rows exist once in Supabase,
and the edge receives matching receipt topics. A repeated publication must
produce no second logical row and may return `duplicate`.

Record timestamps, outbox states, reconnect evidence, ingestion outcomes, and
final database rows. Never record credentials or raw environment files. This
demonstrates only the supervised scenario; it is not evidence of zero data
loss or exactly-once delivery. Keep the pump disconnected or use fake hardware.
