from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from agrimind_edge.adapters.hardware.pump import PumpRelay
from agrimind_edge.adapters.persistence import SqliteEventOutboxStore
from agrimind_edge.config import RuntimeConfig
from agrimind_edge.entrypoints import schedule as schedule_entrypoint
from agrimind_edge.entrypoints.schedule import _runtime, main, parse_utc

SCHEDULE_ID = UUID("33333333-3333-4333-8333-333333333333")


def env_file(tmp_path: Path, *, enabled: bool = False) -> Path:
    path = tmp_path / "schedule.env"
    database = (tmp_path / "edge.sqlite3").as_posix()
    path.write_text(
        "\n".join(
            [
                "AGRIMIND_FARM_ID=11111111-1111-4111-8111-111111111111",
                "AGRIMIND_DEVICE_ID=22222222-2222-4222-8222-222222222222",
                "AGRIMIND_MQTT_HOST=mqtt.example.invalid",
                "AGRIMIND_MQTT_TLS_ENABLED=false",
                "AGRIMIND_MQTT_USERNAME=user",
                "AGRIMIND_MQTT_PASSWORD=placeholder",  # pragma: allowlist secret
                f"AGRIMIND_SQLITE_PATH={database}",
                f"AGRIMIND_SCHEDULER_ENABLED={str(enabled).lower()}",
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_parse_utc_normalizes_offset_and_rejects_naive() -> None:
    assert parse_utc("2026-09-25T09:30:00+02:00") == datetime(2026, 9, 25, 7, 30, tzinfo=UTC)
    with pytest.raises(Exception, match="UTC offset"):
        parse_utc("2026-09-25T07:30:00")


def test_cli_create_list_and_disable_without_hardware(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    environment = env_file(tmp_path)
    future = datetime.now(UTC) + timedelta(hours=1)
    common = ["--env-file", str(environment)]

    assert (
        main(
            [
                *common,
                "create",
                "--at",
                future.isoformat(),
                "--duration-seconds",
                "30",
                "--schedule-id",
                str(SCHEDULE_ID),
            ]
        )
        == 0
    )
    created = capsys.readouterr().out
    assert f"schedule_id={SCHEDULE_ID}" in created
    assert "duration_seconds=30" in created
    assert "enabled=true" in created

    assert main([*common, "list"]) == 0
    listed = capsys.readouterr().out
    assert str(SCHEDULE_ID) in listed
    assert " 30 true -" in listed

    assert main([*common, "disable", str(SCHEDULE_ID)]) == 0
    assert "enabled=false" in capsys.readouterr().out
    assert main([*common, "list"]) == 0
    assert " 30 false -" in capsys.readouterr().out


@pytest.mark.parametrize("command", ["run", "tick"])
def test_cli_execution_fails_safe_when_scheduler_disabled(
    tmp_path: Path, command: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        schedule_entrypoint,
        "_runtime",
        lambda *_args: pytest.fail("disabled execution must not initialize hardware"),
    )
    assert main(["--env-file", str(env_file(tmp_path)), command]) == 3


def test_hardware_is_cleaned_if_store_initialization_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeRelay:
        initialized = False
        cleaned = False

        def initialize(self) -> None:
            self.initialized = True

        def cleanup(self) -> None:
            self.cleaned = True

    class FailingStore(SqliteEventOutboxStore):
        def initialize(self) -> None:
            raise RuntimeError("synthetic SQLite failure")

    relay = FakeRelay()
    monkeypatch.setattr(PumpRelay, "raspberry_pi", staticmethod(lambda _config: relay))
    config = RuntimeConfig.from_environment(
        {
            "AGRIMIND_FARM_ID": "11111111-1111-4111-8111-111111111111",
            "AGRIMIND_DEVICE_ID": "22222222-2222-4222-8222-222222222222",
            "AGRIMIND_MQTT_HOST": "mqtt.example.invalid",
            "AGRIMIND_MQTT_TLS_ENABLED": "false",
            "AGRIMIND_MQTT_USERNAME": "user",
            "AGRIMIND_MQTT_PASSWORD": "placeholder",  # pragma: allowlist secret
            "AGRIMIND_SQLITE_PATH": str(tmp_path / "edge.sqlite3"),
            "AGRIMIND_SCHEDULER_ENABLED": "true",
        }
    )

    with pytest.raises(RuntimeError, match="SQLite failure"):
        _runtime(config, FailingStore(tmp_path / "edge.sqlite3"))

    assert relay.initialized is True
    assert relay.cleaned is True
