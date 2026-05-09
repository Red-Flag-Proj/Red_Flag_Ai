from __future__ import annotations

from typing import Any

from fraudEngine import detect_fraud
from personal_features import build_context_from_history
from risk_scoring import (
    build_detection_reasons,
    build_score_breakdown,
    calculate_final_risk_score,
    get_prd_risk_level,
    recommended_action,
    score_personal_pattern,
    score_sequence_pattern,
)


MODEL_POLICY = {
    "mode": "rule_personal_sequence",
    "mlScore": 0,
    "anomalyScore": 0,
    "modelServing": "not_enabled",
    "persistenceDecision": "Persisted ML model loading is reserved for a later joblib artifact.",
}


REQUIRED_TRANSACTION_FIELDS = [
    "transactionId",
    "customerRef",
    "amount",
    "deviceId",
    "paymentMethod",
]


def _time_value(transaction: dict[str, Any]) -> str | None:
    value = transaction.get("occurredAt") or transaction.get("createdAt")
    return str(value) if value is not None else None


def validate_transaction(transaction: dict[str, Any]) -> list[str]:
    errors = []
    for field in REQUIRED_TRANSACTION_FIELDS:
        if transaction.get(field) in (None, ""):
            errors.append(f"transaction.{field} is required")
    if not _time_value(transaction):
        errors.append("transaction.occurredAt or transaction.createdAt is required")
    if not (transaction.get("countryCode") or transaction.get("ipCountry")):
        errors.append("transaction.countryCode or transaction.ipCountry is required")
    try:
        float(transaction.get("amount", ""))
    except (TypeError, ValueError):
        errors.append("transaction.amount must be numeric")
    return errors


def build_inference_context(request: dict[str, Any]) -> dict[str, Any]:
    transaction = request["transaction"]
    if isinstance(request.get("context"), dict):
        return request["context"]

    customer_history = request.get("customerHistory") or []
    sequence_history = request.get("sequenceHistory")
    return build_context_from_history(transaction, customer_history, sequence_history)


def detect_transaction(request: dict[str, Any]) -> dict[str, Any]:
    transaction = request.get("transaction")
    if not isinstance(transaction, dict):
        return {
            "ok": False,
            "errors": ["transaction object is required"],
        }

    errors = validate_transaction(transaction)
    if errors:
        return {
            "ok": False,
            "transactionId": transaction.get("transactionId") or transaction.get("id"),
            "errors": errors,
        }

    context = build_inference_context(request)
    rule_result = detect_fraud(transaction, context)

    personal_score, personal_reasons = score_personal_pattern({**context, **transaction})
    sequence_score, sequence_reasons = score_sequence_pattern({**context, **transaction})
    score_breakdown = build_score_breakdown(
        rule_score=rule_result["riskScore"],
        ml_score=MODEL_POLICY["mlScore"],
        personal_score=personal_score,
        sequence_score=sequence_score,
        anomaly_score=MODEL_POLICY["anomalyScore"],
    )
    weighted_score = calculate_final_risk_score(score_breakdown)

    # Until a persisted ML model is served, preserve strong rule signals so
    # realtime backend calls do not under-report obvious high-risk cases.
    decision_score = max(weighted_score, rule_result["riskScore"], personal_score, sequence_score)
    detection_reasons = build_detection_reasons(
        rule_result.get("triggeredRules", []),
        personal_reasons,
        sequence_reasons,
    )

    risk_level = get_prd_risk_level(decision_score)
    return {
        "ok": True,
        "transactionId": transaction.get("transactionId") or transaction.get("id"),
        "customerRef": transaction.get("customerRef"),
        "riskScore": decision_score,
        "finalRiskScore": weighted_score,
        "riskLevel": risk_level,
        "scoreBreakdown": score_breakdown,
        "detectionReasons": detection_reasons,
        "recommendedAction": recommended_action(decision_score),
        "triggeredRules": rule_result.get("triggeredRules", []),
        "modelInfo": MODEL_POLICY,
        "arsPolicy": {
            "customerNameSource": "customer_identity_service",
            "doNotSpeakMaskedCustomerName": True,
        },
    }
