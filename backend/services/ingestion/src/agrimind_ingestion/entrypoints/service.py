"""Run the trusted telemetry/status ingestion worker."""

from __future__ import annotations

import argparse
import logging
import os
import signal
from pathlib import Path
from threading import Event

from dotenv import dotenv_values

from agrimind_ingestion.adapters.mqtt import PahoIngestionConsumer
from agrimind_ingestion.adapters.supabase import (
    SupabaseIngestionRepository,
    SupabaseRegistryRepository,
    SupabaseRestClient,
)
from agrimind_ingestion.application.ingestion import IngestionService
from agrimind_ingestion.config import IngestionConfig
from agrimind_ingestion.contracts import ContractValidator


def load_environment(path: Path) -> dict[str, str]:
    values = dotenv_values(path)
    environment = {key: value for key, value in values.items() if value is not None}
    environment.update(os.environ)
    return environment


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    config = IngestionConfig.from_environment(load_environment(arguments.env_file))
    logging.basicConfig(level=os.environ.get("AGRIMIND_LOG_LEVEL", "INFO"))
    client = SupabaseRestClient(
        config.supabase_url,
        config.supabase_service_role_key.value,
    )
    processor = IngestionService(
        ContractValidator(config.contract_root),
        SupabaseRegistryRepository(client),
        SupabaseIngestionRepository(client),
        maximum_age=config.maximum_age,
        maximum_future_skew=config.maximum_future_skew,
    )
    consumer = PahoIngestionConsumer(
        host=config.mqtt_host,
        port=config.mqtt_port,
        client_id=config.mqtt_client_id,
        username=config.mqtt_username.value,
        password=config.mqtt_password.value,
        ca_file=config.mqtt_ca_file,
        processor=processor,
    )
    stopped = Event()

    def request_stop(signum: int, frame: object) -> None:
        del signum, frame
        stopped.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    consumer.start()
    try:
        stopped.wait()
    finally:
        consumer.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
