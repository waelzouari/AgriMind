from pathlib import Path

from scripts.check_repository import (
    validate_environment_example,
    validate_relative_markdown_links,
)


def test_environment_example_rejects_privileged_key_name(tmp_path: Path) -> None:
    example = tmp_path / ".env.example"
    example.write_text(
        "AGRIMIND_SERVICE_ROLE=forbidden\n"
        "MQTT_PASSWORD=replace-at-deployment\n"  # pragma: allowlist secret
        "ANON_KEY=replace-with-public-anon-key\n",  # pragma: allowlist secret
        encoding="utf-8",
    )

    assert validate_environment_example(example) == [
        "forbidden variable name in .env.example: SERVICE_ROLE"
    ]


def test_markdown_link_check_reports_missing_relative_target(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("[missing](docs/missing.md)\n", encoding="utf-8")

    assert validate_relative_markdown_links(tmp_path) == [
        "README.md: broken link docs/missing.md"
    ]
