import argparse
import csv
import datetime as dt
import hashlib
import hmac
import json
import os
import getpass
from pathlib import Path
from typing import Iterable


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = BASE_DIR / "data" / "db_test_transactions_200.csv"
DEFAULT_OUTPUT_PATH = BASE_DIR / "data" / "db_test_transactions_200_masked.csv"
DEFAULT_AUDIT_LOG_PATH = BASE_DIR / "data" / "masking_audit.jsonl"
DEFAULT_DAY_OFFSET = 180
DEFAULT_AMOUNT_ROUNDING = 1000
DEFAULT_POLICY_VERSION = "fg-dev-data-security-v1"
LOCAL_ENVIRONMENT = "local-dev"
NONLOCAL_ENVIRONMENTS = {"shared-dev", "qa-staging", "production-like-test"}

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
    parser = argparse.ArgumentParser(description="Mask backend/API test CSV for safe local ingestion candidate use.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--day-offset", type=int, default=DEFAULT_DAY_OFFSET)
    parser.add_argument("--amount-policy", choices=("keep", "round"), default="keep")
    parser.add_argument("--location-policy", choices=("remove", "coarse"), default="remove")
    parser.add_argument("--round-amount", action="store_true", help="Legacy alias for --amount-policy round.")
    parser.add_argument("--keep-coarse-location", action="store_true", help="Legacy alias for --location-policy coarse.")
    parser.add_argument("--salt-env", default="FRAUDGUARD_MASKING_SALT")
    parser.add_argument("--environment", choices=(LOCAL_ENVIRONMENT, *sorted(NONLOCAL_ENVIRONMENTS)), default=LOCAL_ENVIRONMENT)
    parser.add_argument("--policy-version", default=DEFAULT_POLICY_VERSION)
    parser.add_argument("--token-length", type=int, default=12)
    parser.add_argument("--audit-log", type=Path, default=DEFAULT_AUDIT_LOG_PATH)
    parser.add_argument("--no-audit-log", action="store_true")
    parser.add_argument(
        "--allow-env-secret-outside-local",
        action="store_true",
        help="Allow environment-variable secret use outside local-dev. Intended only for controlled prototypes.",
    )
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


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_args(args):
    if args.round_amount:
        args.amount_policy = "round"
    if args.keep_coarse_location:
        args.location_policy = "coarse"
    if args.token_length < 12:
        raise ValueError("--token-length must be at least 12.")
    if args.input.resolve() == args.output.resolve():
        raise ValueError("--input and --output must be different paths.")
    if args.environment in NONLOCAL_ENVIRONMENTS and not args.allow_env_secret_outside_local:
        raise RuntimeError(
            "Environment-variable secrets are allowed only for local-dev. "
            "Use a managed secret provider, or pass --allow-env-secret-outside-local for this prototype."
        )
    return args


def audit_event(args, status: str, row_count: int = 0, error: str = "", output_hash: str = "") -> dict:
    input_hash = file_sha256(args.input) if args.input.exists() else ""
    return {
        "event": "mask_test_data",
        "timestampUtc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "actor": getpass.getuser(),
        "environment": args.environment,
        "policyVersion": args.policy_version,
        "status": status,
        "error": error,
        "inputPath": str(args.input),
        "inputSha256": input_hash,
        "outputPath": str(args.output),
        "outputSha256": output_hash,
        "rowCount": row_count,
        "options": {
            "dayOffset": args.day_offset,
            "amountPolicy": args.amount_policy,
            "locationPolicy": args.location_policy,
            "tokenLength": args.token_length,
            "saltEnv": args.salt_env,
        },
        "keySource": f"env:{args.salt_env}",
    }


def write_audit_log(path: Path, event: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as log_file:
        log_file.write(json.dumps(event, sort_keys=True) + "\n")


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


def mask_amount(value: str, amount_policy: str) -> str:
    amount = float(value)
    if amount_policy == "round":
        amount = round(amount / DEFAULT_AMOUNT_ROUNDING) * DEFAULT_AMOUNT_ROUNDING
    if amount.is_integer():
        return str(int(amount))
    return f"{amount:.2f}"


def mask_location(row: dict, location_policy: str) -> tuple[str, str]:
    if location_policy == "remove":
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


def mask_rows(
    rows: list[dict],
    day_offset: int,
    amount_policy: str,
    location_policy: str,
    salt: bytes,
    token_length: int,
) -> list[dict]:
    customer_tokens: dict[str, str] = {}
    customer_names: dict[str, str] = {}
    masked_rows: list[dict] = []

    for row in rows:
        ensure_columns(row, REQUIRED_COLUMNS)

        customer_ref = row["customerRef"]
        if customer_ref not in customer_tokens:
            customer_tokens[customer_ref] = stable_token("CUST", customer_ref, salt, token_length)
        if customer_ref not in customer_names:
            customer_names[customer_ref] = stable_customer_name(
                customer_tokens[customer_ref],
                len(customer_names) + 1,
            )
        customer_token = customer_tokens[customer_ref]

        timestamp = parse_timestamp(row["occurredAt"]) + dt.timedelta(days=day_offset)
        hour, day_of_week, is_dawn = recalculate_time_features(timestamp)
        latitude, longitude = mask_location(row, location_policy)

        masked_rows.append(
            {
                "transactionId": stable_token("TX", row["transactionId"], salt, token_length),
                "customerRef": customer_token,
                "customerName": customer_names[customer_ref],
                "amount": mask_amount(row["amount"], amount_policy),
                "occurredAt": format_timestamp(timestamp),
                "countryCode": row["countryCode"],
                "city": row["city"],
                "latitude": latitude,
                "longitude": longitude,
                "merchantId": stable_token("MER", row["merchantId"], salt, token_length),
                "merchantCategory": row["merchantCategory"],
                "deviceId": stable_token("DEV", row["deviceId"], salt, token_length),
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

    forbidden_prefixes = (
        "SIM-",
        "CUST-",
        "DEV-",
        "MER-",
        "online-",
        "offline-",
        "mobile-",
        "web-",
        "Jang ",
        "Lee ",
        "Kim ",
        "Park ",
        "Hong ",
        "Choi ",
        "Seo ",
    )
    expected_prefixes = {
        "transactionId": "TX_",
        "customerRef": "CUST_",
        "merchantId": "MER_",
        "deviceId": "DEV_",
        "customerName": "Customer_",
    }
    for row in rows:
        for column in OUTPUT_COLUMNS:
            if column not in row:
                raise ValueError(f"Missing output column: {column}")
        timestamp = parse_timestamp(row["occurredAt"])
        hour, day_of_week, is_dawn = recalculate_time_features(timestamp)
        if row["hour"] != hour or row["dayOfWeek"] != day_of_week or row["isDawn"] != is_dawn:
            raise ValueError(f"Time feature mismatch for transaction {row['transactionId']}.")
        for field, expected_prefix in expected_prefixes.items():
            value = str(row.get(field, ""))
            if not value.startswith(expected_prefix):
                raise ValueError(f"Unexpected masked value in {field}: {value}")
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
    try:
        args = normalize_args(args)
        salt = require_salt(args.salt_env)
        rows = read_rows(args.input)
        masked_rows = mask_rows(
            rows,
            args.day_offset,
            args.amount_policy,
            args.location_policy,
            salt,
            args.token_length,
        )
        validate_masked_rows(masked_rows)
        write_rows(args.output, masked_rows)
        output_hash = file_sha256(args.output)

        if not args.no_audit_log:
            write_audit_log(args.audit_log, audit_event(args, "success", len(masked_rows), output_hash=output_hash))

        print(f"wrote {len(masked_rows)} rows to {args.output}")
        print(
            "day_offset="
            f"{args.day_offset}, amount_policy={args.amount_policy}, "
            f"location_policy={args.location_policy}, environment={args.environment}"
        )
    except Exception as exc:
        if not args.no_audit_log:
            write_audit_log(args.audit_log, audit_event(args, "failure", error=str(exc)))
        raise


if __name__ == "__main__":
    main()
