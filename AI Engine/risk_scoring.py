from __future__ import annotations


FINAL_SCORE_WEIGHTS = {
    "ruleScore": 0.30,
    "mlScore": 0.35,
    "personalPatternScore": 0.20,
    "sequencePatternScore": 0.10,
    "anomalyScore": 0.05,
}


def clamp_score(value):
    return int(round(max(0, min(100, float(value or 0)))))


def get_prd_risk_level(score):
    score = clamp_score(score)
    if score >= 80:
        return "고위험"
    if score >= 60:
        return "의심"
    if score >= 40:
        return "주의"
    return "정상"


def recommended_action(score):
    level = get_prd_risk_level(score)
    if level == "고위험":
        return "거래 보류 후 관리자 검토"
    if level == "의심":
        return "추가 인증 또는 관리자 확인"
    if level == "주의":
        return "승인 후 모니터링"
    return "승인"


def score_personal_pattern(features):
    score = 0
    reasons = []

    amount_ratio = float(features.get("amountToRecent30dAvgRatio", 1) or 1)
    median_ratio = float(features.get("amountRatioToUserMedian30d", 1) or 1)
    z_score = float(features.get("amountZScoreByUser", 0) or 0)

    if z_score >= 3:
        score += 25
        reasons.append(f"개인 금액 분포 기준 z-score가 {z_score:.1f}입니다.")
    elif amount_ratio >= 3 or median_ratio >= 3:
        score += 20
        reasons.append("사용자 최근 30일 기준보다 큰 금액의 거래입니다.")

    if bool(features.get("isNewCountryForCustomer", False)):
        score += 15
        reasons.append("사용자 이력에 없던 국가에서 발생한 거래입니다.")

    if bool(features.get("newMerchantForUser", False)):
        amount = float(features.get("amount", 0) or 0)
        if amount >= float(features.get("recent30dAmountAvg", 0) or 0) * 2:
            score += 15
            reasons.append("새 가맹점에서 평소보다 큰 금액이 결제되었습니다.")
        else:
            score += 8
            reasons.append("사용자 이력에 없던 가맹점에서 발생한 거래입니다.")

    if bool(features.get("newCategoryForUser", False)):
        score += 8
        reasons.append("사용자 이력에 없던 업종에서 발생한 거래입니다.")

    if bool(features.get("isNewPaymentMethodForCustomer", False)):
        score += 8
        reasons.append("사용자가 평소 쓰지 않던 결제수단이 사용되었습니다.")

    if float(features.get("hourDeviation", 0) or 0) >= 8:
        score += 8
        reasons.append("사용자 평소 결제 시간대와 크게 다른 시간입니다.")

    return clamp_score(score), reasons


def score_sequence_pattern(features):
    score = 0
    reasons = []

    if int(features.get("txCountLast10min", 0) or 0) >= 3:
        score += 20
        reasons.append("최근 10분 내 거래가 3회 이상 발생했습니다.")

    if int(features.get("txCountLast5min", 0) or 0) >= 2:
        score += 10
        reasons.append("최근 5분 내 거래가 반복되었습니다.")

    if bool(features.get("smallTestThenLargeTx", False)):
        score += 30
        reasons.append("소액 테스트 후 큰 금액 결제로 이어지는 패턴입니다.")

    amount_change_ratio = float(features.get("amountChangeRatioFromLast", 1) or 1)
    if amount_change_ratio >= 5:
        score += 15
        reasons.append(f"직전 거래 대비 금액이 {amount_change_ratio:.1f}배 증가했습니다.")

    if bool(features.get("amountIncreasingPattern", False)):
        score += 15
        reasons.append("최근 거래 금액이 점진적으로 증가했습니다.")

    if bool(features.get("sameAmountRepeated", False)):
        score += 12
        reasons.append("동일 금액 결제가 짧은 시간 안에 반복되었습니다.")

    if bool(features.get("rapidMultiTransaction", False)):
        score += 15
        reasons.append("짧은 시간 안에 여러 거래가 집중되었습니다.")

    if int(features.get("uniqueMerchantCountLast1h", 0) or 0) >= 3:
        score += 12
        reasons.append("최근 1시간 내 여러 가맹점에서 결제되었습니다.")

    if int(features.get("uniqueCategoryCountLast1h", 0) or 0) >= 3:
        score += 8
        reasons.append("최근 1시간 내 여러 업종에서 결제되었습니다.")

    if int(features.get("uniqueCountryCountLast24h", 0) or 0) >= 2:
        score += 12
        reasons.append("최근 24시간 내 여러 국가에서 거래가 발생했습니다.")

    return clamp_score(score), reasons


def build_score_breakdown(rule_score, ml_score=0, personal_score=0, sequence_score=0, anomaly_score=0):
    return {
        "ruleScore": clamp_score(rule_score),
        "mlScore": clamp_score(ml_score),
        "personalPatternScore": clamp_score(personal_score),
        "sequencePatternScore": clamp_score(sequence_score),
        "anomalyScore": clamp_score(anomaly_score),
    }


def calculate_final_risk_score(score_breakdown):
    total = 0
    for key, weight in FINAL_SCORE_WEIGHTS.items():
        total += clamp_score(score_breakdown.get(key, 0)) * weight
    return clamp_score(total)


def build_detection_reasons(rule_results, personal_reasons=None, sequence_reasons=None, anomaly_reason=None, ml_reason=None):
    reasons = []
    for rule in rule_results or []:
        reasons.append(rule.get("reason") or rule.get("title"))
    reasons.extend(personal_reasons or [])
    reasons.extend(sequence_reasons or [])
    if anomaly_reason:
        reasons.append(anomaly_reason)
    if ml_reason:
        reasons.append(ml_reason)
    return [reason for reason in reasons if reason]
