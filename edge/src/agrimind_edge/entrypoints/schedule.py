"""Local CLI for one-shot scheduled irrigation."""

from __future__ import annotations

import argparse
import logging
import signal
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from uuid import UUID

from dotenv import dotenv_values

from agrimind_edge.adapters.persistence import SqliteEventOutboxStore
from agrimind_edge.application.clock import SystemUtcClock
from agrimind_edge.application.pump_command_handler import PumpCommandHandler
from agrimind_edge.application.pump_controller import SafePumpController
from agrimind_edge.application.scheduled_irrigation import (
    DuplicateScheduleError,
    ScheduledIrrigationRunner,
    ScheduledIrrigationService,
    ScheduleNotFoundError,
    ScheduleTooOldError,
)
from agrimind_edge.config import RuntimeConfig

_LOGGER = logging.getLogger(__name__)


def parse_utc(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise argparse.ArgumentTypeError("timestamp must be valid ISO-8601") from error
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("timestamp must include a UTC offset")
    return parsed.astimezone(UTC)


def load_config(env_file: Path) -> RuntimeConfig:
    if not env_file.is_file():
        raise FileNotFoundError(f"environment file not found: {env_file}")
    values = dotenv_values(env_file, interpolate=False)
    environment: Mapping[str, str] = {
        key: value for key, value in values.items() if value is not None
    }
    return RuntimeConfig.from_environment(environment)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage local one-shot irrigation schedules.")
    parser.add_argument("--env-file", required=True, type=Path)
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser(
        "create",
        help="Create one local one-shot schedule.",
        description="Persist one local one-shot UTC irrigation schedule without using hardware.",
    )
    create.add_argument("--at", required=True, type=parse_utc)
    create.add_argument("--duration-seconds", required=True, type=int)
    create.add_argument("--schedule-id", type=UUID)

    commands.add_parser(
        "list",
        help="List local schedules.",
        description="List local schedules and occurrence states without using hardware.",
    )
    disable = commands.add_parser(
        "disable",
        help="Soft-disable one schedule.",
        description="Soft-disable one local schedule; this does not stop an active pump.",
    )
    disable.add_argument("schedule_id", type=UUID)
    commands.add_parser(
        "run",
        help="Run the enabled local scheduler until stopped.",
        description="Run the enabled scheduler; due schedules may actuate the configured pump.",
    )
    commands.add_parser(
        "tick",
        help="Process due schedules once; may actuate the configured pump.",
        description="Process due schedules once; may actuate the configured pump.",
    )
    return parser


def _admin_service(
    config: RuntimeConfig, store: SqliteEventOutboxStore
) -> ScheduledIrrigationService:
    return ScheduledIrrigationService(
        store,
        None,
        SystemUtcClock(),
        farm_id=config.pump_safety.farm_id,
        device_id=config.pump_safety.device_id,
        max_lateness_seconds=config.scheduler.max_lateness_seconds,
    )


def _runtime(
    config: RuntimeConfig, store: SqliteEventOutboxStore
) -> tuple[ScheduledIrrigationRunner, SafePumpController]:
    # Hardware-only imports and construction stay inside the explicit run/tick path.
    from agrimind_edge.adapters.hardware.pump import PumpRelay
    from agrimind_edge.adapters.scheduling import ThreadingScheduler

    pump = PumpRelay.raspberry_pi(config.hardware)
    pump.initialize()
    controller: SafePumpController | None = None
    try:
        store.initialize()
        controller = SafePumpController(pump, ThreadingScheduler())
        handler = PumpCommandHandler(
            controller,
            config.pump_safety,
            processed_command_store=store,
        )
        service = ScheduledIrrigationService(
            store,
            handler,
            SystemUtcClock(),
            farm_id=config.pump_safety.farm_id,
            device_id=config.pump_safety.device_id,
            max_lateness_seconds=config.scheduler.max_lateness_seconds,
        )
        service.recover()
        return (
            ScheduledIrrigationRunner(
                service,
                enabled=config.scheduler.enabled,
                poll_interval_seconds=config.scheduler.poll_interval_seconds,
            ),
            controller,
        )
    except Exception:
        try:
            if controller is not None:
                controller.shutdown()
            else:
                pump.cleanup()
        finally:
            store.close()
        raise


def main(arguments: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(arguments)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        config = load_config(args.env_file)
        store = SqliteEventOutboxStore(config.persistence.database_path)
    except (FileNotFoundError, ValueError, RuntimeError):
        _LOGGER.error("schedule_configuration_invalid")
        return 2

    controller: SafePumpController | None = None
    try:
        if args.command in {"run", "tick"}:
            if not config.scheduler.enabled:
                _LOGGER.error("scheduler_disabled")
                return 3
            runner, controller = _runtime(config, store)
            if args.command == "tick":
                print(f"processed={len(runner.tick())}")
            else:
                stop_event = Event()

                def stop(_signum: int, _frame: object) -> None:
                    stop_event.set()

                signal.signal(signal.SIGINT, stop)
                signal.signal(signal.SIGTERM, stop)
                runner.run(stop_event)
            return 0

        store.initialize()
        service = _admin_service(config, store)
        if args.command == "create":
            schedule = service.create_schedule(
                args.at,
                args.duration_seconds,
                schedule_id=args.schedule_id,
            )
            print(f"schedule_id={schedule.schedule_id}")
            print(f"scheduled_for={schedule.scheduled_for.isoformat().replace('+00:00', 'Z')}")
            print(f"duration_seconds={schedule.duration_seconds}")
            print(f"enabled={str(schedule.enabled).lower()}")
        elif args.command == "list":
            print("ID UTC_TIME DURATION_SECONDS ENABLED OCCURRENCE_STATUS")
            for summary in service.list_schedules():
                schedule = summary.schedule
                status = summary.occurrence_status.value if summary.occurrence_status else "-"
                instant = schedule.scheduled_for.isoformat().replace("+00:00", "Z")
                print(
                    f"{schedule.schedule_id} {instant} {schedule.duration_seconds} "
                    f"{str(schedule.enabled).lower()} {status}"
                )
        elif args.command == "disable":
            service.disable_schedule(args.schedule_id)
            print(f"schedule_id={args.schedule_id}")
            print("enabled=false")
    except (
        DuplicateScheduleError,
        ScheduleNotFoundError,
        ScheduleTooOldError,
        ValueError,
    ) as error:
        _LOGGER.error(str(error))
        return 4
    except Exception:
        _LOGGER.error("schedule_operation_failed")
        return 5
    finally:
        if controller is not None:
            try:
                controller.shutdown()
            except Exception:
                _LOGGER.error("pump_safe_shutdown_failed")
        store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
