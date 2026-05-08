import json
import sys
from pathlib import Path

from fraudEngine import detect_fraud
from test_data import sample_transactions


results = []

for data in sample_transactions:
    result = detect_fraud(data["transaction"], data["context"])
    results.append(result)

    print(f"거래 ID: {result['transactionId']}")
    print(f"위험 점수: {result['riskScore']}")
    print(f"위험 등급: {result['riskLevel']}")
    print("탐지 사유:")

    for rule in result["triggeredRules"]:
        print(f"- {rule['title']} (+{rule['score']}): {rule['reason']}")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("-" * 60)

if "--write-results" in sys.argv:
    result_path = Path(__file__).resolve().parent / "results.json"
    with result_path.open("w", encoding="utf-8") as output_file:
        json.dump(results, output_file, ensure_ascii=False, indent=2)
    print(f"results saved: {result_path}")
