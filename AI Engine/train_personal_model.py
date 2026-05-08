import json
from pathlib import Path

import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, classification_report, confusion_matrix
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

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


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "personal_customers_10_transactions.csv"
RESULT_PATH = BASE_DIR / "personal_model_results.json"

THRESHOLD_QUANTILE = 0.999
MIN_RULE_SCORE_FOR_FRAUD = 45
MIN_HYBRID_SCORE_FOR_FRAUD = 62
MIN_PERSONAL_SCORE_FOR_FRAUD = 45
MIN_SEQUENCE_SCORE_FOR_FRAUD = 20
MIN_ML_SCORE_FOR_FRAUD = 50
MIN_FORCE_RULE_SCORE_FOR_FRAUD = 80
RULE_SCORE_WEIGHT = 1.0
ML_SCORE_WEIGHT = 0.45
ISOLATION_FOREST_ESTIMATORS = 60
ISOLATION_FOREST_MAX_SAMPLES = 2048

# Train with normal transactions only, then evaluate on normal + anomaly rows.
FEATURE_COLUMNS = [
    "amount",
    "hour",
    "dayOfWeek",
    "isForeign",
    "isNewDevice",
    "isNewPaymentMethod",
    "isDawn",
    "amountToAvgRatio",
    "amountToRecent7dAvgRatio",
    "amountToRecent30dAvgRatio",
    "hourDeviation",
    "recent1hCount",
    "txCountLast5min",
    "txCountLast10min",
    "txCountLast24h",
    "amountSumLast10min",
    "amountSumLast1h",
    "amountSumLast24h",
    "uniqueMerchantCountLast1h",
    "uniqueCategoryCountLast1h",
    "uniqueCountryCountLast24h",
    "recent7dCount",
    "recent30dCount",
    "userMedianAmount30d",
    "userStdAmount30d",
    "amountRatioToUserMedian30d",
    "amountZScoreByUser",
    "isFirstDevice",
    "isNewCountryForCustomer",
    "isNewPaymentMethodForCustomer",
    "newMerchantForUser",
    "newCategoryForUser",
    "userForeignTxRatio",
    "userNightTxRatio",
    "smallTestThenLargeTx",
    "amountIncreasingPattern",
    "sameAmountRepeated",
    "rapidMultiTransaction",
    "minutesSinceLastTransaction",
    "amountChangeRatioFromLast",
    "countryChangedFromLast",
    "deviceChangedFromLast",
    "paymentChangedFromLast",
    "distanceFromLastKm",
    "countryTravelSpeedKmh",
    "ruleScore",
]

SUPERVISED_FEATURE_COLUMNS = [column for column in FEATURE_COLUMNS if column != "ruleScore"]


def load_dataset() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATA_PATH}. Run generate_personal_data.py first.")
    df = pd.read_csv(DATA_PATH)
    df["occurredAt"] = pd.to_datetime(df["occurredAt"])
    return df.sort_values(["occurredAt", "customerRef", "transactionId"]).reset_index(drop=True)


def row_to_transaction(row) -> dict:
    # Convert one CSV row into the transaction shape expected by the rule engine.
    return {
        "transactionId": row["transactionId"],
        "customerRef": row["customerRef"],
        "amount": float(row["amount"]),
        "occurredAt": row["occurredAt"].isoformat(),
        "countryCode": row["countryCode"],
        "city": row["city"],
        "latitude": float(row["latitude"]) if "latitude" in row and pd.notna(row["latitude"]) else None,
        "longitude": float(row["longitude"]) if "longitude" in row and pd.notna(row["longitude"]) else None,
        "deviceId": row["deviceId"],
        "paymentMethod": row["paymentMethod"],
        "merchantId": row.get("merchantId"),
        "merchantCategory": row.get("merchantCategory"),
    }


def build_personal_features(df: pd.DataFrame) -> pd.DataFrame:
    # For each transaction, use only the same customer's previous rows as baseline.
    rows = df.to_dict(orient="records")
    histories_by_customer = {}
    sequence_histories_by_customer = {}
    contexts = []
    rule_results = []
    personal_scores = []
    personal_reasons = []
    sequence_scores = []
    sequence_reasons = []

    for row in rows:
        transaction = row_to_transaction(row)
        customer_ref = row["customerRef"]
        history = histories_by_customer.setdefault(customer_ref, [])
        sequence_history = sequence_histories_by_customer.setdefault(customer_ref, [])

        context = build_context_from_history(transaction, history, sequence_history)
        rule_result = detect_fraud(transaction, context)
        feature_snapshot = {**transaction, **context}
        personal_score, personal_reason = score_personal_pattern(feature_snapshot)
        sequence_score, sequence_reason = score_sequence_pattern(feature_snapshot)

        contexts.append(context)
        rule_results.append(rule_result)
        personal_scores.append(personal_score)
        personal_reasons.append(personal_reason)
        sequence_scores.append(sequence_score)
        sequence_reasons.append(sequence_reason)

        # Keep the customer baseline clean during training/evaluation. Confirmed fraud rows
        # should not become future "normal" behavior.
        if int(row.get("label", 0) or 0) == 0:
            history.append(row)
        sequence_history.append(row)

    df = df.copy()
    df["amountToAvgRatio"] = [context["amountToAvgRatio"] for context in contexts]
    df["amountToRecent7dAvgRatio"] = [context["amountToRecent7dAvgRatio"] for context in contexts]
    df["amountToRecent30dAvgRatio"] = [context["amountToRecent30dAvgRatio"] for context in contexts]
    df["hourDeviation"] = [context["hourDeviation"] for context in contexts]
    df["recent1hCount"] = [context["recent1hCount"] for context in contexts]
    df["txCountLast5min"] = [context["txCountLast5min"] for context in contexts]
    df["txCountLast10min"] = [context["txCountLast10min"] for context in contexts]
    df["txCountLast24h"] = [context["txCountLast24h"] for context in contexts]
    df["amountSumLast10min"] = [context["amountSumLast10min"] for context in contexts]
    df["amountSumLast1h"] = [context["amountSumLast1h"] for context in contexts]
    df["amountSumLast24h"] = [context["amountSumLast24h"] for context in contexts]
    df["uniqueMerchantCountLast1h"] = [context["uniqueMerchantCountLast1h"] for context in contexts]
    df["uniqueCategoryCountLast1h"] = [context["uniqueCategoryCountLast1h"] for context in contexts]
    df["uniqueCountryCountLast24h"] = [context["uniqueCountryCountLast24h"] for context in contexts]
    df["recent7dCount"] = [context["recent7dCount"] for context in contexts]
    df["recent30dCount"] = [context["recent30dCount"] for context in contexts]
    df["userMedianAmount30d"] = [context["userMedianAmount30d"] for context in contexts]
    df["userStdAmount30d"] = [context["userStdAmount30d"] for context in contexts]
    df["amountRatioToUserMedian30d"] = [context["amountRatioToUserMedian30d"] for context in contexts]
    df["amountZScoreByUser"] = [context["amountZScoreByUser"] for context in contexts]
    df["isFirstDevice"] = [1 if context["isFirstDevice"] else 0 for context in contexts]
    df["isNewCountryForCustomer"] = [1 if context["isNewCountryForCustomer"] else 0 for context in contexts]
    df["isNewPaymentMethodForCustomer"] = [1 if context["isNewPaymentMethodForCustomer"] else 0 for context in contexts]
    df["newMerchantForUser"] = [1 if context["newMerchantForUser"] else 0 for context in contexts]
    df["newCategoryForUser"] = [1 if context["newCategoryForUser"] else 0 for context in contexts]
    df["userForeignTxRatio"] = [context["userForeignTxRatio"] for context in contexts]
    df["userNightTxRatio"] = [context["userNightTxRatio"] for context in contexts]
    df["smallTestThenLargeTx"] = [1 if context["smallTestThenLargeTx"] else 0 for context in contexts]
    df["amountIncreasingPattern"] = [1 if context["amountIncreasingPattern"] else 0 for context in contexts]
    df["sameAmountRepeated"] = [1 if context["sameAmountRepeated"] else 0 for context in contexts]
    df["rapidMultiTransaction"] = [1 if context["rapidMultiTransaction"] else 0 for context in contexts]
    df["minutesSinceLastTransaction"] = [context["minutesSinceLastTransaction"] for context in contexts]
    df["amountChangeRatioFromLast"] = [context["amountChangeRatioFromLast"] for context in contexts]
    df["countryChangedFromLast"] = [context["countryChangedFromLast"] for context in contexts]
    df["deviceChangedFromLast"] = [context["deviceChangedFromLast"] for context in contexts]
    df["paymentChangedFromLast"] = [context["paymentChangedFromLast"] for context in contexts]
    df["distanceFromLastKm"] = [context["distanceFromLastKm"] for context in contexts]
    df["countryTravelSpeedKmh"] = [context["countryTravelSpeedKmh"] for context in contexts]
    df["ruleScore"] = [result["riskScore"] for result in rule_results]
    df["ruleLevel"] = [result["riskLevel"] for result in rule_results]
    df["triggeredRules"] = [result["triggeredRules"] for result in rule_results]
    df["personalPatternScore"] = personal_scores
    df["personalReasons"] = personal_reasons
    df["sequencePatternScore"] = sequence_scores
    df["sequenceReasons"] = sequence_reasons
    return df


def normalize_ml_score(score, threshold):
    # Convert IsolationForest anomaly score into a dashboard-friendly partial risk score.
    if threshold <= 0:
        return 0
    return max(0, min(100, round((score / threshold) * 50)))


def binary_metrics(y_true, y_pred):
    matrix = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = int(matrix[0][0]), int(matrix[0][1]), int(matrix[1][0]), int(matrix[1][1])
    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
    return {
        "threshold": None,
        "predictedAnomalies": int(tp + fp),
        "truePositive": tp,
        "falsePositive": fp,
        "falseNegative": fn,
        "trueNegative": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def threshold_sweep(eval_df):
    rows = []
    y_true = eval_df["label"]
    for threshold in [45, 50, 55, 60, 62, 65, 70, 75, 80]:
        y_pred = (
            (eval_df["anomalyScore"] >= eval_df["customerThreshold"])
            | (eval_df["ruleScore"] >= MIN_RULE_SCORE_FOR_FRAUD)
            | (eval_df["personalPatternScore"] >= MIN_PERSONAL_SCORE_FOR_FRAUD)
            | (eval_df["sequencePatternScore"] >= MIN_SEQUENCE_SCORE_FOR_FRAUD)
            | (eval_df["finalRiskScore"] >= threshold)
        ).astype(int)
        metrics = binary_metrics(y_true, y_pred)
        metrics["threshold"] = threshold
        rows.append(metrics)
    return rows


def component_threshold_sweep(eval_df):
    rows = []
    y_true = eval_df["label"]
    for sequence_threshold in [15, 20, 25, 30, 35]:
        for personal_threshold in [40, 45, 50, 55]:
            y_pred = (
                (eval_df["anomalyScore"] >= eval_df["customerThreshold"])
                | (eval_df["ruleScore"] >= MIN_RULE_SCORE_FOR_FRAUD)
                | (eval_df["personalPatternScore"] >= personal_threshold)
                | (eval_df["sequencePatternScore"] >= sequence_threshold)
                | (eval_df["finalRiskScore"] >= MIN_HYBRID_SCORE_FOR_FRAUD)
            ).astype(int)
            metrics = binary_metrics(y_true, y_pred)
            metrics["sequenceThreshold"] = sequence_threshold
            metrics["personalThreshold"] = personal_threshold
            metrics.pop("threshold", None)
            rows.append(metrics)
    return rows


def supervised_ml_threshold_sweep(eval_df):
    rows = []
    y_true = eval_df["label"]
    for threshold in [50, 60, 70, 80, 90]:
        y_pred = (eval_df["mlScore"] >= threshold).astype(int)
        metrics = binary_metrics(y_true, y_pred)
        metrics["mlScoreThreshold"] = threshold
        metrics.pop("threshold", None)
        rows.append(metrics)
    return rows


def component_prediction(eval_df, personal_threshold=MIN_PERSONAL_SCORE_FOR_FRAUD, sequence_threshold=MIN_SEQUENCE_SCORE_FOR_FRAUD):
    return (
        (eval_df["anomalyScore"] >= eval_df["customerThreshold"])
        | (eval_df["ruleScore"] >= MIN_RULE_SCORE_FOR_FRAUD)
        | (eval_df["personalPatternScore"] >= personal_threshold)
        | (eval_df["sequencePatternScore"] >= sequence_threshold)
        | (eval_df["finalRiskScore"] >= MIN_HYBRID_SCORE_FOR_FRAUD)
    ).astype(int)


def final_prediction(eval_df):
    return (
        (eval_df["mlScore"] >= MIN_ML_SCORE_FOR_FRAUD)
        | (eval_df["ruleScore"] >= MIN_FORCE_RULE_SCORE_FOR_FRAUD)
    ).astype(int)


def decision_method(row):
    ml_triggered = bool(row["mlScore"] >= MIN_ML_SCORE_FOR_FRAUD)
    fallback_triggered = bool(row["ruleScore"] >= MIN_FORCE_RULE_SCORE_FOR_FRAUD)
    if ml_triggered and fallback_triggered:
        return "ml_score_and_rule_fallback"
    if ml_triggered:
        return "ml_score"
    if fallback_triggered:
        return "rule_fallback"
    return "not_flagged"


def add_supervised_ml_scores(eval_df):
    labels = eval_df["label"].astype(int)
    class_counts = labels.value_counts()
    min_class_count = int(class_counts.min()) if len(class_counts) == 2 else 0

    if min_class_count < 2:
        eval_df["mlScore"] = 0
        return {
            "enabled": False,
            "reason": "Need at least two examples per class for cross-validated supervised ML scoring.",
            "features": SUPERVISED_FEATURE_COLUMNS,
        }

    n_splits = min(5, min_class_count)
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            random_state=42,
            solver="liblinear",
        ),
    )
    probabilities = cross_val_predict(
        model,
        eval_df[SUPERVISED_FEATURE_COLUMNS],
        labels,
        cv=cv,
        method="predict_proba",
        n_jobs=-1,
    )[:, 1]
    eval_df["mlScore"] = [max(0, min(100, round(probability * 100))) for probability in probabilities]
    pr_auc = average_precision_score(labels, probabilities)

    return {
        "enabled": True,
        "model": "LogisticRegression(class_weight='balanced')",
        "validation": f"{n_splits}-fold stratified out-of-fold probabilities",
        "features": SUPERVISED_FEATURE_COLUMNS,
        "prAuc": float(pr_auc),
    }


def fit_supervised_model(train_df):
    labels = train_df["label"].astype(int)
    if labels.nunique() < 2:
        return None

    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            random_state=42,
            solver="liblinear",
        ),
    )
    model.fit(train_df[SUPERVISED_FEATURE_COLUMNS], labels)
    return model


def compare_methods_on_split(name, train_df, test_df):
    if test_df.empty:
        return {
            "name": name,
            "enabled": False,
            "reason": "Test split is empty.",
        }

    y_true = test_df["label"].astype(int)
    result = {
        "name": name,
        "enabled": True,
        "trainRows": int(len(train_df)),
        "testRows": int(len(test_df)),
        "trainAnomalies": int(train_df["label"].sum()),
        "testAnomalies": int(test_df["label"].sum()),
        "methods": {},
    }

    component_current = component_prediction(test_df)
    result["methods"]["componentCurrent"] = binary_metrics(y_true, component_current)

    component_tuned = component_prediction(test_df, personal_threshold=50, sequence_threshold=20)
    result["methods"]["componentPersonal50Sequence20"] = binary_metrics(y_true, component_tuned)

    model = fit_supervised_model(train_df)
    if model is None:
        result["methods"]["supervisedMl"] = {
            "enabled": False,
            "reason": "Training split does not contain both classes.",
        }
        return result

    probabilities = model.predict_proba(test_df[SUPERVISED_FEATURE_COLUMNS])[:, 1]
    ml_scores = pd.Series([max(0, min(100, round(probability * 100))) for probability in probabilities], index=test_df.index)
    supervised = {
        "enabled": True,
        "prAuc": float(average_precision_score(y_true, probabilities)) if y_true.nunique() == 2 else None,
        "thresholds": {},
    }
    for threshold in [50, 70]:
        supervised["thresholds"][f"mlScoreGte{threshold}"] = binary_metrics(y_true, (ml_scores >= threshold).astype(int))
    result["methods"]["supervisedMl"] = supervised
    return result


def holdout_method_comparison(eval_df):
    sorted_df = eval_df.sort_values(["occurredAt", "customerRef", "transactionId"]).copy()
    cutoff = sorted_df["occurredAt"].quantile(0.80)
    time_train = sorted_df[sorted_df["occurredAt"] < cutoff].copy()
    time_test = sorted_df[sorted_df["occurredAt"] >= cutoff].copy()

    customers = sorted(eval_df["customerRef"].unique())
    holdout_count = max(1, round(len(customers) * 0.20))
    holdout_customers = set(customers[-holdout_count:])
    customer_train = eval_df[~eval_df["customerRef"].isin(holdout_customers)].copy()
    customer_test = eval_df[eval_df["customerRef"].isin(holdout_customers)].copy()

    return {
        "note": "Component metrics use already-computed rule/pattern/anomaly scores. Supervised ML metrics train only on each split's train rows.",
        "timeHoldout": compare_methods_on_split("timeHoldoutLast20Percent", time_train, time_test),
        "newCustomerHoldout": compare_methods_on_split("newCustomerHoldoutLast20Percent", customer_train, customer_test),
    }


def scenario_breakdown(eval_df):
    rows = []
    for scenario, group in eval_df.groupby("scenario"):
        metrics = binary_metrics(group["label"], group["predictedLabel"])
        metrics["scenario"] = scenario
        metrics["rows"] = int(len(group))
        metrics["actualAnomalies"] = int(group["label"].sum())
        metrics.pop("threshold", None)
        rows.append(metrics)
    return sorted(rows, key=lambda row: (row["actualAnomalies"] == 0, row["scenario"]))


def train_and_evaluate() -> dict:
    # Build customer-specific baseline features, then train only on normal transactions.
    df = build_personal_features(load_dataset())
    train_df = df[df["label"] == 0].copy()
    eval_df = df.copy()

    scaler = StandardScaler()
    x_train = scaler.fit_transform(train_df[FEATURE_COLUMNS])
    x_eval = scaler.transform(eval_df[FEATURE_COLUMNS])

    # IsolationForest estimates how far each transaction is from normal behavior.
    model = IsolationForest(
        n_estimators=ISOLATION_FOREST_ESTIMATORS,
        contamination="auto",
        max_samples=min(ISOLATION_FOREST_MAX_SAMPLES, len(train_df)),
        random_state=42,
        n_jobs=-1,
    )
    model.fit(x_train)

    train_scores = -model.score_samples(x_train)
    eval_df["anomalyScore"] = -model.score_samples(x_eval)
    train_score_df = train_df[["customerRef"]].copy()
    train_score_df["anomalyScore"] = train_scores

    # Use customer-specific thresholds so high-variance customers are not judged by one global cutoff.
    global_threshold = float(pd.Series(train_scores).quantile(THRESHOLD_QUANTILE))
    customer_thresholds = (
        train_score_df
        .groupby("customerRef")["anomalyScore"]
        .quantile(THRESHOLD_QUANTILE)
        .to_dict()
    )
    eval_df["customerThreshold"] = eval_df["customerRef"].map(customer_thresholds).fillna(global_threshold)
    eval_df["anomalyPredictedLabel"] = (eval_df["anomalyScore"] >= eval_df["customerThreshold"]).astype(int)
    eval_df["anomalyRiskScore"] = [
        normalize_ml_score(score, threshold)
        for score, threshold in zip(eval_df["anomalyScore"], eval_df["customerThreshold"])
    ]

    supervised_ml_experiment = add_supervised_ml_scores(eval_df)
    eval_df["scoreBreakdown"] = [
        build_score_breakdown(rule_score, ml_score, personal_score, sequence_score, anomaly_risk_score)
        for rule_score, ml_score, personal_score, sequence_score, anomaly_risk_score in zip(
            eval_df["ruleScore"],
            eval_df["mlScore"],
            eval_df["personalPatternScore"],
            eval_df["sequencePatternScore"],
            eval_df["anomalyRiskScore"],
        )
    ]
    eval_df["finalRiskScore"] = [calculate_final_risk_score(breakdown) for breakdown in eval_df["scoreBreakdown"]]
    eval_df["weightedRiskLevel"] = [get_prd_risk_level(score) for score in eval_df["finalRiskScore"]]
    eval_df["detectionReasons"] = [
        build_detection_reasons(rules, personal, sequence, anomaly_reason)
        for rules, personal, sequence, anomaly_reason in zip(
            eval_df["triggeredRules"],
            eval_df["personalReasons"],
            eval_df["sequenceReasons"],
            [
                "정상 거래 분포 기준 anomaly threshold를 초과했습니다." if predicted else None
                for predicted in eval_df["anomalyPredictedLabel"]
            ],
        )
    ]
    eval_df["hybridRiskScore"] = eval_df["finalRiskScore"]
    eval_df["mlPredictedLabel"] = (eval_df["mlScore"] >= MIN_ML_SCORE_FOR_FRAUD).astype(int)
    eval_df["ruleFallbackPredictedLabel"] = (eval_df["ruleScore"] >= MIN_FORCE_RULE_SCORE_FOR_FRAUD).astype(int)
    eval_df["componentPredictedLabel"] = component_prediction(eval_df)
    eval_df["predictedLabel"] = final_prediction(eval_df)
    eval_df["finalDecisionMethod"] = eval_df.apply(decision_method, axis=1)
    eval_df["fallbackTriggeredRules"] = [
        rules if fallback else []
        for rules, fallback in zip(eval_df["triggeredRules"], eval_df["ruleFallbackPredictedLabel"])
    ]
    eval_df["finalDecisionScore"] = [
        max(ml_score, rule_score if fallback else 0, weighted_score)
        for ml_score, rule_score, fallback, weighted_score in zip(
            eval_df["mlScore"],
            eval_df["ruleScore"],
            eval_df["ruleFallbackPredictedLabel"],
            eval_df["finalRiskScore"],
        )
    ]
    eval_df["riskLevel"] = [get_prd_risk_level(score) for score in eval_df["finalDecisionScore"]]
    eval_df["recommendedAction"] = [recommended_action(score) for score in eval_df["finalDecisionScore"]]
    eval_df["decisionScore"] = eval_df["finalDecisionScore"]

    matrix = confusion_matrix(eval_df["label"], eval_df["predictedLabel"], labels=[0, 1])
    report = classification_report(
        eval_df["label"],
        eval_df["predictedLabel"],
        target_names=["normal", "anomaly"],
        output_dict=True,
        zero_division=0,
    )
    pr_auc = average_precision_score(eval_df["label"], eval_df["decisionScore"])

    flagged = eval_df[eval_df["predictedLabel"] == 1].sort_values(
        ["finalDecisionScore", "mlScore", "anomalyScore"],
        ascending=False,
    )
    false_positives = eval_df[(eval_df["label"] == 0) & (eval_df["predictedLabel"] == 1)].sort_values(
        ["finalDecisionScore", "mlScore", "anomalyScore"],
        ascending=False,
    )
    false_negatives = eval_df[(eval_df["label"] == 1) & (eval_df["predictedLabel"] == 0)].sort_values(
        ["finalDecisionScore", "mlScore", "anomalyScore"],
        ascending=False,
    )
    diagnostic_columns = [
        "transactionId",
        "customerRef",
        "amount",
        "occurredAt",
        "countryCode",
        "city",
        "deviceId",
        "paymentMethod",
        "merchantCategory",
        "scenario",
        "label",
        "ruleScore",
        "mlScore",
        "anomalyRiskScore",
        "finalRiskScore",
        "finalDecisionScore",
        "finalDecisionMethod",
        "mlPredictedLabel",
        "ruleFallbackPredictedLabel",
        "componentPredictedLabel",
        "riskLevel",
        "recommendedAction",
        "scoreBreakdown",
        "detectionReasons",
        "fallbackTriggeredRules",
        "personalPatternScore",
        "sequencePatternScore",
        "anomalyScore",
        "customerThreshold",
        "triggeredRules",
    ]
    result = {
        "dataset": str(DATA_PATH),
        "rows": int(len(eval_df)),
        "trainRows": int(len(train_df)),
        "customers": int(eval_df["customerRef"].nunique()),
        "actualAnomalies": int(eval_df["label"].sum()),
        "predictedAnomalies": int(eval_df["predictedLabel"].sum()),
        "threshold": {
            "method": "normal-train-score-quantile",
            "quantile": THRESHOLD_QUANTILE,
            "globalAnomalyScoreThreshold": global_threshold,
            "customerAnomalyScoreThresholds": customer_thresholds,
            "minRuleScoreForFraud": MIN_RULE_SCORE_FOR_FRAUD,
            "minHybridScoreForFraud": MIN_HYBRID_SCORE_FOR_FRAUD,
            "minPersonalScoreForFraud": MIN_PERSONAL_SCORE_FOR_FRAUD,
            "minSequenceScoreForFraud": MIN_SEQUENCE_SCORE_FOR_FRAUD,
            "minMlScoreForFraud": MIN_ML_SCORE_FOR_FRAUD,
            "minForceRuleScoreForFraud": MIN_FORCE_RULE_SCORE_FOR_FRAUD,
            "finalDecisionMethod": "supervised_ml_score_with_rule_fallback",
            "ruleScoreWeight": RULE_SCORE_WEIGHT,
            "mlScoreWeight": ML_SCORE_WEIGHT,
            "finalScoreWeights": {
                "ruleScore": 0.30,
                "mlScore": 0.35,
                "personalPatternScore": 0.20,
                "sequencePatternScore": 0.10,
                "anomalyScore": 0.05,
            },
        },
        "features": FEATURE_COLUMNS,
        "confusionMatrix": {
            "trueNormal_predNormal": int(matrix[0][0]),
            "trueNormal_predAnomaly": int(matrix[0][1]),
            "trueAnomaly_predNormal": int(matrix[1][0]),
            "trueAnomaly_predAnomaly": int(matrix[1][1]),
        },
        "classificationReport": report,
        "prAuc": float(pr_auc),
        "supervisedMlExperiment": {
            **supervised_ml_experiment,
            "thresholdSweep": supervised_ml_threshold_sweep(eval_df),
        },
        "thresholdSweep": threshold_sweep(eval_df),
        "componentThresholdSweep": component_threshold_sweep(eval_df),
        "scenarioBreakdown": scenario_breakdown(eval_df),
        "holdoutMethodComparison": holdout_method_comparison(eval_df),
        "topFalsePositives": false_positives[diagnostic_columns].head(20).to_dict(orient="records"),
        "topFalseNegatives": false_negatives[diagnostic_columns].head(20).to_dict(orient="records"),
        "topFlaggedTransactions": flagged[
            [
                "transactionId",
                "customerRef",
                "amount",
                "occurredAt",
                "countryCode",
                "city",
                "deviceId",
                "paymentMethod",
                "merchantCategory",
                "scenario",
                "label",
                "ruleScore",
                "mlScore",
                "anomalyRiskScore",
                "finalRiskScore",
                "finalDecisionScore",
                "finalDecisionMethod",
                "mlPredictedLabel",
                "ruleFallbackPredictedLabel",
                "componentPredictedLabel",
                "riskLevel",
                "recommendedAction",
                "scoreBreakdown",
                "detectionReasons",
                "fallbackTriggeredRules",
                "personalPatternScore",
                "sequencePatternScore",
                "anomalyScore",
                "amountToAvgRatio",
                "amountToRecent7dAvgRatio",
                "amountToRecent30dAvgRatio",
                "userMedianAmount30d",
                "userStdAmount30d",
                "amountRatioToUserMedian30d",
                "amountZScoreByUser",
                "hourDeviation",
                "recent1hCount",
                "txCountLast5min",
                "txCountLast10min",
                "txCountLast24h",
                "amountSumLast10min",
                "amountSumLast1h",
                "amountSumLast24h",
                "uniqueMerchantCountLast1h",
                "uniqueCategoryCountLast1h",
                "uniqueCountryCountLast24h",
                "recent7dCount",
                "recent30dCount",
                "isFirstDevice",
                "isNewCountryForCustomer",
                "isNewPaymentMethodForCustomer",
                "minutesSinceLastTransaction",
                "amountChangeRatioFromLast",
                "countryChangedFromLast",
                "deviceChangedFromLast",
                "paymentChangedFromLast",
                "distanceFromLastKm",
                "countryTravelSpeedKmh",
                "customerThreshold",
                "triggeredRules",
            ]
        ].head(30).to_dict(orient="records"),
    }

    with RESULT_PATH.open("w", encoding="utf-8") as output_file:
        json.dump(result, output_file, ensure_ascii=False, indent=2, default=str)

    return result


def main() -> None:
    result = train_and_evaluate()
    print(json.dumps({
        "rows": result["rows"],
        "customers": result["customers"],
        "trainRows": result["trainRows"],
        "actualAnomalies": result["actualAnomalies"],
        "predictedAnomalies": result["predictedAnomalies"],
        "threshold": result["threshold"],
        "confusionMatrix": result["confusionMatrix"],
        "anomalyPrecision": round(result["classificationReport"]["anomaly"]["precision"], 4),
        "anomalyRecall": round(result["classificationReport"]["anomaly"]["recall"], 4),
        "anomalyF1": round(result["classificationReport"]["anomaly"]["f1-score"], 4),
        "prAuc": round(result["prAuc"], 4),
    }, ensure_ascii=False, indent=2))
    print(f"saved result: {RESULT_PATH}")


if __name__ == "__main__":
    main()
