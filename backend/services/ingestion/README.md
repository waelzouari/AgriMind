# Trusted ingestion service

AGM-012 consumes only canonical v1 telemetry and device-status MQTT messages.
It has no command publisher, pump port, GPIO dependency, Flutter API, ACK
ingestion, irrigation-result ingestion, or Storage responsibility.

## Trust flow

```text
Raspberry Pi -- per-device MQTT credential/ACL --> HiveMQ Cloud
HiveMQ Cloud -- QoS 1 persistent subscription --> ingestion service
ingestion service -- server-only service_role --> restricted PostgreSQL RPC
PostgreSQL -- AGM-011 RLS reads --> Flutter
```

The broker authenticates device principals and must enforce exact per-device
publish ACLs. MQTT 3.1.1 subscribers do not receive the original publisher's
username, so topic UUIDs are identifiers rather than authentication proof. The
service cross-checks topic and payload identity, then treats `devices.farm_id`
as authoritative and requires `devices.is_active`.

## Device registration

Install the service package in a trusted operator environment, create an
ignored environment file from `.env.example`, then use:

```bash
agrimind-device-registry --env-file /secure/path/ingestion.env register \
  --device-id 22222222-2222-4222-8222-222222222222 \
  --farm-id 11111111-1111-4111-8111-111111111111 \
  --label edge-1

agrimind-device-registry --env-file /secure/path/ingestion.env deactivate \
  --device-id 22222222-2222-4222-8222-222222222222
```

Registration requires an existing farm. Repeating the same device/farm is
idempotent; moving an existing UUID to another farm is a conflict. Deactivation
preserves history and immediately makes ingestion reject that device.

Broker provisioning remains separate. Give each edge device a unique broker
credential and only the exact AGM-006 ACLs for its farm/device topics. Raw MQTT
passwords are never stored in PostgreSQL. For revocation, deactivate the
registry record first, revoke the broker credential/ACL second, then verify the
old principal can no longer publish. Reactivation requires an intentionally
provisioned broker credential before the registry is activated.

## Run

```bash
agrimind-ingestion --env-file /secure/path/ingestion.env
```

The source checkout discovers the shared `contracts/v1` directory
automatically. A packaged deployment must deploy those unchanged schemas and
set `AGRIMIND_INGESTION_CONTRACT_ROOT` to their absolute directory.

The worker uses verified TLS, a stable MQTT client ID, persistent MQTT 3.1.1
session semantics, QoS 1, and manual acknowledgement. Permanent invalid input
is acknowledged and discarded. A temporary persistence failure is not
acknowledged; the client disconnects so the broker can redeliver. Exact
redelivery is a successful no-op through database `message_id` idempotency.

For telemetry, a terminal result also publishes a QoS 1, non-retained receipt
on `agrimind/v1/farms/{farm_id}/devices/{device_id}/sync/acks/{message_id}`.
`inserted` maps to `persisted`, an exact redelivery to `duplicate`, and a safely
correlatable permanent failure to `rejected`. The inbound message is broker-
acknowledged after the receipt PUBACK. Transient failures and uncorrelatable
invalid input publish no receipt. This remains an at-least-once design.

The trusted MQTT principal may publish the receipt wildcard. Each device may
subscribe only below its own exact farm/device receipt namespace and may never
publish a receipt.

Telemetry older than 24 hours or more than five minutes in the future is
rejected by default. Both limits are configurable operational validity rules,
not agronomic thresholds. Retained telemetry is rejected; retained device
status is expected.

HiveMQ Cloud persistent-session retention and outage behavior have not yet
been validated end to end. The implementation and fake-adapter tests must not
be presented as proof of guaranteed broker durability. AGM-008/009 remain the
edge offline/outbox authority; AGM-013 owns broader synchronization behavior.

The Supabase service-role key belongs only in this server runtime's secret
store. It is forbidden in Flutter, the Raspberry Pi, screenshots, logs,
examples with working values, or Git.
