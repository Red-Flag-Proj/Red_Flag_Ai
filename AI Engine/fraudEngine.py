from rules import (
    check_high_amount,
    check_frequent_transaction,
    check_foreign_ip,
    check_dawn_time,
    check_new_device,
    check_country_velocity,
)
from risk_scoring import build_score_breakdown, get_prd_risk_level, recommended_action

# 규칙 기반 FDS 엔진입니다.
# 각 rule 함수가 위험 조건을 검사하고, 탐지된 rule 점수를 합산해 최종 위험 등급을 만듭니다.

def get_risk_level(score):
    return get_prd_risk_level(score)


def detect_fraud(transaction, context):
    # 필요한 규칙을 여기에 등록하면 탐지 흐름에 자동으로 포함됩니다.
    rule_checks = [
        check_high_amount,
        check_frequent_transaction,
        check_foreign_ip,
        check_dawn_time,
        check_new_device,
        check_country_velocity,
    ]

    total_score = 0
    triggered_rules = []

    for check in rule_checks:
        result = check(transaction, context)

        # triggered가 True인 규칙만 점수와 사유에 반영합니다.
        if result["triggered"]:
            total_score += result["score"]
            triggered_rules.append({
                "ruleId": result["ruleId"],
                "title": result["title"],
                "score": result["score"],
                "reason": result["reason"],
            })

    # 대시보드에서 쓰기 쉽게 위험 점수는 0~100 범위로 제한합니다.
    risk_score = min(total_score, 100)
    score_breakdown = build_score_breakdown(rule_score=risk_score)
    detection_reasons = [rule["reason"] for rule in triggered_rules]

    return {
        "transactionId": transaction.get("id") or transaction.get("transactionId"),
        "riskScore": risk_score,
        "finalRiskScore": risk_score,
        "riskLevel": get_risk_level(risk_score),
        "scoreBreakdown": score_breakdown,
        "detectionReasons": detection_reasons,
        "recommendedAction": recommended_action(risk_score),
        "triggeredRules": triggered_rules,
    }
