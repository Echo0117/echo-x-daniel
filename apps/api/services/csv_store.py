import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


def default_data_path(filename: str) -> Path:
    return Path(__file__).resolve().parents[1] / "data" / filename


def read_csv_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []

    with path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = []
        for row in reader:
            if not row or not any((value or "") != "" for value in row.values()):
                continue
            rows.append({
                key: (None if value == "null" else value)
                for key, value in row.items()
            })
        return rows


def append_csv_row(path: Path, fieldnames: Sequence[str], row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    if not write_header:
        _ensure_trailing_newline(path)

    with path.open("a", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        if write_header:
            writer.writeheader()
        writer.writerow({field: _csv_value(row.get(field)) for field in fieldnames})


def write_csv_rows(path: Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fieldnames})


def read_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []

    with path.open("r", encoding="utf-8") as jsonl_file:
        return [json.loads(line) for line in jsonl_file if line.strip()]


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _ensure_trailing_newline(path: Path) -> None:
    with path.open("rb+") as csv_file:
        csv_file.seek(-1, 2)
        last_byte = csv_file.read(1)
        if last_byte not in {b"\n", b"\r"}:
            csv_file.write(b"\n")
