import argparse
import csv
import random
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
SOURCE_PATH = BASE_DIR / "data" / "personal_customers_10_transactions.csv"
OUTPUT_PATH = BASE_DIR / "data" / "db_test_transactions_400.csv"
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
    parser = argparse.ArgumentParser(description="Create a DB integration test CSV.")
    parser.add_argument("--source", type=Path, default=SOURCE_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--rows", type=int, default=400)
    parser.add_argument("--anomalies", type=int, default=120)
    parser.add_argument("--danger-stress", type=int, default=60)
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


def strengthen_dashboard_danger_cases(rows, target_count):
    if target_count <= 0:
        return rows

    strengthened = []
    danger_candidates = [row for row in rows if int(row.get("label", 0) or 0) == 1]
    foreign_cases = [
        ("US", "New York", 40.7128, -74.0060),
        ("JP", "Tokyo", 35.6762, 139.6503),
        ("VN", "Ho Chi Minh City", 10.8231, 106.6297),
        ("CN", "Shanghai", 31.2304, 121.4737),
    ]

    for index, row in enumerate(danger_candidates[:target_count]):
        country, city, latitude, longitude = foreign_cases[index % len(foreign_cases)]
        occurred_at = datetime.fromisoformat(row["occurredAt"]).replace(hour=(index % 4) + 1)
        stressed = dict(row)
        stressed["transactionId"] = f"{row['transactionId']}-DANGER-STRESS"
        stressed["amount"] = str(max(int(float(row.get("amount", 0) or 0)), 1250000 + (index % 7) * 85000))
        stressed["occurredAt"] = occurred_at.isoformat()
        stressed["countryCode"] = country
        stressed["city"] = city
        stressed["latitude"] = latitude
        stressed["longitude"] = longitude
        stressed["merchantId"] = f"dashboard-danger-{index + 1:03d}"
        stressed["merchantCategory"] = "ONLINE"
        stressed["deviceId"] = f"dashboard-danger-device-{index + 1:03d}"
        stressed["paymentMethod"] = "ACCOUNT" if index % 2 == 0 else "E-PAY"
        stressed["hour"] = str(occurred_at.hour)
        stressed["dayOfWeek"] = str(occurred_at.weekday())
        stressed["isForeign"] = "1"
        stressed["isNewDevice"] = "1"
        stressed["isNewPaymentMethod"] = "1"
        stressed["isDawn"] = "1"
        stressed["scenario"] = "DASHBOARD_DANGER_STRESS"
        strengthened.append((row["transactionId"], stressed))

    replacements = dict(strengthened)
    return [replacements.get(row["transactionId"], row) for row in rows]


def main():
    args = parse_args()
    rows = read_rows(args.source)
    selected = stratified_sample(rows, args.rows, args.anomalies, args.seed)
    selected = strengthen_dashboard_danger_cases(selected, min(args.danger_stress, args.anomalies))

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
