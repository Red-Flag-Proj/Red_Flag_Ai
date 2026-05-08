# FraudGuard 모델 평가 기록

작성 기준일: 2026-05-08

## 1. 현재 결론

Phase 3~4에서 데이터셋을 정상 위장형 이상거래와 오탐 방지용 정상 케이스까지 포함하도록 확장하고, supervised ML 후보를 component threshold 방식과 비교했다. 현재 완료된 검증 세트는 고객 100명, 31,900건, 이상거래 1,300건이다.

| 항목 | 값 |
| --- | ---: |
| 전체 거래 | 31,900건 |
| 정상 거래 | 30,600건 |
| 실제 이상거래 | 1,300건 |
| 예측 이상거래 | 1,324건 |
| 정상인데 이상으로 잡은 거래(FP) | 24건 |
| 이상인데 정상으로 놓친 거래(FN) | 0건 |
| 이상거래 Precision | 0.9819 |
| 이상거래 Recall | 1.0000 |
| 이상거래 F1 | 0.9909 |
| 통합 decision PR-AUC | 0.9918 |
| Supervised ML PR-AUC | 0.9943 |

현재 최종 판정 기준은 `mlScore >= 50`이며, `ruleScore >= 80`은 강제 fallback 탐지로 유지한다. 이 기준은 FN 0건을 유지하면서 FP를 24건으로 낮춘다. Component threshold 방식은 설명 가능성과 fallback 분석을 위한 보조 계층으로 유지한다.

## 2. 데이터셋 구성

`AI Engine/data/personal_customers_10_transactions.csv`는 고객 100명의 synthetic 거래로 구성된다.

| 구분 | 건수 | 설명 |
| --- | ---: | --- |
| 정상 baseline | 30,000건 | 고객별 300건의 일반 거래 |
| 오탐 방지 정상 케이스 | 400건 | 해외여행, 월말 소비, 정상 고액 구매, 등록된 신규 기기 |
| stealth precursor 정상 케이스 | 200건 | 소액 테스트 첫 거래, 동일금액 반복의 첫 거래 |
| 이상거래 | 1,300건 | 고액/해외/새벽/신규기기/정상 위장형 이상거래 |

정상 위장형 이상거래는 다음 시나리오를 포함한다.

| 시나리오 | 실제 이상거래 | 탐지 | 미탐 |
| --- | ---: | ---: | ---: |
| `SMALL_TEST_THEN_LARGE` | 100 | 100 | 0 |
| `SAME_AMOUNT_REPEATED` | 200 | 200 | 0 |
| `RAPID_DISTRIBUTED_MERCHANTS` | 300 | 300 | 0 |
| `DOMESTIC_NEW_CATEGORY_HIGH_AMOUNT` | 100 | 100 | 0 |
| `BURST_DAWN_NEW_DEVICE_METHOD` | 300 | 300 | 0 |
| `FOREIGN_HIGH_AMOUNT_NEW_DEVICE` | 100 | 100 | 0 |
| `DAWN_HIGH_TRANSFER` | 100 | 100 | 0 |
| `NEW_DEVICE_PAYMENT_METHOD` | 100 | 100 | 0 |

소액 테스트 첫 거래와 동일금액 반복의 첫 거래는 단독으로는 패턴이 형성되기 전이므로 `STEALTH_PRECURSOR_*` 정상/관찰 케이스로 라벨링했다. 후속 거래에서 sequence feature가 형성되면 이상거래로 평가한다.

## 3. 현재 아키텍처

```text
generate_personal_data.py
  -> 정상 baseline, 오탐 방지 정상 케이스, 정상 위장형 이상거래 생성

personal_features.py
  -> 개인 baseline history와 sequence history를 분리해 feature 생성
  -> 개인 baseline은 정상 거래만 사용
  -> sequence feature는 실제 시간순 이전 거래를 사용

fraudEngine.py + rules.py
  -> 설명 가능한 ruleScore와 triggeredRules 계산

risk_scoring.py
  -> Rule / ML / Personal / Sequence / Anomaly score breakdown 계산
  -> PRD 가중치 기반 finalRiskScore 계산

train_personal_model.py
  -> 정상 거래만 IsolationForest 학습
  -> 고객별 anomaly threshold 계산
  -> component threshold 기반 최종 predictedLabel 산출
  -> PR-AUC, scenario breakdown, threshold sweep, FP/FN 목록 저장
```

## 4. 주요 판단 기준

현재 최종 이상거래 판단은 supervised ML score 기준으로 산출한다.

```python
predictedLabel = (mlScore >= 50) or (ruleScore >= 80)
```

PRD의 가중치 기반 `finalRiskScore`는 설명과 등급 산출에 사용한다. 현재 `predictedLabel`은 `mlScore >= 50`을 기본으로 하고, `ruleScore >= 80`인 명확한 고위험 룰 조합은 fallback으로 강제 탐지한다.

## 5. Phase 3에서 추가된 평가 산출물

`personal_model_results.json`에는 다음 항목이 자동 저장된다.

| 항목 | 설명 |
| --- | --- |
| `prAuc` | decision score 기준 PR-AUC |
| `thresholdSweep` | hybrid threshold별 Precision/Recall/F1 |
| `componentThresholdSweep` | personal/sequence threshold 조합별 결과 |
| `scenarioBreakdown` | 시나리오별 TP/FP/FN/Precision/Recall/F1 |
| `topFalsePositives` | 오탐 상위 거래와 score breakdown |
| `topFalseNegatives` | 미탐 상위 거래와 score breakdown |
| `topFlaggedTransactions` | 탐지 거래 상위 목록 |

현재 hybrid threshold sweep는 component threshold가 우선 작동하기 때문에 결과 차이가 작다. 실제 조정 포인트는 `componentThresholdSweep`의 `personalThreshold`, `sequenceThreshold`다.

## 6. 남은 리스크와 다음 조치

- Phase 4에서 `LogisticRegression(class_weight='balanced')` 기반 supervised ML score를 5-fold out-of-fold 방식으로 산출했다.
- supervised ML 단독 기준 `mlScore >= 50`은 OOF 기준 TP 1,300, FP 24, FN 0으로 현재 component threshold 판정보다 오탐이 적다.
- 다만 현재 데이터가 synthetic이므로 supervised ML을 바로 운영 판정으로 대체하지 않고, 다음 검증 데이터셋에서도 같은 개선이 유지되는지 확인해야 한다.
- 현재 FP 24건은 `topFalsePositives`와 `scenarioBreakdown`에서 추적한다.
- 해외여행 정상 케이스는 여행 상태, 사전 등록, 국가 체류 기간 같은 운영 context가 없으면 오탐으로 남기 쉽다.
- `sequencePatternScore >= 20`은 정상 위장형 이상거래 탐지에 효과적이지만, 정상 반복 구매가 많은 데이터에서는 오탐을 늘릴 수 있다.
- Phase 4 다음 작업은 supervised ML 기준을 운영 판정에 반영할지 결정하기 위해, `mlScore >= 50` 후보와 현재 component threshold 후보를 별도 데이터셋에서 비교하는 것이다.
- Phase 5에서는 모델 저장/로드, 운영 API, 거래 상태별 baseline 반영 정책을 정리해야 한다.

## 7. Component Threshold vs Supervised ML 비교

현재 100명/31,900건 검증 기준 비교 결과는 다음과 같다.

| 방식 | 조건 | 예측 이상 | TP | FP | FN | Precision | Recall | F1 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 현재 component threshold | rule/personal/sequence/anomaly/hybrid OR 조건 | 1,557 | 1,300 | 257 | 0 | 0.8349 | 1.0000 | 0.9100 |
| supervised ML 후보 | `mlScore >= 50` OOF | 1,324 | 1,300 | 24 | 0 | 0.9819 | 1.0000 | 0.9909 |
| supervised ML 보수 후보 | `mlScore >= 90` OOF | 1,320 | 1,300 | 20 | 0 | 0.9848 | 1.0000 | 0.9924 |

추천은 다음과 같다.

1. 현재 검증 기준으로는 `mlScore >= 50` 후보가 가장 좋다. FN 0을 유지하면서 FP를 257건에서 24건으로 줄인다.
2. 시간순 holdout에서도 `mlScore >= 50`은 TP 260, FP 4, FN 0으로 component current(TP 260, FP 34, FN 0)보다 우세하다.
3. 신규 고객 holdout에서도 `mlScore >= 50`은 TP 260, FP 4, FN 0으로 component current(TP 260, FP 54, FN 0)보다 우세하다.
4. 따라서 프로토타입의 현재 최종 판정 기준은 `mlScore >= 50`이다.
5. component threshold는 완전히 제거하지 않고 설명 가능성, fallback, 룰 기반 강제 차단 조건으로 유지한다.
6. 100,000건 전체 학습은 현재 feature 생성/IsolationForest 경로가 30분 이상 걸리므로, Phase 5 전에 feature 생성 최적화나 캐싱을 적용한 뒤 재검증한다.

## 8. 데이터 확장 계획

현재 완료된 학습 데이터는 31,900건, 이상거래 1,300건, 고객 100명이다. 지도학습 방식의 일반화 성능은 1차로 확인됐지만, 100,000건 이상 학습은 현재 feature 생성 성능상 최적화 후 재시도해야 한다.

| 항목 | 현재 | 다음 목표 |
| --- | ---: | ---: |
| 고객 수 | 100명 | 100명 이상 유지 |
| 전체 거래 | 31,900건 완료, 101,900건 생성 가능 | 100,000건 이상 학습 완료 |
| 이상거래 | 1,300건 | 1,000건 이상 유지 |
| 정상 예외 케이스 | 600건 | 2,000건 이상 |
| 검증 방식 | 5-fold OOF + 시간순 holdout + 신규 고객 holdout | 100k 기준 재검증 |

확장 데이터에는 다음을 추가한다.

- 정상 해외여행/출장 체류 기간 케이스
- 정상 반복 구독/정기 결제 케이스
- 정상 신규 기기 등록 후 거래 케이스
- 급여일/명절/월말 소비 증가 케이스
- 정상 소액 반복 구매 케이스
- 정상 신규 가맹점 탐색 케이스
- 더 약한 정상 위장형 이상거래
- 고객군별 소비 편차와 개념 드리프트

100k 재검증 전 필요한 최적화:

- `build_context_from_history()`의 고객 history 반복 스캔을 rolling/window 기반으로 최적화한다.
- IsolationForest 학습/평가를 샘플링하거나 별도 옵션으로 분리한다.
- `train_personal_model.py`에 `--skip-isolation` 또는 `--fast-eval` 옵션을 추가해 supervised ML 비교를 빠르게 반복할 수 있게 한다.
- 100k 기준에서도 `mlScore >= 50` 후보가 Recall 0.98 이상 또는 FN 3건 이하를 유지하는지 확인한다.

## 9. 검증 명령

이 환경에서는 `python` 명령이 PATH에 없을 수 있으므로 번들 Python을 사용한다.

```powershell
$env:PYTHONPATH = (Resolve-Path .pydeps).Path
& 'C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\platform\bundledpython\python.exe' "AI Engine\generate_personal_data.py"
& 'C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\platform\bundledpython\python.exe' "AI Engine\train_personal_model.py"
& 'C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\platform\bundledpython\python.exe' "AI Engine\test.py" --write-results
```

최근 검증 결과:

- `generate_personal_data.py --customers 100 --normal-per-customer 300`: 31,900 rows, normal 30,600, anomaly 1,300
- `train_personal_model.py`: Precision 0.9819, Recall 1.0000, F1 0.9909, 통합 decision PR-AUC 0.9918
- `supervisedMlExperiment`: 5-fold out-of-fold PR-AUC 0.9943, `mlScore >= 50` 기준 Precision 0.9819, Recall 1.0000, F1 0.9909
- `holdoutMethodComparison.timeHoldout.mlScoreGte50`: TP 260, FP 4, FN 0
- `holdoutMethodComparison.newCustomerHoldout.mlScoreGte50`: TP 260, FP 4, FN 0
- `test.py --write-results`: 통과, `results.json` 생성
