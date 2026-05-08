import argparse
import csv
import math
import random
from datetime import datetime, timedelta
from pathlib import Path


BASE_DATE = datetime(2026, 5, 7, 12, 0, 0)
OUTPUT_PATH = Path(__file__).resolve().parent / "data" / "personal_customers_10_transactions.csv"
RANDOM_SEED = 42
NORMAL_TX_PER_CUSTOMER = 980


# Realistic home locations used for normal customer behavior.
CITY_COORDINATES = {
    "Seoul": (37.5665, 126.9780),
    "Busan": (35.1796, 129.0756),
    "Incheon": (37.4563, 126.7052),
    "Daegu": (35.8714, 128.6014),
    "Daejeon": (36.3504, 127.3845),
    "New York": (40.7128, -74.0060),
    "Tokyo": (35.6762, 139.6503),
    "Shanghai": (31.2304, 121.4737),
    "Ho Chi Minh City": (10.8231, 106.6297),
}


CUSTOMERS = [
    {"ref": "SIM-CUST-001", "name": "Kim Minjun", "city": "Seoul", "base": 52000, "method": "CARD", "category": "GROCERY", "hours": [9, 10, 11, 12, 18, 19, 20]},
    {"ref": "SIM-CUST-002", "name": "Lee Seoyeon", "city": "Busan", "base": 43000, "method": "CARD", "category": "CAFE", "hours": [8, 9, 12, 13, 18, 19]},
    {"ref": "SIM-CUST-003", "name": "Park Jiho", "city": "Incheon", "base": 68000, "method": "E-PAY", "category": "ONLINE", "hours": [10, 11, 12, 20, 21, 22]},
    {"ref": "SIM-CUST-004", "name": "Choi Haein", "city": "Daegu", "base": 36000, "method": "CARD", "category": "TRANSPORT", "hours": [7, 8, 9, 18, 19]},
    {"ref": "SIM-CUST-005", "name": "Jung Doyun", "city": "Daejeon", "base": 88000, "method": "CARD", "category": "DINING", "hours": [11, 12, 13, 19, 20, 21]},
    {"ref": "SIM-CUST-006", "name": "Kang Yuna", "city": "Seoul", "base": 125000, "method": "ACCOUNT", "category": "TRANSFER", "hours": [9, 10, 14, 15, 16]},
    {"ref": "SIM-CUST-007", "name": "Cho Hyunwoo", "city": "Busan", "base": 74000, "method": "E-PAY", "category": "SHOPPING", "hours": [10, 11, 19, 20, 21]},
    {"ref": "SIM-CUST-008", "name": "Yoon Sumin", "city": "Incheon", "base": 58000, "method": "CARD", "category": "MEDICAL", "hours": [9, 10, 11, 15, 16]},
    {"ref": "SIM-CUST-009", "name": "Jang Jiwon", "city": "Daegu", "base": 155000, "method": "ACCOUNT", "category": "TRANSFER", "hours": [8, 9, 10, 13, 14, 15]},
    {"ref": "SIM-CUST-010", "name": "Lim Nari", "city": "Daejeon", "base": 47000, "method": "CARD", "category": "UTILITY", "hours": [12, 13, 18, 19, 20]},
]

FIRST_NAMES = [
    "Kim", "Lee", "Park", "Choi", "Jung", "Kang", "Cho", "Yoon", "Jang", "Lim",
    "Han", "Oh", "Seo", "Shin", "Kwon", "Hwang", "Ahn", "Song", "Hong", "Moon",
]

LAST_NAMES = [
    "Minjun", "Seoyeon", "Jiho", "Haein", "Doyun", "Yuna", "Hyunwoo", "Sumin", "Jiwon", "Nari",
]

METHODS = ["CARD", "E-PAY", "ACCOUNT"]
CATEGORIES = ["GROCERY", "CAFE", "DINING", "ONLINE", "UTILITY", "TRANSPORT", "SHOPPING", "MEDICAL", "TRANSFER"]
DOMESTIC_CITIES = ["Seoul", "Busan", "Incheon", "Daegu", "Daejeon"]
HOUR_PROFILES = [
    [9, 10, 11, 12, 18, 19, 20],
    [8, 9, 12, 13, 18, 19],
    [10, 11, 12, 20, 21, 22],
    [7, 8, 9, 18, 19],
    [11, 12, 13, 19, 20, 21],
    [9, 10, 14, 15, 16],
]


def build_customers(customer_count):
    if customer_count <= len(CUSTOMERS):
        return CUSTOMERS[:customer_count]

    customers = list(CUSTOMERS)
    for index in range(len(CUSTOMERS), customer_count):
        ref = f"SIM-CUST-{index + 1:03d}"
        city = DOMESTIC_CITIES[index % len(DOMESTIC_CITIES)]
        category = CATEGORIES[index % len(CATEGORIES)]
        method = METHODS[index % len(METHODS)]
        base = random.randint(35, 165) * 1000
        customers.append({
            "ref": ref,
            "name": f"{FIRST_NAMES[index % len(FIRST_NAMES)]} {LAST_NAMES[index % len(LAST_NAMES)]}",
            "city": city,
            "base": base,
            "method": method,
            "category": category,
            "hours": HOUR_PROFILES[index % len(HOUR_PROFILES)],
        })
    return customers


def device_id(customer, kind):
    return f"{kind}-{customer['ref'].lower()}"


def normal_amount(customer, day_index):
    # Weekly/monthly rhythm and payday spikes make normal behavior less flat.
    weekly = 1 + ((day_index % 7) - 3) * 0.025
    monthly = 1 + math.sin(day_index / 30 * math.pi * 2) * 0.07
    payday = 1.45 if day_index % 30 in (24, 25) else 1
    noise = random.uniform(0.90, 1.14)
    return max(4000, round(customer["base"] * weekly * monthly * payday * noise))


def normal_transaction(customer, customer_index, tx_index, normal_tx_per_customer):
    occurred_at = BASE_DATE - timedelta(days=normal_tx_per_customer - tx_index)
    hour = random.choice(customer["hours"])
    occurred_at = occurred_at.replace(hour=hour, minute=(tx_index * 7 + customer_index * 3) % 60, second=0, microsecond=0)
    lat, lon = CITY_COORDINATES[customer["city"]]

    merchant_category = random.choices(
        [customer["category"], "GROCERY", "CAFE", "DINING", "ONLINE", "UTILITY", "TRANSPORT"],
        weights=[35, 18, 14, 12, 10, 7, 4],
        k=1,
    )[0]
    merchant_id = f"{merchant_category.lower()}-{customer['city'].lower()}-{(tx_index % 12) + 1:02d}"
    backup_device_every = 43 + customer_index
    current_device = device_id(customer, "web-trusted") if tx_index % backup_device_every == 0 else device_id(customer, "mobile-primary")

    return {
        "transactionId": f"{customer['ref']}-NORMAL-{tx_index + 1:04d}",
        "customerRef": customer["ref"],
        "customerName": customer["name"],
        "amount": normal_amount(customer, tx_index),
        "occurredAt": occurred_at.isoformat(),
        "countryCode": "KR",
        "city": customer["city"],
        "latitude": round(lat + random.uniform(-0.025, 0.025), 6),
        "longitude": round(lon + random.uniform(-0.025, 0.025), 6),
        "merchantId": merchant_id,
        "merchantCategory": merchant_category,
        "deviceId": current_device,
        "paymentMethod": customer["method"],
        "hour": occurred_at.hour,
        "dayOfWeek": occurred_at.weekday(),
        "isForeign": 0,
        "isNewDevice": 0,
        "isNewPaymentMethod": 0,
        "isDawn": 0,
        "label": 0,
        "scenario": "NORMAL_BASELINE",
    }


def normal_exception_transactions(customer, customer_index):
    home_lat, home_lon = CITY_COORDINATES[customer["city"]]
    foreign_country, foreign_city = [("JP", "Tokyo"), ("US", "New York"), ("VN", "Ho Chi Minh City")][customer_index % 3]
    foreign_lat, foreign_lon = CITY_COORDINATES[foreign_city]
    cases = [
        {
            "suffix": "N-TRAVEL-FOREIGN",
            "amount": round(customer["base"] * random.uniform(1.3, 2.0)),
            "daysAgo": 35 + customer_index,
            "hour": random.choice(customer["hours"]),
            "country": foreign_country,
            "city": foreign_city,
            "lat": foreign_lat,
            "lon": foreign_lon,
            "device": device_id(customer, "mobile-primary"),
            "method": customer["method"],
            "merchantId": f"travel-{foreign_city.lower().replace(' ', '-')}-01",
            "category": "HOTEL",
            "scenario": "NORMAL_TRAVEL_FOREIGN",
        },
        {
            "suffix": "N-LARGE-PAYDAY",
            "amount": round(customer["base"] * random.uniform(2.1, 2.8)),
            "daysAgo": 32 + customer_index,
            "hour": random.choice(customer["hours"]),
            "country": "KR",
            "city": customer["city"],
            "lat": home_lat,
            "lon": home_lon,
            "device": device_id(customer, "mobile-primary"),
            "method": customer["method"],
            "merchantId": f"{customer['category'].lower()}-{customer['city'].lower()}-payday",
            "category": customer["category"],
            "scenario": "NORMAL_PAYDAY_LARGE_PURCHASE",
        },
        {
            "suffix": "N-NEW-DEVICE",
            "amount": round(customer["base"] * random.uniform(0.8, 1.3)),
            "daysAgo": 28 + customer_index,
            "hour": random.choice(customer["hours"]),
            "country": "KR",
            "city": customer["city"],
            "lat": home_lat,
            "lon": home_lon,
            "device": device_id(customer, "tablet-registered"),
            "method": customer["method"],
            "merchantId": f"{customer['category'].lower()}-{customer['city'].lower()}-registered-device",
            "category": customer["category"],
            "scenario": "NORMAL_REGISTERED_NEW_DEVICE",
        },
        {
            "suffix": "N-MONTH-END-SPEND",
            "amount": round(customer["base"] * random.uniform(1.4, 2.1)),
            "daysAgo": 26 + customer_index,
            "hour": random.choice(customer["hours"]),
            "country": "KR",
            "city": customer["city"],
            "lat": home_lat,
            "lon": home_lon,
            "device": device_id(customer, "mobile-primary"),
            "method": customer["method"],
            "merchantId": f"shopping-{customer['city'].lower()}-month-end",
            "category": "SHOPPING",
            "scenario": "NORMAL_MONTH_END_SPEND",
        },
    ]

    rows = []
    for case in cases:
        occurred_at = (BASE_DATE - timedelta(days=case["daysAgo"])).replace(hour=case["hour"], minute=41, second=0, microsecond=0)
        rows.append({
            "transactionId": f"{customer['ref']}-{case['suffix']}",
            "customerRef": customer["ref"],
            "customerName": customer["name"],
            "amount": case["amount"],
            "occurredAt": occurred_at.isoformat(),
            "countryCode": case["country"],
            "city": case["city"],
            "latitude": case["lat"],
            "longitude": case["lon"],
            "merchantId": case["merchantId"],
            "merchantCategory": case["category"],
            "deviceId": case["device"],
            "paymentMethod": case["method"],
            "hour": occurred_at.hour,
            "dayOfWeek": occurred_at.weekday(),
            "isForeign": 1 if case["country"] != "KR" else 0,
            "isNewDevice": 1 if case["device"] not in {device_id(customer, "mobile-primary"), device_id(customer, "web-trusted")} else 0,
            "isNewPaymentMethod": 1 if case["method"] != customer["method"] else 0,
            "isDawn": 1 if 0 <= case["hour"] < 5 else 0,
            "label": 0,
            "scenario": case["scenario"],
        })
    return rows


def scenario_time_offset(customer_index, normal_tx_per_customer):
    # Spread labeled scenarios across the timeline so time-based holdout has both
    # train and test anomalies.
    bucket_count = 5
    bucket = customer_index % bucket_count
    max_offset = max(0, normal_tx_per_customer - 140)
    step = max(20, normal_tx_per_customer // bucket_count)
    return min(bucket * step, max_offset)


def anomaly_transactions(customer, customer_index, normal_tx_per_customer):
    home_lat, home_lon = CITY_COORDINATES[customer["city"]]
    offset_days = scenario_time_offset(customer_index, normal_tx_per_customer)
    foreign_cases = [
        ("US", "New York", "ONLINE"),
        ("JP", "Tokyo", "HOTEL"),
        ("CN", "Shanghai", "ONLINE"),
        ("VN", "Ho Chi Minh City", "SHOPPING"),
    ]
    foreign_country, foreign_city, foreign_category = foreign_cases[customer_index % len(foreign_cases)]
    foreign_lat, foreign_lon = CITY_COORDINATES[foreign_city]

    high_amount = round(customer["base"] * random.uniform(7.5, 11.0))
    transfer_amount = round(customer["base"] * random.uniform(5.0, 7.2))
    medium_amount = round(customer["base"] * random.uniform(2.8, 4.2))

    cases = [
        {
            "suffix": "A-FOREIGN-HIGH",
            "amount": max(high_amount, 650000),
            "daysAgo": offset_days + 2 + (customer_index % 17),
            "hour": random.choice([18, 19, 20, 21]),
            "country": foreign_country,
            "city": foreign_city,
            "lat": foreign_lat,
            "lon": foreign_lon,
            "device": device_id(customer, "unknown-mobile"),
            "method": customer["method"],
            "category": foreign_category,
            "scenario": "FOREIGN_HIGH_AMOUNT_NEW_DEVICE",
        },
        {
            "suffix": "A-DAWN-TRANSFER",
            "amount": max(transfer_amount, 420000),
            "daysAgo": offset_days + 4 + (customer_index % 17),
            "hour": random.choice([1, 2, 3]),
            "country": "KR",
            "city": customer["city"],
            "lat": home_lat,
            "lon": home_lon,
            "device": device_id(customer, "mobile-primary"),
            "method": "ACCOUNT",
            "category": "TRANSFER",
            "scenario": "DAWN_HIGH_TRANSFER",
        },
        {
            "suffix": "A-NEW-METHOD",
            "amount": max(medium_amount, 180000),
            "daysAgo": offset_days + 7 + (customer_index % 17),
            "hour": random.choice([20, 21, 22]),
            "country": "KR",
            "city": customer["city"],
            "lat": home_lat,
            "lon": home_lon,
            "device": device_id(customer, "new-browser"),
            "method": "E-PAY" if customer["method"] != "E-PAY" else "CARD",
            "category": "ONLINE",
            "scenario": "NEW_DEVICE_PAYMENT_METHOD",
        },
    ]

    rows = []
    for case in cases:
        occurred_at = (BASE_DATE - timedelta(days=case["daysAgo"])).replace(hour=case["hour"], minute=17, second=0, microsecond=0)
        rows.append({
            "transactionId": f"{customer['ref']}-{case['suffix']}",
            "customerRef": customer["ref"],
            "customerName": customer["name"],
            "amount": case["amount"],
            "occurredAt": occurred_at.isoformat(),
            "countryCode": case["country"],
            "city": case["city"],
            "latitude": case["lat"],
            "longitude": case["lon"],
            "merchantId": f"{case['category'].lower()}-{case['city'].lower().replace(' ', '-')}-fraud",
            "merchantCategory": case["category"],
            "deviceId": case["device"],
            "paymentMethod": case["method"],
            "hour": occurred_at.hour,
            "dayOfWeek": occurred_at.weekday(),
            "isForeign": 1 if case["country"] != "KR" else 0,
            "isNewDevice": 1 if case["device"] not in {device_id(customer, "mobile-primary"), device_id(customer, "web-trusted")} else 0,
            "isNewPaymentMethod": 1 if case["method"] != customer["method"] else 0,
            "isDawn": 1 if 0 <= case["hour"] < 5 else 0,
            "label": 1,
            "scenario": case["scenario"],
        })

    burst_start = (BASE_DATE - timedelta(days=offset_days + 12 + (customer_index % 17))).replace(hour=1, minute=5, second=0, microsecond=0)
    for burst_index in range(3):
        occurred_at = burst_start + timedelta(minutes=burst_index * 8)
        rows.append({
            "transactionId": f"{customer['ref']}-A-BURST-{burst_index + 1:02d}",
            "customerRef": customer["ref"],
            "customerName": customer["name"],
            "amount": round(customer["base"] * random.uniform(2.2, 3.4)),
            "occurredAt": occurred_at.isoformat(),
            "countryCode": "KR",
            "city": customer["city"],
            "latitude": home_lat,
            "longitude": home_lon,
            "merchantId": f"online-burst-{burst_index + 1:02d}",
            "merchantCategory": "ONLINE",
            "deviceId": device_id(customer, "burst-device"),
            "paymentMethod": "E-PAY",
            "hour": occurred_at.hour,
            "dayOfWeek": occurred_at.weekday(),
            "isForeign": 0,
            "isNewDevice": 1,
            "isNewPaymentMethod": 1 if customer["method"] != "E-PAY" else 0,
            "isDawn": 1,
            "label": 1,
            "scenario": "BURST_DAWN_NEW_DEVICE_METHOD",
        })

    stealth_start = (BASE_DATE - timedelta(days=offset_days + 18 + (customer_index % 17))).replace(hour=random.choice(customer["hours"]), minute=3, second=0, microsecond=0)
    stealth_cases = [
        ("A-STEALTH-SMALL-TEST", 7000, 0, "DIGITAL", "digital-test-01", "STEALTH_PRECURSOR_SMALL_TEST", 0),
        ("A-STEALTH-LARGE-FOLLOWUP", round(customer["base"] * random.uniform(2.8, 3.6)), 4, "ELECTRONICS", "electronics-followup-01", "SMALL_TEST_THEN_LARGE", 1),
        ("A-STEALTH-REPEAT-1", round(customer["base"] * 1.35), 18, "ONLINE", "same-amount-01", "STEALTH_PRECURSOR_REPEAT_FIRST", 0),
        ("A-STEALTH-REPEAT-2", round(customer["base"] * 1.35), 21, "ONLINE", "same-amount-02", "SAME_AMOUNT_REPEATED", 1),
        ("A-STEALTH-REPEAT-3", round(customer["base"] * 1.35), 24, "ONLINE", "same-amount-03", "SAME_AMOUNT_REPEATED", 1),
        ("A-STEALTH-DISTRIBUTED-1", round(customer["base"] * 1.2), 40, "CAFE", "distributed-cafe-01", "RAPID_DISTRIBUTED_MERCHANTS", 1),
        ("A-STEALTH-DISTRIBUTED-2", round(customer["base"] * 1.3), 46, "GROCERY", "distributed-grocery-01", "RAPID_DISTRIBUTED_MERCHANTS", 1),
        ("A-STEALTH-DISTRIBUTED-3", round(customer["base"] * 1.4), 52, "DINING", "distributed-dining-01", "RAPID_DISTRIBUTED_MERCHANTS", 1),
        ("A-STEALTH-NEW-CATEGORY", round(customer["base"] * random.uniform(2.2, 2.8)), 80, "JEWELRY", "new-category-jewelry-01", "DOMESTIC_NEW_CATEGORY_HIGH_AMOUNT", 1),
    ]
    for suffix, amount, minute_offset, category, merchant_id, scenario, label in stealth_cases:
        occurred_at = stealth_start + timedelta(minutes=minute_offset)
        rows.append({
            "transactionId": f"{customer['ref']}-{suffix}",
            "customerRef": customer["ref"],
            "customerName": customer["name"],
            "amount": max(5000, amount),
            "occurredAt": occurred_at.isoformat(),
            "countryCode": "KR",
            "city": customer["city"],
            "latitude": home_lat,
            "longitude": home_lon,
            "merchantId": f"{merchant_id}-{customer['ref'].lower()}",
            "merchantCategory": category,
            "deviceId": device_id(customer, "mobile-primary"),
            "paymentMethod": customer["method"],
            "hour": occurred_at.hour,
            "dayOfWeek": occurred_at.weekday(),
            "isForeign": 0,
            "isNewDevice": 0,
            "isNewPaymentMethod": 0,
            "isDawn": 1 if 0 <= occurred_at.hour < 5 else 0,
            "label": label,
            "scenario": scenario,
        })

    return rows


def parse_args():
    parser = argparse.ArgumentParser(description="Generate synthetic FraudGuard personal transaction data.")
    parser.add_argument("--customers", type=int, default=len(CUSTOMERS), help="Number of synthetic customers to generate.")
    parser.add_argument("--normal-per-customer", type=int, default=NORMAL_TX_PER_CUSTOMER, help="Normal baseline transactions per customer.")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="CSV output path.")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED, help="Random seed.")
    return parser.parse_args()


def main():
    args = parse_args()
    random.seed(RANDOM_SEED)
    random.seed(args.seed)
    rows = []
    customers = build_customers(args.customers)

    for customer_index, customer in enumerate(customers):
        for tx_index in range(args.normal_per_customer):
            rows.append(normal_transaction(customer, customer_index, tx_index, args.normal_per_customer))
        rows.extend(normal_exception_transactions(customer, customer_index))
        rows.extend(anomaly_transactions(customer, customer_index, args.normal_per_customer))

    rows.sort(key=lambda row: (row["occurredAt"], row["customerRef"], row["transactionId"]))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    normal_count = sum(row["label"] == 0 for row in rows)
    anomaly_count = sum(row["label"] == 1 for row in rows)
    print(f"wrote {len(rows)} rows to {args.output}")
    print(f"customers={len(customers)}, normal={normal_count}, anomaly={anomaly_count}")


if __name__ == "__main__":
    main()
