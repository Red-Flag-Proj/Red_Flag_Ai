import argparse
import os
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
RAW_OUTPUT_PATH = BASE_DIR / "data" / "db_test_transactions_200.csv"
MASKED_OUTPUT_PATH = BASE_DIR / "data" / "db_test_transactions_200_masked.csv"
DEFAULT_AUDIT_LOG_PATH = BASE_DIR / "data" / "masking_audit.jsonl"
DEFAULT_SALT_ENV = "FRAUDGUARD_MASKING_SALT"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate DB test data and immediately produce the masked CSV."
    )
    parser.add_argument("--source", type=Path, default=BASE_DIR / "data" / "personal_customers_10_transactions.csv")
    parser.add_argument("--raw-output", type=Path, default=RAW_OUTPUT_PATH)
    parser.add_argument("--masked-output", type=Path, default=MASKED_OUTPUT_PATH)
    parser.add_argument("--rows", type=int, default=200)
    parser.add_argument("--anomalies", type=int, default=50)
    parser.add_argument("--seed", type=int, default=20260508)
    parser.add_argument("--day-offset", type=int, default=180)
    parser.add_argument("--amount-policy", choices=("keep", "round"), default="keep")
    parser.add_argument("--location-policy", choices=("remove", "coarse"), default="remove")
    parser.add_argument("--round-amount", action="store_true")
    parser.add_argument("--keep-coarse-location", action="store_true")
    parser.add_argument("--salt-env", default=DEFAULT_SALT_ENV)
    parser.add_argument("--environment", default="local-dev")
    parser.add_argument("--policy-version", default="fg-dev-data-security-v1")
    parser.add_argument("--token-length", type=int, default=12)
    parser.add_argument("--audit-log", type=Path, default=DEFAULT_AUDIT_LOG_PATH)
    parser.add_argument("--no-audit-log", action="store_true")
    parser.add_argument("--allow-env-secret-outside-local", action="store_true")
    return parser.parse_args()


def run_command(command, env=None):
    subprocess.run(command, check=True, env=env)


def main():
    args = parse_args()

    generate_command = [
        sys.executable,
        str(BASE_DIR / "generate_db_test_data.py"),
        "--source",
        str(args.source),
        "--output",
        str(args.raw_output),
        "--rows",
        str(args.rows),
        "--anomalies",
        str(args.anomalies),
        "--seed",
        str(args.seed),
    ]
    run_command(generate_command)

    env = os.environ.copy()
    if not env.get(args.salt_env, "").strip():
        raise RuntimeError(
            f"Missing required salt. Set environment variable {args.salt_env} before masking."
        )

    amount_policy = "round" if args.round_amount else args.amount_policy
    location_policy = "coarse" if args.keep_coarse_location else args.location_policy
    mask_command = [
        sys.executable,
        str(BASE_DIR / "mask_test_data.py"),
        "--input",
        str(args.raw_output),
        "--output",
        str(args.masked_output),
        "--day-offset",
        str(args.day_offset),
        "--amount-policy",
        amount_policy,
        "--location-policy",
        location_policy,
        "--salt-env",
        args.salt_env,
        "--environment",
        args.environment,
        "--policy-version",
        args.policy_version,
        "--token-length",
        str(args.token_length),
        "--audit-log",
        str(args.audit_log),
    ]
    if args.no_audit_log:
        mask_command.append("--no-audit-log")
    if args.allow_env_secret_outside_local:
        mask_command.append("--allow-env-secret-outside-local")

    run_command(mask_command, env=env)
    print(f"ready for DB import: {args.masked_output}")


if __name__ == "__main__":
    main()
