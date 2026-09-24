from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import pytest

from agrimind_irrigation.audit import audit_dataset
from agrimind_irrigation.contract import load_contract

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = load_contract(ROOT / "data_contracts" / "feature-contract-v1.json")
VALID = ROOT / "tests" / "fixtures" / "valid.csv"


def write_fixture(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "fixture.csv"
    path.write_text(body, encoding="utf-8")
    return path


def audit_fixture(path: Path):  # type: ignore[no-untyped-def]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return audit_dataset(CONTRACT, path, expected_sha256=digest)


def write_minimal_xlsx(tmp_path: Path) -> Path:
    path = tmp_path / "fixture.xlsx"
    spreadsheet_namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    relationship_namespace = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    workbook = f"""<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="{spreadsheet_namespace}" xmlns:r="{relationship_namespace}">
 <workbookPr date1904="1"/><sheets><sheet name="smart irrigation" sheetId="1" r:id="rId1"/></sheets>
</workbook>"""
    worksheet_relationship = f"{relationship_namespace}/worksheet"
    relationships = f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Id="rId1" Type="{worksheet_relationship}"
  Target="/xl/worksheets/sheet1.xml"/>
</Relationships>"""
    headers = (
        "Time",
        "crop type",
        "Temperature",
        "Humidity",
        "Soil Moisture",
        "Soil Tempertuer",
        "irrigation",
        "best time",
    )
    header_cells = "".join(
        f'<c r="{chr(65 + index)}1" t="inlineStr"><is><t>{header}</t></is></c>'
        for index, header in enumerate(headers)
    )

    def numeric_row(row_number: int, values: tuple[float, ...]) -> str:
        cells = "".join(
            f'<c r="{chr(65 + index)}{row_number}"><v>{value}</v></c>'
            for index, value in enumerate(values)
        )
        return f'<row r="{row_number}">{cells}</row>'

    rows = (
        f'<row r="1">{header_cells}<c r="L1"/></row>'
        + numeric_row(2, (45000, 1, 22, 60, 45, 18, 0, 0))
        + numeric_row(3, (45000.0020833333, 2, 24, 55, 30, 19, 1, 0))
    )
    sheet = f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="{spreadsheet_namespace}">
 <sheetData>
  {rows}
 </sheetData>
</worksheet>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", relationships)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return path


def test_valid_synthetic_fixture_is_deterministic_and_not_mutated() -> None:
    before = VALID.read_bytes()

    first = audit_fixture(VALID)
    second = audit_fixture(VALID)

    assert first == second
    assert first.structurally_valid
    assert first.row_count == 2
    assert first.target_counts == {"0": 1, "1": 1}
    assert first.invalid_training_rows == 0
    assert first.known_leakage_columns == ("best time",)
    assert VALID.read_bytes() == before


def test_minimal_xlsx_and_csv_apply_the_same_logical_contract(tmp_path: Path) -> None:
    csv_report = audit_fixture(VALID)
    xlsx_report = audit_fixture(write_minimal_xlsx(tmp_path))

    assert xlsx_report.columns == csv_report.columns
    assert xlsx_report.row_count == csv_report.row_count
    assert xlsx_report.missing_counts == csv_report.missing_counts
    assert xlsx_report.target_counts == csv_report.target_counts
    assert xlsx_report.invalid_training_rows == csv_report.invalid_training_rows
    assert xlsx_report.known_leakage_columns == csv_report.known_leakage_columns
    assert xlsx_report.feature_target_duplicate_rows == csv_report.feature_target_duplicate_rows


def test_malformed_xlsx_has_safe_error(tmp_path: Path) -> None:
    path = tmp_path / "malformed.xlsx"
    path.write_bytes(b"not a zip and private-row-value")

    with pytest.raises(ValueError, match="not a readable XLSX package") as error:
        audit_dataset(CONTRACT, path, expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest())

    assert "private-row-value" not in str(error.value)


@pytest.mark.parametrize(
    ("source", "replacement", "expected_type", "expected_range", "expected_target"),
    [
        (",45,18,0,0", ",,18,0,0", 0, 0, 0),
        (",45,18,0,0", ",bad,18,0,0", 1, 0, 0),
        (",45,18,0,0", ",101,18,0,0", 0, 1, 0),
        (",45,18,0,0", ",NaN,18,0,0", 1, 0, 0),
        (",45,18,0,0", ",Infinity,18,0,0", 1, 0, 0),
        (",45,18,0,0", ",45,18,,0", 0, 0, 1),
        (",45,18,0,0", ",45,18,2,0", 0, 0, 1),
    ],
)
def test_invalid_rows_are_counted_without_preprocessing(
    tmp_path: Path,
    source: str,
    replacement: str,
    expected_type: int,
    expected_range: int,
    expected_target: int,
) -> None:
    content = VALID.read_text(encoding="utf-8").replace(source, replacement, 1)
    report = audit_fixture(write_fixture(tmp_path, content))

    assert report.invalid_training_rows == 1
    assert report.invalid_type_counts["soil_moisture_index_0_100"] == expected_type
    assert report.invalid_range_counts["soil_moisture_index_0_100"] == expected_range
    assert report.invalid_target_count == expected_target


def test_missing_required_column_and_unexpected_column_are_structural_errors(
    tmp_path: Path,
) -> None:
    content = VALID.read_text(encoding="utf-8").replace("Humidity,", "unexpected,")
    report = audit_fixture(write_fixture(tmp_path, content))

    assert not report.structurally_valid
    assert report.missing_required_columns == ("Humidity",)
    assert report.unexpected_columns == ("unexpected",)


def test_duplicates_are_reported_but_not_removed(tmp_path: Path) -> None:
    lines = VALID.read_text(encoding="utf-8").splitlines()
    report = audit_fixture(write_fixture(tmp_path, "\n".join([*lines, lines[1]]) + "\n"))

    assert report.row_count == 3
    assert report.exact_duplicate_rows == 1
    assert report.duplicates_without_time == 1
    assert report.feature_target_duplicate_rows == 1


def test_fingerprint_mismatch_is_structural_error() -> None:
    report = audit_dataset(CONTRACT, VALID, expected_sha256="0" * 64)

    assert not report.fingerprint_matches
    assert not report.structurally_valid


def test_error_does_not_echo_dataset_content(tmp_path: Path) -> None:
    secret_marker = "fixture-private-value"  # pragma: allowlist secret
    path = tmp_path / "unsupported.txt"
    path.write_text(secret_marker, encoding="utf-8")

    with pytest.raises(ValueError, match="supported dataset formats") as error:
        audit_dataset(CONTRACT, path, expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest())

    assert secret_marker not in str(error.value)
