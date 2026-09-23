"""Supervised AGM-013 telemetry synchronization runtime with fake sensors."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from agrimind_edge import __version__
from agrimind_edge.adapters.fake import (
    FakeAirSensor,
    FakeDeviceStatusSource,
    FakeSoilSensor,
    FakeTankSensor,
)
from agrimind_edge.adapters.mqtt import PahoMqttTransport
from agrimind_edge.adapters.persistence import SqliteEventOutboxStore
from agrimind_edge.application import (
    CloudMqttService,
    IngestionAcknowledgementProcessor,
    OutboxService,
    SensorService,
    TelemetryMapper,
)
from agrimind_edge.application.mqtt_ports import MqttTransport
from agrimind_edge.config import RuntimeConfig
from agrimind_edge.contracts import TopicBuilder
from agrimind_edge.contracts.enums import DeviceHealth
from agrimind_edge.domain import DeviceRuntimeStatus
from agrimind_edge.entrypoints.mqtt_validate import load_runtime_config, wait_until_connected

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class OfflineSyncRuntime:
    service: CloudMqttService
    sensors: SensorService
    store: SqliteEventOutboxStore
    topics: TopicBuilder


def build_offline_sync_runtime(
    config: RuntimeConfig,
    *,
    transport: MqttTransport | None = None,
    drain_submitter: Callable[[Callable[[], None]], None] | None = None,
) -> OfflineSyncRuntime:
    topics = TopicBuilder(
        config.mqtt.farm_id,
        config.mqtt.device_id,
        config.mqtt.contract_version,
    )
    mqtt_transport = transport or PahoMqttTransport(config.mqtt, config.credentials)
    store = SqliteEventOutboxStore(config.persistence.database_path)
    outbox = (
        OutboxService(store, mqtt_transport)
        if drain_submitter is None
        else OutboxService(store, mqtt_transport, drain_submitter=drain_submitter)
    )
    acknowledgement_processor = IngestionAcknowledgementProcessor(store, topics)
    service = CloudMqttService(
        mqtt_transport,
        TelemetryMapper(config.mqtt.farm_id, config.mqtt.device_id),
        topics,
        FakeDeviceStatusSource(DeviceRuntimeStatus(False, DeviceHealth.HEALTHY, 0, __version__)),
        ingestion_acknowledgement_handler=acknowledgement_processor.process,
        durable_publisher=outbox,
    )
    sensors = SensorService(
        FakeAirSensor([{"temperature": 24.5, "humidity_air": 62.0, "error": None}]),
        FakeSoilSensor([{"soil_humidity": 45.0, "soil_raw": 20_350, "error": None}]),
        FakeTankSensor(
            [
                {
                    "distance_cm": 8.0,
                    "water_level_cm": 20.0,
                    "water_pct": 66.7,
                    "error": None,
                }
            ]
        ),
    )
    return OfflineSyncRuntime(service, sensors, store, topics)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--connection-timeout-seconds", type=float, default=15.0)
    parser.add_argument("--receipt-wait-seconds", type=float, default=15.0)
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(arguments)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    runtime: OfflineSyncRuntime | None = None
    try:
        config = load_runtime_config(args.env_file)
        runtime = build_offline_sync_runtime(config)
        runtime.service.start()
        if not wait_until_connected(runtime.service, args.connection_timeout_seconds):
            raise TimeoutError("MQTT connection was not confirmed")
        result = runtime.service.publish_snapshot(runtime.sensors.capture())
        print(f"telemetry_broker_accepted={result.published}/{result.mapped}")
        print(f"ingestion_ack_subscription={runtime.topics.ingestion_acknowledgement_filter()}")
        time.sleep(max(0.0, args.receipt_wait_seconds))
        return 0
    except (FileNotFoundError, ValueError):
        _LOGGER.error("offline synchronization configuration is invalid")
        return 2
    except TimeoutError:
        _LOGGER.error("offline synchronization connection timed out")
        return 3
    except Exception:
        _LOGGER.error("offline synchronization validation failed")
        return 4
    finally:
        if runtime is not None:
            runtime.service.stop()
            runtime.store.close()


if __name__ == "__main__":
    sys.exit(main())
