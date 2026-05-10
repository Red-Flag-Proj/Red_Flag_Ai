from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache
from math import asin, cos, radians, sin, sqrt
from statistics import median, pstdev


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


@lru_cache(maxsize=None)
def _parse_time_cached(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)


def parse_time(value):
    return _parse_time_cached(str(value))


def circular_hour_distance(hour_a, hour_b):
    # Example: 23:00 and 01:00 are 2 hours apart, not 22.
    diff = abs(float(hour_a) - float(hour_b))
    return min(diff, 24 - diff)


def haversine_km(lat1, lon1, lat2, lon2):
    radius_km = 6371
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return 2 * radius_km * asin(sqrt(a))


def row_coordinates(row):
    if "latitude" in row and "longitude" in row and row["latitude"] == row["latitude"] and row["longitude"] == row["longitude"]:
        return float(row["latitude"]), float(row["longitude"])
    return CITY_COORDINATES.get(row.get("city"))


def rows_since(history_rows, occurred_at, days):
    cutoff = occurred_at - timedelta(days=days)
    return [
        row for row in history_rows
        if cutoff <= parse_time(row.get("occurredAt") or row.get("createdAt")) < occurred_at
    ]


def average(values, default=0):
    return sum(values) / len(values) if values else default


def unique_count(rows, key_fn):
    return len({value for value in (key_fn(row) for row in rows) if value})


def count_since(prior_rows, occurred_at, minutes):
    cutoff = occurred_at - timedelta(minutes=minutes)
    return [
        row for row in prior_rows
        if cutoff <= parse_time(row.get("occurredAt") or row.get("createdAt")) < occurred_at
    ]


def get_merchant(row):
    return row.get("merchantId") or row.get("merchantName") or row.get("merchantCategory")


def get_category(row):
    return row.get("merchantCategory") or row.get("category")


def is_small_test_then_large(amount, recent_rows):
    small_rows = [row for row in recent_rows if float(row.get("amount", 0) or 0) <= 10000]
    return bool(small_rows and amount >= 100000)


def is_amount_increasing(recent_rows, amount):
    amounts = [float(row.get("amount", 0) or 0) for row in recent_rows[-2:]] + [float(amount)]
    return len(amounts) >= 3 and amounts[0] < amounts[1] < amounts[2]


def is_same_amount_repeated(amount, recent_rows):
    return sum(1 for row in recent_rows if abs(float(row.get("amount", 0) or 0) - float(amount)) < 1) >= 2


def build_context_from_history(transaction, history_rows, sequence_rows=None):
    # history_rows is the clean personal baseline. sequence_rows may include all
    # previous transactions so burst/follow-up patterns can be detected.
    amount = float(transaction["amount"])
    occurred_at = parse_time(transaction.get("occurredAt") or transaction.get("createdAt"))
    prior_rows = [
        row for row in history_rows
        if parse_time(row.get("occurredAt") or row.get("createdAt")) < occurred_at
    ]
    sequence_prior_rows = [
        row for row in (sequence_rows if sequence_rows is not None else history_rows)
        if parse_time(row.get("occurredAt") or row.get("createdAt")) < occurred_at
    ]

    amounts = [float(row["amount"]) for row in prior_rows]
    avg_amount = average(amounts)
    hours = [parse_time(row.get("occurredAt") or row.get("createdAt")).hour for row in prior_rows]
    avg_hour = average(hours, occurred_at.hour)
    known_devices = sorted({row.get("deviceId") for row in prior_rows if row.get("deviceId")})
    known_countries = sorted({row.get("countryCode") or row.get("ipCountry") for row in prior_rows if row.get("countryCode") or row.get("ipCountry")})
    known_methods = sorted({row.get("paymentMethod") for row in prior_rows if row.get("paymentMethod")})
    known_merchants = sorted({get_merchant(row) for row in prior_rows if get_merchant(row)})
    known_categories = sorted({get_category(row) for row in prior_rows if get_category(row)})

    recent_1h = [
        row for row in sequence_prior_rows
        if 0 <= (occurred_at - parse_time(row.get("occurredAt") or row.get("createdAt"))).total_seconds() <= 3600
    ]
    recent_5min = count_since(sequence_prior_rows, occurred_at, 5)
    recent_10min = count_since(sequence_prior_rows, occurred_at, 10)
    recent_24h = count_since(sequence_prior_rows, occurred_at, 24 * 60)
    recent_7d = rows_since(prior_rows, occurred_at, 7)
    recent_30d = rows_since(prior_rows, occurred_at, 30)

    recent_7d_amounts = [float(row["amount"]) for row in recent_7d]
    recent_30d_amounts = [float(row["amount"]) for row in recent_30d]
    recent_7d_avg = average(recent_7d_amounts, avg_amount)
    recent_30d_avg = average(recent_30d_amounts, avg_amount)
    recent_30d_median = median(recent_30d_amounts) if recent_30d_amounts else avg_amount
    recent_30d_std = pstdev(recent_30d_amounts) if len(recent_30d_amounts) >= 2 else 0
    amount_z_score = (amount - recent_30d_avg) / recent_30d_std if recent_30d_std > 0 else 0
    recent_7d_count = len(recent_7d)
    recent_30d_count = len(recent_30d)
    foreign_30d_count = sum(1 for row in recent_30d if (row.get("countryCode") or row.get("ipCountry")) != "KR")
    night_30d_count = sum(1 for row in recent_30d if 0 <= parse_time(row.get("occurredAt") or row.get("createdAt")).hour < 5)

    last_row = max(sequence_prior_rows, key=lambda row: parse_time(row.get("occurredAt") or row.get("createdAt"))) if sequence_prior_rows else None
    minutes_since_last = 24 * 60
    amount_change_ratio = 1
    country_changed_from_last = 0
    device_changed_from_last = 0
    payment_changed_from_last = 0
    distance_from_last_km = 0
    country_speed = 0

    if last_row:
        last_time = parse_time(last_row.get("occurredAt") or last_row.get("createdAt"))
        minutes_since_last = max((occurred_at - last_time).total_seconds() / 60, 1)
        last_amount = float(last_row["amount"])
        amount_change_ratio = amount / last_amount if last_amount > 0 else 1
        country_changed_from_last = 1 if (transaction.get("countryCode") or transaction.get("ipCountry")) != (last_row.get("countryCode") or last_row.get("ipCountry")) else 0
        device_changed_from_last = 1 if transaction.get("deviceId") != last_row.get("deviceId") else 0
        payment_changed_from_last = 1 if transaction.get("paymentMethod") != last_row.get("paymentMethod") else 0

        current_coord = row_coordinates(transaction)
        previous_coord = row_coordinates(last_row)
        if current_coord and previous_coord:
            distance_from_last_km = haversine_km(previous_coord[0], previous_coord[1], current_coord[0], current_coord[1])
            country_speed = distance_from_last_km / max(minutes_since_last / 60, 1 / 60)

    has_personal_baseline = len(prior_rows) > 0

    return {
        "avgAmount7d": recent_7d_avg,
        "amountToAvgRatio": amount / avg_amount if avg_amount > 0 else 1,
        "amountToRecent7dAvgRatio": amount / recent_7d_avg if recent_7d_avg > 0 else 1,
        "amountToRecent30dAvgRatio": amount / recent_30d_avg if recent_30d_avg > 0 else 1,
        "userMedianAmount30d": recent_30d_median,
        "userStdAmount30d": recent_30d_std,
        "amountRatioToUserMedian30d": amount / recent_30d_median if recent_30d_median > 0 else 1,
        "amountZScoreByUser": amount_z_score,
        "hourDeviation": circular_hour_distance(occurred_at.hour, avg_hour),
        "recent1hCount": len(recent_1h),
        "txCountLast5min": len(recent_5min),
        "txCountLast10min": len(recent_10min),
        "txCountLast24h": len(recent_24h),
        "amountSumLast10min": sum(float(row["amount"]) for row in recent_10min),
        "amountSumLast1h": sum(float(row["amount"]) for row in recent_1h),
        "amountSumLast24h": sum(float(row["amount"]) for row in recent_24h),
        "uniqueMerchantCountLast1h": unique_count(recent_1h, get_merchant),
        "uniqueCategoryCountLast1h": unique_count(recent_1h, get_category),
        "uniqueCountryCountLast24h": unique_count(recent_24h, lambda row: row.get("countryCode") or row.get("ipCountry")),
        "recent7dCount": recent_7d_count,
        "recent30dCount": recent_30d_count,
        "recent7dAmountAvg": recent_7d_avg,
        "recent30dAmountAvg": recent_30d_avg,
        "hasPersonalBaseline": has_personal_baseline,
        "isFirstDevice": has_personal_baseline and transaction.get("deviceId") not in known_devices,
        "isNewCountryForCustomer": has_personal_baseline and (transaction.get("countryCode") or transaction.get("ipCountry")) not in known_countries,
        "isNewPaymentMethodForCustomer": has_personal_baseline and transaction.get("paymentMethod") not in known_methods,
        "newMerchantForUser": has_personal_baseline and get_merchant(transaction) not in known_merchants,
        "newCategoryForUser": has_personal_baseline and get_category(transaction) not in known_categories,
        "userForeignTxRatio": foreign_30d_count / recent_30d_count if recent_30d_count else 0,
        "userNightTxRatio": night_30d_count / recent_30d_count if recent_30d_count else 0,
        "smallTestThenLargeTx": is_small_test_then_large(amount, recent_10min),
        "amountIncreasingPattern": is_amount_increasing(recent_10min, amount),
        "sameAmountRepeated": is_same_amount_repeated(amount, recent_10min),
        "rapidMultiTransaction": len(recent_10min) >= 3,
        "minutesSinceLastTransaction": minutes_since_last,
        "amountChangeRatioFromLast": amount_change_ratio,
        "countryChangedFromLast": country_changed_from_last,
        "deviceChangedFromLast": device_changed_from_last,
        "paymentChangedFromLast": payment_changed_from_last,
        "distanceFromLastKm": distance_from_last_km,
        "knownDeviceIds": known_devices,
        "recentTransactions": recent_1h,
        "countryTravelSpeedKmh": country_speed,
    }
