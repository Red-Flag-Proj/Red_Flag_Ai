import argparse
import csv
import datetime as dt
import hashlib
import hmac
import os
from pathlib import Path
from typing import Iterable


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = BASE_DIR / "data" / "db_test_transactions_200.csv"
DEFAULT_OUTPUT_PATH = BASE_DIR / "data" / "db_test_transactions_200_masked.csv"
DEFAULT_DAY_OFFSET = 180
DEFAULT_AMOUNT_ROUNDING = 1000

REQUIRED_COLUMNS = [
    "transactionId",
    "customerRef",
    "customerName",
    "amount",
    "occurredAt",
    "countryCode",
    "city",
    "latitude",
    "longitude",
    "merchantId",
    "merchantCategory",
    "deviceId",
    "paymentMethod",
    "hour",
    "dayOfWeek",
    "isForeign",
    "isNewDevice",
    "isNewPaymentMethod",
    "isDawn",
    "label",
    "scenario",
]

OUTPUT_COLUMNS = REQUIRED_COLUMNS


def parse_args():
    parser = argparse.ArgumentParser(description="Mask DB test CSV for safe local import.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--day-offset", type=int, default=DEFAULT_DAY_OFFSET)
    parser.add_argument("--round-amount", action="store_true")
    parser.add_argument("--keep-coarse-location", action="store_true")
    parser.add_argument("--salt-env", default="FRAUDGUARD_MASKING_SALT")
    return parser.parse_args()


def read_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))

    missing = [column for column in REQUIRED_COLUMNS if not rows or column not in rows[0]]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    return rows


def require_salt(env_name: str) -> bytes:
    salt = os.environ.get(env_name, "").strip()
    if not salt:
        raise RuntimeError(f"Missing required salt. Set environment variable {env_name}.")
    return salt.encode("utf-8")


def stable_token(prefix: str, value: str, salt: bytes, length: int = 12) -> str:
    digest = hmac.new(salt, value.encode("utf-8"), hashlib.sha256).hexdigest().upper()
    return f"{prefix}_{digest[:length]}"


def stable_customer_name(customer_token: str, customer_index: int) -> str:
    suffix = customer_token.split("_", 1)[-1][:4]
    return f"Customer_{customer_index:04d}_{suffix}"


def parse_timestamp(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value)


def format_timestamp(value: dt.datetime) -> str:
    return value.replace(microsecond=0).isoformat(timespec="seconds")


def mask_amount(value: str, round_amount: bool) -> str:
    amount = float(value)
    if round_amount:
        amount = round(amount / DEFAULT_AMOUNT_ROUNDING) * DEFAULT_AMOUNT_ROUNDING
    if amount.is_integer():
        return str(int(amount))
    return f"{amount:.2f}"


def mask_location(row: dict, keep_coarse_location: bool) -> tuple[str, str]:
    if not keep_coarse_location:
        return "", ""
    latitude = row.get("latitude", "")
    longitude = row.get("longitude", "")
    if latitude in ("", None) or longitude in ("", None):
        return "", ""
    return f"{float(latitude):.2f}", f"{float(longitude):.2f}"


def recalculate_time_features(timestamp: dt.datetime) -> tuple[str, str, str]:
    hour = str(timestamp.hour)
    day_of_week = str(timestamp.weekday())
    is_dawn = "1" if timestamp.hour < 6 else "0"
    return hour, day_of_week, is_dawn


def ensure_columns(row: dict, required_columns: Iterable[str]) -> None:
    missing = [column for column in required_columns if column not in row]
    if missing:
        raise ValueError(f"Missing required columns in row: {', '.join(missing)}")


def mask_rows(rows: list[dict], day_offset: int, round_amount: bool, keep_coarse_location: bool, salt: bytes) -> list[dict]:
    customer_tokens: dict[str, str] = {}
    customer_names: dict[str, str] = {}
    masked_rows: list[dict] = []

    for row in rows:
        ensure_columns(row, REQUIRED_COLUMNS)

        customer_ref = row["customerRef"]
        if customer_ref not in customer_tokens:
            customer_tokens[customer_ref] = stable_token("CUST", customer_ref, salt)
        if customer_ref not in customer_names:
            customer_names[customer_ref] = stable_customer_name(
                customer_tokens[customer_ref],
                len(customer_names) + 1,
            )
        customer_token = customer_tokens[customer_ref]

        timestamp = parse_timestamp(row["occurredAt"]) + dt.timedelta(days=day_offset)
        hour, day_of_week, is_dawn = recalculate_time_features(timestamp)
        latitude, longitude = mask_location(row, keep_coarse_location)

        masked_rows.append(
            {
                "transactionId": stable_token("TX", row["transactionId"], salt),
                "customerRef": customer_token,
                "customerName": customer_names[customer_ref],
                "amount": mask_amount(row["amount"], round_amount),
                "occurredAt": format_timestamp(timestamp),
                "countryCode": row["countryCode"],
                "city": row["city"],
                "latitude": latitude,
                "longitude": longitude,
                "merchantId": stable_token("MER", row["merchantId"], salt),
                "merchantCategory": row["merchantCategory"],
                "deviceId": stable_token("DEV", row["deviceId"], salt),
                "paymentMethod": row["paymentMethod"],
                "hour": hour,
                "dayOfWeek": day_of_week,
                "isForeign": row["isForeign"],
                "isNewDevice": row["isNewDevice"],
                "isNewPaymentMethod": row["isNewPaymentMethod"],
                "isDawn": is_dawn,
                "label": row["label"],
                "scenario": row["scenario"],
            }
        )

    return masked_rows


def validate_masked_rows(rows: list[dict]) -> None:
    if not rows:
        raise ValueError("No rows produced.")

    forbidden_prefixes = ("SIM-", "Jang ", "Lee ", "Kim ", "Park ", "Hong ", "Choi ", "Seo ")
    for row in rows:
        for column in OUTPUT_COLUMNS:
            if column not in row:
                raise ValueError(f"Missing output column: {column}")
        for field in ("transactionId", "customerRef", "deviceId", "merchantId", "customerName"):
            value = str(row.get(field, ""))
            if any(value.startswith(prefix) for prefix in forbidden_prefixes):
                raise ValueError(f"Unmasked value detected in {field}: {value}")


def write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in OUTPUT_COLUMNS})


def main():
    args = parse_args()
    salt = require_salt(args.salt_env)
    rows = read_rows(args.input)
    masked_rows = mask_rows(rows, args.day_offset, args.round_amount, args.keep_coarse_location, salt)
    validate_masked_rows(masked_rows)
    write_rows(args.output, masked_rows)

    print(f"wrote {len(masked_rows)} rows to {args.output}")
    print(f"day_offset={args.day_offset}, round_amount={args.round_amount}, keep_coarse_location={args.keep_coarse_location}")


if __name__ == "__main__":
    main()
