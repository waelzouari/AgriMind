"""Trusted operator-only device registry CLI."""

from __future__ import annotations

import argparse
from pathlib import Path
from uuid import UUID

from agrimind_ingestion.adapters.supabase import SupabaseRegistryRepository, SupabaseRestClient
from agrimind_ingestion.application.device_registry import DeviceRegistryService
from agrimind_ingestion.config import IngestionConfig
from agrimind_ingestion.entrypoints.service import load_environment


def _uuid(value: str) -> UUID:
    parsed = UUID(value)
    if parsed.int == 0 or str(parsed) != value:
        raise argparse.ArgumentTypeError("must be a canonical non-zero UUID")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    register = commands.add_parser("register")
    register.add_argument("--device-id", type=_uuid, required=True)
    register.add_argument("--farm-id", type=_uuid, required=True)
    register.add_argument("--label")
    for name in ("get", "activate", "deactivate"):
        command = commands.add_parser(name)
        command.add_argument("--device-id", type=_uuid, required=True)
    label = commands.add_parser("set-label")
    label.add_argument("--device-id", type=_uuid, required=True)
    label.add_argument("--label")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    config = IngestionConfig.from_environment(load_environment(arguments.env_file))
    client = SupabaseRestClient(config.supabase_url, config.supabase_service_role_key.value)
    service = DeviceRegistryService(SupabaseRegistryRepository(client))
    if arguments.command == "register":
        result = service.register(arguments.device_id, arguments.farm_id, label=arguments.label)
    elif arguments.command == "get":
        registration = service.get(arguments.device_id)
        if registration is None:
            print("not_found")
            return 1
        print(
            f"found device_id={registration.device_id} farm_id={registration.farm_id} "
            f"active={str(registration.is_active).lower()}"
        )
        return 0
    elif arguments.command == "activate":
        result = service.activate(arguments.device_id)
    elif arguments.command == "deactivate":
        result = service.deactivate(arguments.device_id)
    else:
        result = service.update_label(arguments.device_id, arguments.label)
    registration = result.registration
    print(
        f"{result.outcome.value} device_id={registration.device_id} "
        f"farm_id={registration.farm_id} active={str(registration.is_active).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
