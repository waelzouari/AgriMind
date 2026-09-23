from pathlib import Path

import pytest

from agrimind_ingestion.config import IngestionConfig
from agrimind_ingestion.entrypoints.service import load_environment


def environment() -> dict[str, str]:
    return {
        "AGRIMIND_INGESTION_MQTT_HOST": "mqtt.example.invalid",
        "AGRIMIND_INGESTION_MQTT_CLIENT_ID": "agrimind-ingestion-test",
        "AGRIMIND_INGESTION_MQTT_USERNAME": "server-user-secret",
        "AGRIMIND_INGESTION_MQTT_PASSWORD": "server-password-secret",  # pragma: allowlist secret
        "AGRIMIND_INGESTION_MQTT_CA_FILE": "/etc/ssl/cert.pem",
        "AGRIMIND_INGESTION_SUPABASE_URL": "https://example.supabase.co",
        "AGRIMIND_INGESTION_SUPABASE_SERVICE_ROLE_KEY": "service-role-secret",
    }


def test_configuration_defaults_and_repr_redact_every_secret() -> None:
    config = IngestionConfig.from_environment(environment())

    assert config.maximum_age.total_seconds() == 86_400
    assert config.maximum_future_skew.total_seconds() == 300
    assert config.mqtt_ca_file == Path("/etc/ssl/cert.pem")
    rendered = repr(config)
    assert "server-user-secret" not in rendered
    assert "server-password-secret" not in rendered
    assert "service-role-secret" not in rendered
    assert rendered.count("***") == 3


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("AGRIMIND_INGESTION_MQTT_HOST", "https://broker", "scheme"),
        ("AGRIMIND_INGESTION_MQTT_PORT", "70000", "between"),
        ("AGRIMIND_INGESTION_MQTT_CA_FILE", "relative.pem", "absolute"),
        ("AGRIMIND_INGESTION_SUPABASE_URL", "http://unsafe", "HTTPS"),
        ("AGRIMIND_INGESTION_MAXIMUM_AGE_SECONDS", "0", "positive"),
        ("AGRIMIND_INGESTION_MAXIMUM_FUTURE_SKEW_SECONDS", "-1", "negative"),
    ],
)
def test_invalid_configuration_fails_before_connect(key: str, value: str, message: str) -> None:
    values = environment()
    values[key] = value
    with pytest.raises(ValueError, match=message):
        IngestionConfig.from_environment(values)


def test_process_environment_takes_precedence_over_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "ingestion.env"
    path.write_text("KEY=file-value\n", encoding="utf-8")
    monkeypatch.setenv("KEY", "runtime-secret-store-value")

    assert load_environment(path)["KEY"] == "runtime-secret-store-value"
