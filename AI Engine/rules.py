from datetime import datetime


# rules.py는 설명 가능한 규칙 기반 탐지 조건을 모아 둔 파일입니다.
# 모델 점수만으로 설명하기 어려운 케이스를 FDS rule 점수로 보완합니다.

def parse_time(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)


def get_time_value(transaction):
    return transaction.get("occurredAt") or transaction.get("createdAt")


def get_country(transaction):
    return transaction.get("countryCode") or transaction.get("ipCountry")


def check_high_amount(transaction, context):
    # 절대 금액 기준과 개인/최근 평균 대비 배율 기준을 같이 봅니다.
    amount = float(transaction["amount"])
    avg_amount_7d = float(context.get("avgAmount7d", 0) or 0)
    amount_to_avg_ratio = float(context.get("amountToAvgRatio", 0) or 0)

    if amount >= 1_000_000 or (avg_amount_7d > 0 and amount >= avg_amount_7d * 3) or amount_to_avg_ratio >= 3:
        return {
            "triggered": True,
            "ruleId": "AMOUNT_HIGH",
            "title": "고액 거래",
            "score": 30,
            "reason": "100만원 이상이거나 최근/개인 평균 대비 3배 이상인 거래",
        }

    return {"triggered": False}


def check_frequent_transaction(transaction, context):
    # 짧은 시간에 반복 결제가 몰리는 패턴을 탐지합니다.
    current_time = parse_time(get_time_value(transaction))
    recent_transactions = context.get("recentTransactions", [])

    count_1min = 0
    count_10min = 0

    for tx in recent_transactions:
        tx_time = parse_time(get_time_value(tx))
        diff_minutes = (current_time - tx_time).total_seconds() / 60

        if 0 <= diff_minutes <= 1:
            count_1min += 1
        if 0 <= diff_minutes <= 10:
            count_10min += 1

    recent_1h_count = int(context.get("recent1hCount", 0) or 0)
    if count_1min >= 3 or count_10min >= 5 or recent_1h_count >= 5:
        return {
            "triggered": True,
            "ruleId": "FREQ_SHORT",
            "title": "짧은 시간 반복 거래",
            "score": 25,
            "reason": "1분 내 3회, 10분 내 5회, 또는 최근 1시간 5회 이상 거래",
        }

    return {"triggered": False}


def check_foreign_ip(transaction, context):
    # 현재 MVP는 국내 고객(KR)을 기준으로 해외 거래를 위험 신호로 봅니다.
    country = get_country(transaction)

    if country and country != "KR":
        return {
            "triggered": True,
            "ruleId": "LOCATION_FOREIGN",
            "title": "해외 거래",
            "score": 30,
            "reason": "국내 고객 기준 해외 국가에서 발생한 거래",
        }

    return {"triggered": False}


def check_dawn_time(transaction, context):
    # 새벽 거래는 명확한 rule로 보고, 평소 시간대 이탈은 낮은 점수로만 반영합니다.
    created_at = parse_time(get_time_value(transaction))
    hour = created_at.hour
    hour_deviation = float(context.get("hourDeviation", 0) or 0)

    if 0 <= hour < 5:
        return {
            "triggered": True,
            "ruleId": "TIME_DAWN",
            "title": "새벽 시간대 거래",
            "score": 15,
            "reason": "00:00~05:00 사이에 발생한 거래",
        }

    if hour_deviation >= 8:
        return {
            "triggered": True,
            "ruleId": "TIME_UNUSUAL",
            "title": "평소와 다른 시간대",
            "score": 5,
            "reason": "고객의 평균 사용 시간과 8시간 이상 차이",
        }

    return {"triggered": False}


def check_new_device(transaction, context):
    # 신규 기기는 오탐이 잦으므로 단독으로는 낮은 점수만 부여합니다.
    known_device_ids = context.get("knownDeviceIds", [])
    is_first_device = bool(context.get("isFirstDevice", False))

    if is_first_device or transaction.get("deviceId") not in known_device_ids:
        return {
            "triggered": True,
            "ruleId": "DEVICE_NEW",
            "title": "신규 기기 거래",
            "score": 10,
            "reason": "기존 고객 이력에 없던 기기에서 발생한 거래. 단독 신규 기기는 낮은 위험으로 반영",
        }

    return {"triggered": False}


def check_country_velocity(transaction, context):
    # 국가 이동 속도는 VPN/출장/프록시 때문에 오탐 가능성이 있어 높은 임계값만 사용합니다.
    speed = float(context.get("countryTravelSpeedKmh", 0) or 0)

    if speed >= 2500:
        return {
            "triggered": True,
            "ruleId": "LOCATION_VELOCITY",
            "title": "비정상 국가 이동 속도",
            "score": 15,
            "reason": "직전 거래 위치에서 현재 거래 위치까지 이동 속도가 2500km/h 이상",
        }

    return {"triggered": False}
