import argparse
import csv
import random
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
SOURCE_PATH = BASE_DIR / "data" / "personal_customers_10_transactions.csv"
OUTPUT_PATH = BASE_DIR / "data" / "db_test_transactions_200.csv"
RANDOM_SEED = 20260508

OUTPUT_COLUMNS = [
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


def parse_args():
    parser = argparse.ArgumentParser(description="Create a small DB integration test CSV.")
    parser.add_argument("--source", type=Path, default=SOURCE_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--rows", type=int, default=200)
    parser.add_argument("--anomalies", type=int, default=50)
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    return parser.parse_args()


def read_rows(path):
    with path.open(newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def stratified_sample(rows, total_count, anomaly_count, seed):
    random.seed(seed)
    anomaly_rows = [row for row in rows if int(row.get("label", 0) or 0) == 1]
    normal_rows = [row for row in rows if int(row.get("label", 0) or 0) == 0]

    anomaly_count = min(anomaly_count, total_count, len(anomaly_rows))
    normal_count = min(total_count - anomaly_count, len(normal_rows))

    selected = random.sample(anomaly_rows, anomaly_count) + random.sample(normal_rows, normal_count)
    selected.sort(key=lambda row: (row["occurredAt"], row["customerRef"], row["transactionId"]))
    return selected


def main():
    args = parse_args()
    rows = read_rows(args.source)
    selected = stratified_sample(rows, args.rows, args.anomalies, args.seed)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in selected:
            writer.writerow({column: row.get(column, "") for column in OUTPUT_COLUMNS})

    anomaly_count = sum(int(row.get("label", 0) or 0) == 1 for row in selected)
    print(f"wrote {len(selected)} rows to {args.output}")
    print(f"normal={len(selected) - anomaly_count}, anomaly={anomaly_count}")


if __name__ == "__main__":
    main()
