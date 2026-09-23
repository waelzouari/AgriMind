"""Supervised AGM-007 HiveMQ validation using fake pump hardware."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from agrimind_edge import __version__
from agrimind_edge.adapters.fake import FakePump, FakeScheduler
from agrimind_edge.adapters.mqtt import PahoMqttTransport
from agrimind_edge.application import (
    CloudMqttService,
    MqttAcknowledgementPublisher,
    MqttPumpCommandProcessor,
    PumpCommandHandler,
    SafePumpController,
    TelemetryMapper,
)
from agrimind_edge.application.mqtt_ports import MqttTransport
from agrimind_edge.config import RuntimeConfig
from agrimind_edge.contracts import PumpCommand
from agrimind_edge.contracts.enums import DeviceHealth, PumpAction
from agrimind_edge.contracts.topics import TopicBuilder
from agrimind_edge.domain import DeviceRuntimeStatus
from agrimind_edge.entrypoints.mqtt_validate import load_runtime_config, wait_until_connected

_LOGGER = logging.getLogger(__name__)


class _FakePumpStatusSource:
    def __init__(self, pump: FakePump, started_at: float) -> None:
        self._pump = pump
        self._started_at = started_at

    def read_status(self) -> DeviceRuntimeStatus:
        return DeviceRuntimeStatus(
            pump_state=self._pump.active,
            health=DeviceHealth.HEALTHY,
            uptime_seconds=max(0, int(time.monotonic() - self._started_at)),
            firmware_version=__version__,
        )


@dataclass(frozen=True, slots=True)
class ControlValidationRuntime:
    service: CloudMqttService
    controller: SafePumpController
    pump: FakePump
    scheduler: FakeScheduler
    topics: TopicBuilder


def build_control_validation_runtime(
    config: RuntimeConfig,
    *,
    transport: MqttTransport | None = None,
    clock: Callable[[], datetime] | None = None,
) -> ControlValidationRuntime:
    """Compose AGM-003/005/006/007 with deterministic fake hardware."""

    runtime_clock = clock or (lambda: datetime.now(UTC))
    topics = TopicBuilder(
        config.mqtt.farm_id,
        config.mqtt.device_id,
        config.mqtt.contract_version,
    )
    mqtt_transport = transport or PahoMqttTransport(config.mqtt, config.credentials)
    pump = FakePump()
    scheduler = FakeScheduler()
    controller = SafePumpController(pump, scheduler)
    acknowledgement_publisher = MqttAcknowledgementPublisher(mqtt_transport, topics)
    command_handler = PumpCommandHandler(
        controller,
        config.pump_safety,
        clock=runtime_clock,
        acknowledgement_sink=acknowledgement_publisher.publish,
    )
    processor = MqttPumpCommandProcessor(
        command_handler,
        acknowledgement_publisher,
        topics,
        clock=runtime_clock,
    )
    service = CloudMqttService(
        mqtt_transport,
        TelemetryMapper(config.mqtt.farm_id, config.mqtt.device_id),
        topics,
        _FakePumpStatusSource(pump, time.monotonic()),
        command_message_handler=processor.process,
        clock=runtime_clock,
    )
    return ControlValidationRuntime(service, controller, pump, scheduler, topics)


def run_pending_fake_schedules(
    scheduler: FakeScheduler,
    deadlines: dict[int, float],
    *,
    monotonic: Callable[[], float] = time.monotonic,
) -> None:
    now = monotonic()
    for call in scheduler.calls:
        if call.cancelled or call.fired:
            continue
        key = id(call)
        deadline = deadlines.setdefault(key, now + call.delay_seconds)
        if now >= deadline:
            call.fire()


def sample_on_command(config: RuntimeConfig, *, now: datetime | None = None) -> str:
    issued_at = now or datetime.now(UTC)
    return PumpCommand(
        command_id=uuid4(),
        farm_id=config.mqtt.farm_id,
        device_id=config.mqtt.device_id,
        action=PumpAction.ON,
        duration_seconds=5,
        issued_at=issued_at,
        expires_at=issued_at + timedelta(minutes=2),
        requested_by=uuid4(),
    ).to_json()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate AGM-007 remote control against a configured MQTT broker."
    )
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--connection-timeout-seconds", type=float, default=15.0)
    parser.add_argument("--run-seconds", type=float, default=120.0)
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(arguments)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.run_seconds <= 0:
        _LOGGER.error("control validation duration must be positive")
        return 2
    try:
        config = load_runtime_config(args.env_file)
        runtime = build_control_validation_runtime(config)
    except (FileNotFoundError, ValueError):
        _LOGGER.error("MQTT control validation configuration is invalid")
        return 2

    runtime.service.start()
    try:
        if not wait_until_connected(runtime.service, args.connection_timeout_seconds):
            _LOGGER.error("MQTT connection was not confirmed before timeout")
            return 3
        print(f"command_topic={runtime.topics.pump_command()}")
        print(f"ack_subscription={runtime.topics.base}/acks/#")
        print(f"sample_on_command={sample_on_command(config)}")
        print("fake_pump=true")
        deadlines: dict[int, float] = {}
        end = time.monotonic() + args.run_seconds
        while time.monotonic() < end:
            run_pending_fake_schedules(runtime.scheduler, deadlines)
            time.sleep(0.05)
    except KeyboardInterrupt:
        _LOGGER.info("MQTT control validation interrupted")
    finally:
        try:
            runtime.controller.shutdown()
        except Exception:
            _LOGGER.error("fake pump shutdown failed")
        runtime.service.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
