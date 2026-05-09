import argparse
import csv
from pathlib import Path

from mask_test_data import OUTPUT_COLUMNS, parse_timestamp, recalculate_time_features


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = BASE_DIR / "data" / "db_test_transactions_200_masked.csv"

EXPECTED_PREFIXES = {
    "transactionId": "TX_",
    "customerRef": "CUST_",
    "customerName": "Customer_",
    "merchantId": "MER_",
    "deviceId": "DEV_",
}

FORBIDDEN_PREFIXES = (
    "SIM-",
    "CUST-",
    "DEV-",
    "MER-",
    "online-",
    "offline-",
    "mobile-",
    "web-",
)


def parse_args():
    parser = argparse.ArgumentParser(description="Validate a masked CSV before backend/API ingestion.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--allow-coarse-location", action="store_true")
    return parser.parse_args()


def read_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames != OUTPUT_COLUMNS:
            raise ValueError(f"Unexpected schema. Expected: {', '.join(OUTPUT_COLUMNS)}")
        return list(reader)


def validate_rows(rows: list[dict], allow_coarse_location: bool) -> None:
    if not rows:
        raise ValueError("No rows found.")

    for index, row in enumerate(rows, start=2):
        for field, prefix in EXPECTED_PREFIXES.items():
            value = row.get(field, "")
            if not value.startswith(prefix):
                raise ValueError(f"Line {index}: {field} is not masked: {value}")
            if any(value.startswith(forbidden) for forbidden in FORBIDDEN_PREFIXES):
                raise ValueError(f"Line {index}: raw-looking value in {field}: {value}")

        if not allow_coarse_location and (row.get("latitude") or row.get("longitude")):
            raise ValueError(f"Line {index}: location columns must be empty by default.")

        try:
            timestamp = parse_timestamp(row["occurredAt"])
        except ValueError as exc:
            raise ValueError(f"Line {index}: invalid occurredAt value: {row['occurredAt']}") from exc

        hour, day_of_week, is_dawn = recalculate_time_features(timestamp)
        if row["hour"] != hour or row["dayOfWeek"] != day_of_week or row["isDawn"] != is_dawn:
            raise ValueError(f"Line {index}: time-derived columns do not match occurredAt.")


def main():
    args = parse_args()
    rows = read_rows(args.input)
    validate_rows(rows, args.allow_coarse_location)
    print(f"validated {len(rows)} masked rows for backend/API ingestion candidate: {args.input}")


if __name__ == "__main__":
    main()
