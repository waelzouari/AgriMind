"""Supervised AGM-006 validation against a configured cloud MQTT broker."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

from agrimind_edge import __version__
from agrimind_edge.adapters.fake import (
    FakeAirSensor,
    FakeDeviceStatusSource,
    FakeSoilSensor,
    FakeTankSensor,
)
from agrimind_edge.adapters.mqtt import PahoMqttTransport
from agrimind_edge.application import CloudMqttService, SensorService, TelemetryMapper
from agrimind_edge.application.mqtt_ports import MqttTransport
from agrimind_edge.config import RuntimeConfig
from agrimind_edge.contracts.enums import DeviceHealth, TelemetryMetric
from agrimind_edge.contracts.topics import TopicBuilder
from agrimind_edge.domain import DeviceRuntimeStatus, MqttConnectionState

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ValidationReport:
    wildcard_topic: str
    status_topic: str
    telemetry_topics: tuple[str, ...]
    mapped: int
    published: int


def load_runtime_config(env_file: Path) -> RuntimeConfig:
    """Load one dotenv file without mutating the process environment."""

    if not env_file.is_file():
        raise FileNotFoundError(f"environment file not found: {env_file}")
    parsed = dotenv_values(env_file, interpolate=False)
    environment: Mapping[str, str] = {
        key: value for key, value in parsed.items() if value is not None
    }
    return RuntimeConfig.from_environment(environment)


def wait_until_connected(
    service: CloudMqttService,
    timeout_seconds: float,
    *,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        if service.state is MqttConnectionState.CONNECTED:
            return True
        sleep(0.05)
    return service.state is MqttConnectionState.CONNECTED


def run_validation(
    config: RuntimeConfig,
    *,
    transport: MqttTransport | None = None,
    timeout_seconds: float = 15.0,
    wait_for_connection: Callable[[CloudMqttService, float], bool] = wait_until_connected,
) -> ValidationReport:
    """Publish one deterministic sensor cycle through the AGM-006 lifecycle."""

    if timeout_seconds <= 0:
        raise ValueError("connection timeout must be positive")

    topics = TopicBuilder(
        config.mqtt.farm_id,
        config.mqtt.device_id,
        config.mqtt.contract_version,
    )
    mqtt_transport = transport or PahoMqttTransport(config.mqtt, config.credentials)
    mapper = TelemetryMapper(config.mqtt.farm_id, config.mqtt.device_id)
    status_source = FakeDeviceStatusSource(
        DeviceRuntimeStatus(
            pump_state=False,
            health=DeviceHealth.HEALTHY,
            uptime_seconds=0,
            firmware_version=__version__,
        )
    )
    mqtt_service = CloudMqttService(mqtt_transport, mapper, topics, status_source)
    sensor_service = SensorService(
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

    mqtt_service.start()
    try:
        if not wait_for_connection(mqtt_service, timeout_seconds):
            raise TimeoutError("MQTT connection was not confirmed before the timeout")
        result = mqtt_service.publish_snapshot(sensor_service.capture())
        if result.published != result.mapped:
            raise RuntimeError("not all mapped telemetry was accepted by the MQTT client")
        return ValidationReport(
            wildcard_topic=f"{topics.base}/#",
            status_topic=topics.device_status(),
            telemetry_topics=tuple(
                topics.telemetry(metric)
                for metric in (
                    TelemetryMetric.TEMPERATURE,
                    TelemetryMetric.HUMIDITY,
                    TelemetryMetric.SOIL_MOISTURE,
                    TelemetryMetric.TANK_LEVEL,
                )
            ),
            mapped=result.mapped,
            published=result.published,
        )
    finally:
        mqtt_service.stop()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate AGM-006 telemetry against a configured MQTT broker."
    )
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--connection-timeout-seconds", type=float, default=15.0)
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(arguments)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        config = load_runtime_config(args.env_file)
        report = run_validation(
            config,
            timeout_seconds=args.connection_timeout_seconds,
        )
    except (FileNotFoundError, ValueError):
        _LOGGER.error("MQTT validation configuration is invalid")
        return 2
    except TimeoutError:
        _LOGGER.error("MQTT connection was not confirmed before timeout")
        return 3
    except Exception:
        _LOGGER.error("MQTT validation failed")
        return 4

    print(f"wildcard_topic={report.wildcard_topic}")
    print(f"status_topic={report.status_topic}")
    for topic in report.telemetry_topics:
        print(f"telemetry_topic={topic}")
    print(f"telemetry_published={report.published}/{report.mapped}")
    print("status_lifecycle=online_then_graceful_offline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
