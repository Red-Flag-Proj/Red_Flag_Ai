import argparse
import csv
import json
from collections import Counter
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = BASE_DIR / "data" / "db_test_transactions_200_masked.csv"
DEFAULT_OUTPUT_PATH = BASE_DIR / "data" / "reidentification_risk_report.json"
DEFAULT_MIN_GROUP_SIZE = 5

QUASI_IDENTIFIER_SETS = {
    "city_hour_amount_label": ("city", "hour", "amount", "label"),
    "city_day_hour_scenario": ("city", "dayOfWeek", "hour", "scenario"),
    "country_city_payment_category": ("countryCode", "city", "paymentMethod", "merchantCategory"),
    "customer_pattern": ("customerRef", "city", "merchantCategory", "hour"),
}


def parse_args():
    parser = argparse.ArgumentParser(description="Assess re-identification risk in a masked FraudGuard CSV.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--min-group-size", type=int, default=DEFAULT_MIN_GROUP_SIZE)
    return parser.parse_args()


def read_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def count_combinations(rows: list[dict], fields: tuple[str, ...]) -> Counter:
    return Counter(tuple(row.get(field, "") for field in fields) for row in rows)


def sample_sparse_groups(counter: Counter, min_group_size: int, limit: int = 10) -> list[dict]:
    sparse = [
        {"count": count, "values": list(values)}
        for values, count in counter.items()
        if count < min_group_size
    ]
    sparse.sort(key=lambda item: (item["count"], item["values"]))
    return sparse[:limit]


def assess(rows: list[dict], min_group_size: int) -> dict:
    if not rows:
        raise ValueError("No rows found.")

    assessments = {}
    total_sparse_groups = 0
    for name, fields in QUASI_IDENTIFIER_SETS.items():
        counter = count_combinations(rows, fields)
        sparse_groups = [count for count in counter.values() if count < min_group_size]
        total_sparse_groups += len(sparse_groups)
        assessments[name] = {
            "fields": fields,
            "uniqueGroupCount": len(counter),
            "sparseGroupCount": len(sparse_groups),
            "minimumGroupSize": min(counter.values()),
            "sampleSparseGroups": sample_sparse_groups(counter, min_group_size),
        }

    location_present_count = sum(1 for row in rows if row.get("latitude") or row.get("longitude"))
    high_risk = total_sparse_groups > 0 or location_present_count > 0

    return {
        "inputRowCount": len(rows),
        "minGroupSize": min_group_size,
        "locationPresentCount": location_present_count,
        "status": "review_required" if high_risk else "pass",
        "assessments": assessments,
        "recommendations": recommendations(total_sparse_groups, location_present_count),
    }


def recommendations(total_sparse_groups: int, location_present_count: int) -> list[str]:
    items = []
    if location_present_count:
        items.append("Remove latitude/longitude unless the test explicitly requires coarse location.")
    if total_sparse_groups:
        items.append("Review sparse quasi-identifier groups before sharing beyond internal development.")
        items.append("Consider amount rounding, time bucketing, city generalization, or scenario suppression.")
    if not items:
        items.append("No immediate re-identification risk threshold violations detected.")
    return items


def main():
    args = parse_args()
    rows = read_rows(args.input)
    report = assess(rows, args.min_group_size)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output_file:
        json.dump(report, output_file, indent=2, sort_keys=True)
        output_file.write("\n")

    print(f"wrote risk report to {args.output}")
    print(f"status={report['status']}, rows={report['inputRowCount']}")


if __name__ == "__main__":
    main()
