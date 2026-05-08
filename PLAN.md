# FraudGuard 단계별 개발 계획

작성 기준일: 2026-05-07

## 1. 계획 수립 목적

본 계획은 `PRD.md`의 목표를 기준으로 현재 FraudGuard 프로젝트를 단계적으로 확장하기 위한 실행 계획이다. 현재 프로젝트는 룰 기반 FDS, 개인 이력 feature, IsolationForest 기반 이상탐지 실험까지 일부 구현되어 있으나, PRD가 요구하는 최종 구조인 `Rule Score + ML Score + Personal Pattern Score + Sequence Pattern Score + Anomaly Score`가 명확한 아키텍처 계층으로 분리되어 있지는 않다.

따라서 작업은 기능 추가부터 시작하지 않고, 먼저 현재 프로젝트가 잡지 못하는 위험 패턴과 구조적 한계를 확인한 뒤 Phase 1, 2, 3 순서로 진행한다.

## 2. 현재 아키텍처 1차 파악

현재 프로젝트의 주요 흐름은 다음과 같다.

```text
AI Engine/generate_personal_data.py
  -> synthetic 거래 데이터 생성
  -> AI Engine/data/personal_customers_10_transactions.csv

AI Engine/personal_features.py
  -> 고객별 과거 거래 이력 기반 context 생성
  -> 평균 대비 금액 비율, 최근 7일/30일 평균, 직전 거래 대비 변화, 국가 이동 속도 등 계산

AI Engine/rules.py
  -> 명시적 FDS rule 평가
  -> 고액, 반복 거래, 해외 거래, 새벽 거래, 신규 기기, 국가 이동 속도 탐지

AI Engine/fraudEngine.py
  -> rule 결과를 합산해 riskScore와 triggeredRules 반환

AI Engine/train_personal_model.py
  -> 정상 거래만으로 IsolationForest 학습
  -> 고객별 anomaly threshold 계산
  -> ruleScore와 mlRiskScore를 결합해 최종 predictedLabel 산출

AI Engine/MODEL_EVALUATION.md
  -> 현재 모델 평가 결과와 운영 기준 문서화
```

현재 구현은 단순 룰 기반 MVP보다 진전되어 있으며, 고객별 정상 패턴과 비지도 이상탐지를 일부 반영한다. 그러나 운영 가능한 하이브리드 FDS로 보기에는 점수 체계, feature 계층, 평가 루프, 설명 가능성, 데이터 시나리오가 아직 명확하게 분리되어 있지 않다.

## 3. 현재 프로젝트가 잡지 못하거나 약하게 잡는 부분

### 3.1 점수 체계가 PRD 구조와 다름

PRD는 최종 위험도를 다음처럼 분리한다.

```text
Final Risk Score =
0.30 * Rule Score
+ 0.35 * ML Score
+ 0.20 * Personal Pattern Score
+ 0.10 * Sequence Pattern Score
+ 0.05 * Anomaly Score
```

하지만 현재 `train_personal_model.py`는 `ruleScore * 1.0 + mlRiskScore * 0.45` 중심이다. 개인 패턴 점수와 거래 흐름 점수는 feature로는 일부 들어가지만, 독립 점수로 산출되지 않는다. 이 때문에 관리자 화면이나 평가 문서에서 "왜 이 거래가 개인 패턴 이탈인지", "왜 거래 흐름상 이상인지"를 계층별로 설명하기 어렵다.

### 3.2 거래 흐름 feature가 충분히 세분화되지 않음

현재 구현은 `recent1hCount`, `minutesSinceLastTransaction`, `amountChangeRatioFromLast` 등을 사용한다. 그러나 PRD가 요구하는 아래 항목은 아직 명확하지 않거나 부족하다.

- `tx_count_last_5min`, `tx_count_last_10min`, `tx_count_last_24h`
- `amount_sum_last_10min`, `amount_sum_last_1h`, `amount_sum_last_24h`
- `unique_merchant_count_last_1h`
- `unique_category_count_last_1h`
- `unique_country_count_last_24h`
- `small_test_then_large_tx`
- `amount_increasing_pattern`
- `same_amount_repeated`
- `rapid_multi_transaction`

특히 소액 테스트 후 고액 결제, 점진적 금액 증가, 동일 금액 반복 결제, 여러 가맹점 분산 결제는 현재 룰과 synthetic 데이터에서 충분히 독립적으로 검증되지 않는다.

### 3.3 개인 패턴 feature가 일부 빠져 있음

현재는 평균 대비 금액 비율, 최근 7일/30일 평균, 신규 국가, 신규 결제수단, 신규 기기 등을 사용한다. PRD 기준으로는 다음 항목 보강이 필요하다.

- `user_median_amount_30d`
- `user_std_amount_30d`
- `amount_ratio_to_user_median_30d`
- `amount_z_score_by_user`
- `new_merchant_for_user`
- `new_category_for_user`
- `user_foreign_tx_ratio`
- `user_night_tx_ratio`
- `is_unusual_payment_method`
- 사용자별 위험 점수 threshold

현재 구조는 고객별 threshold를 anomaly score에 적용하지만, 개인 패턴 점수 자체의 threshold는 별도로 없다.

### 3.4 지도학습 ML Score는 실험 단계

PRD는 `Supervised ML Score`도 최종 구성요소로 언급한다. 초기 학습 코드는 정상 거래만 학습하는 IsolationForest 중심이었으므로 비지도 이상탐지에는 적합했지만, 라벨이 있는 이상거래를 활용한 지도학습 점수는 없었다.

Phase 4 1차 구현 후에는 `LogisticRegression(class_weight='balanced')` 기반 out-of-fold 확률을 `mlScore`로 산출한다. 다만 현재 데이터가 synthetic이고 라벨 수가 제한적이므로, supervised ML을 운영 판정에 바로 반영하기보다 `supervisedMlExperiment`에 실험 결과를 저장하고 별도 검증 데이터셋에서 threshold를 비교한 뒤 반영 여부를 결정한다.

### 3.5 가맹점/업종 정보 활용이 부족함

`generate_personal_data.py`는 `merchantCategory`를 생성하지만, 현재 실시간 transaction 변환과 feature/score 계층에서는 PRD가 요구하는 가맹점/업종 기반 feature가 충분히 반영되지 않는다. 특히 `new_merchant_for_user`, `new_category_for_user`, `unique_merchant_count_last_1h`, `unique_category_count_last_1h`는 정상 위장형 이상거래와 분산 결제 탐지에 중요하다.

### 3.6 평가 지표가 충분히 자동화되어 있지 않음

초기 `MODEL_EVALUATION.md`는 Precision, Recall, F1, FP, FN 중심으로 정리되어 있었다. Phase 3 1차 구현 후에는 `train_personal_model.py`가 PR-AUC, hybrid threshold sweep, personal/sequence component threshold sweep, scenario breakdown, FP/FN 목록을 자동 산출한다.

필요한 평가 기준은 다음과 같다.

- Recall 우선 평가
- False Negative 최소화
- Precision과 False Positive 운영 가능성 확인
- PR-AUC 추가
- threshold 조정 실험 기록
- 시나리오별 탐지율 확인

### 3.7 코드와 문서의 인코딩/표시 품질 문제가 있음

일부 Python 파일 주석과 출력 문자열이 깨진 상태로 보인다. 모델 품질과 직접 관련되지는 않지만, 관리자 설명 가능성 및 발표 자료 품질에 영향을 준다. Phase 1에서 한국어 출력 문자열과 문서 인코딩을 정리해야 한다.

### 3.8 개인 baseline 오염 가능성

초기 구조에서는 학습 feature 생성 시 시간순으로 고객별 history를 누적하면서 이상거래 row도 이후 거래의 과거 이력에 포함될 수 있었다. 실제 운영에서도 이상거래 확정 전 거래가 baseline에 들어가면 개인 평균, 신규 국가/기기 여부, 거래 빈도 기준이 오염될 수 있다.

Task 2 수정 후 `train_personal_model.py`의 학습/평가 feature 생성에서는 `label == 0`인 정상 거래만 고객 history에 추가하도록 변경되어, 확정 이상거래가 future baseline에 들어가는 문제는 학습 검증 범위에서 해소되었다. 다만 운영 환경에서는 거래 상태가 정상/보류/확정 이상거래로 나뉘므로, 실시간 baseline 반영 정책은 Phase 5 또는 운영 API 설계 시 별도로 정리해야 한다.

## 3.9 Task 2 진행 후 현재 해소된 항목

Task 2 수정과 재검증 기준으로, 초기 gap 중 다음 항목은 현재 코드에 반영되었다.

- `risk_scoring.py`에 PRD 가중치 기반 score breakdown 구조가 추가되었다.
- `personalPatternScore`, `sequencePatternScore`, `anomalyRiskScore`, `finalRiskScore`, `detectionReasons`, `recommendedAction`이 학습/평가 결과에 산출된다.
- 거래 흐름 feature가 `txCountLast5min`, `txCountLast10min`, `txCountLast24h`, `amountSumLast10min`, `amountSumLast1h`, `amountSumLast24h`, `uniqueMerchantCountLast1h`, `uniqueCategoryCountLast1h`, `uniqueCountryCountLast24h`로 확장되었다.
- 사기 시나리오 feature인 `smallTestThenLargeTx`, `amountIncreasingPattern`, `sameAmountRepeated`, `rapidMultiTransaction`이 구현되었다.
- 개인 패턴 feature인 `userMedianAmount30d`, `userStdAmount30d`, `amountRatioToUserMedian30d`, `amountZScoreByUser`, `newMerchantForUser`, `newCategoryForUser`, `userForeignTxRatio`, `userNightTxRatio`가 구현되었다.
- 학습/평가 baseline은 확정 이상거래를 future history에 넣지 않도록 정리되었다.

남은 주요 gap은 supervised ML score의 운영 판정 반영 여부 결정, threshold 조정 정책 확정, 모델 저장/로드 및 운영 API 정리다. Phase 3에서 PR-AUC/threshold별 자동 평가와 synthetic 시나리오 확장은 1차 구현되었고, Phase 4에서 supervised ML score도 실험값으로 구현되었다. 다만 FP 26건을 줄이기 위한 운영 threshold 튜닝과 별도 검증 데이터셋 비교는 아직 남아 있다.

## 4. 아키텍처 변경 시 예상 문제점

### 4.1 feature 생성 책임이 커질 수 있음

`personal_features.py`에 모든 feature와 점수 계산을 계속 추가하면 파일이 비대해지고 테스트가 어려워진다. PRD의 계층을 반영하려면 feature 생성과 score 계산을 분리하는 것이 좋다.

권장 구조:

```text
personal_features.py
  -> 고객 이력 기반 원천 feature 생성

sequence_features.py
  -> 최근 거래 흐름 feature 생성

risk_scoring.py
  -> Rule, Personal, Sequence, Anomaly, ML 점수 결합

fraudEngine.py
  -> 실시간 거래 판단 API 역할

train_personal_model.py
  -> 학습/평가 orchestration 역할
```

### 4.2 기존 dictionary contract가 깨질 위험

현재 `transaction`과 `context`는 명시적 schema 없이 dictionary key로 연결되어 있다. feature를 늘릴 때 key 이름이 바뀌면 `rules.py`, `fraudEngine.py`, `train_personal_model.py`, `test_data.py`가 동시에 깨질 수 있다.

Phase 1에서는 key 명세를 문서화하고, 가능한 경우 기본값 처리와 누락 key 방어 로직을 추가해야 한다.

### 4.3 synthetic 데이터가 모델 성능을 과대평가할 수 있음

현재 데이터는 10명 고객, 고객별 정상 980건과 이상 6건으로 구성된 synthetic 데이터다. 이상 시나리오가 비교적 명확하면 모델 성능이 실제보다 높게 보일 수 있다.

따라서 Phase 2부터는 PRD의 "정상 위장형" 이상거래를 더 어렵게 생성해야 한다.

예:

- 고액이 아닌 정상 범위 금액의 반복 결제
- 평소 시간대에 발생하는 이상거래
- 해외가 아닌 국내 신규 가맹점 이상거래
- 신규 기기 없이 발생하는 소액 테스트 후 고액 결제
- 정상 고객의 여행/고액 구매를 오탐으로 잡지 않는 negative case

### 4.4 탐지율과 오탐률의 trade-off

현재 모델은 Recall이 높지만 FP가 존재한다. PRD는 미탐 감소를 1순위로 두지만, 금융권 운영에서는 오탐이 너무 많으면 관리자 검토 비용과 고객 불편이 증가한다.

따라서 Phase별 목표는 단순히 risk score를 높이는 것이 아니라, threshold 실험과 운영 구간 정의까지 포함해야 한다.

### 4.5 rule score 중복 반영 위험

현재 `ruleScore`는 IsolationForest 입력 feature에도 포함되고, 최종 hybrid score에도 다시 반영된다. 이 구조는 설명 가능한 rule 신호를 강하게 반영한다는 장점이 있지만, 특정 룰이 비지도 점수와 최종 점수에 중복 반영되어 risk score를 과도하게 끌어올릴 수 있다. Phase 2에서 점수 계층을 분리할 때 `ruleScore`를 모델 입력에 유지할지, 최종 결합 단계에서만 사용할지 비교 실험해야 한다.

## 5. PRD 기준 개선 효과

PRD에 따라 작업을 진행하면 다음 개선이 기대된다.

| 개선 영역 | 현재 한계 | 개선 후 효과 |
| --- | --- | --- |
| 개인별 소비 패턴 | 평균/최근 평균 중심, 독립 점수 없음 | 사용자별 금액/시간/국가/가맹점 이탈을 명확히 설명 |
| 거래 흐름 분석 | 최근 1시간 수와 직전 금액 비율 중심 | 소액 테스트 후 고액 결제, 반복 결제, 분산 결제 탐지 강화 |
| 점수 구조 | Rule + ML 중심 | Rule/ML/Personal/Sequence/Anomaly 점수별 책임 분리 |
| 평가 | Precision/Recall/F1 중심 문서화 | PR-AUC, threshold 실험, 시나리오별 탐지율 추가 |
| 운영 설명 | triggeredRules 중심 | 탐지 사유와 추천 조치를 점수 출처별로 제공 |
| 데이터 | synthetic 이상거래가 명확함 | 정상 위장형 및 오탐 방지용 정상 케이스 추가 |

## 6. Phase별 실행 계획

### Phase 1. 현재 한계 확인 및 기반 정리

목표: 현재 프로젝트가 PRD 대비 무엇을 잡고, 무엇을 못 잡는지 명확히 만든다.

작업 항목:

1. 현재 feature와 PRD feature 매핑 표 작성
2. `transaction`/`context` dictionary key 계약 정리
3. 깨진 한국어 주석과 출력 문자열 정리
4. 기존 smoke test(`AI Engine/test.py`)의 sample case를 PRD 시나리오 기준으로 재정리
5. 현재 모델 평가 결과를 기준선으로 고정
6. 현재 미탐 2건과 오탐 10건의 시나리오 분석
7. `MODEL_EVALUATION.md`에 기준선, threshold, 평가 조건 업데이트
8. `merchantCategory`, customer history, rule score 중복 사용 여부 점검

완료 기준:

- 현재 구현 feature와 PRD 요구 feature의 gap이 문서화된다.
- smoke test가 정상/고액/해외/새벽/반복/신규기기 케이스를 명확히 검증한다.
- 이후 Phase에서 비교할 baseline metric이 고정된다.

검증 명령:

```powershell
python "AI Engine\test.py"
python "AI Engine\train_personal_model.py"
```

### Phase 2. PRD 핵심 feature와 점수 계층 구현

목표: PRD의 핵심인 개인 패턴 점수와 거래 흐름 점수를 독립 계층으로 구현한다.

진행 상태: Task 2에서 핵심 feature와 점수 계층은 1차 구현되었고, smoke test와 학습 검증을 통과했다. 이후 작업은 현재 구현을 기준으로 시나리오 확장, 평가 자동화, 지도학습 ML Score 실험으로 넘어간다.

작업 항목:

1. 거래 흐름 feature 추가
   - `tx_count_last_5min`
   - `tx_count_last_10min`
   - `tx_count_last_24h`
   - `amount_sum_last_10min`
   - `amount_sum_last_1h`
   - `amount_sum_last_24h`
   - `unique_merchant_count_last_1h`
   - `unique_category_count_last_1h`
   - `unique_country_count_last_24h`
2. 사기 시나리오 feature 추가
   - `small_test_then_large_tx`
   - `amount_increasing_pattern`
   - `same_amount_repeated`
   - `rapid_multi_transaction`
3. 개인 패턴 feature 추가
   - `user_median_amount_30d`
   - `user_std_amount_30d`
   - `amount_z_score_by_user`
   - `new_merchant_for_user`
   - `new_category_for_user`
   - `user_foreign_tx_ratio`
   - `user_night_tx_ratio`
4. baseline 오염 방지 정책 추가
   - 학습 feature 생성 시 정상 거래만 고객 baseline에 반영하는 옵션
   - 운영 시 보류/확정 상태에 따른 baseline 반영 규칙
5. `risk_scoring.py` 또는 동등한 모듈을 추가해 점수 계층 분리
   - Rule Score
   - Personal Pattern Score
   - Sequence Pattern Score
   - Anomaly Score
   - 추후 ML Score placeholder
6. PRD 가중치 기반 최종 risk score 산출
7. 탐지 사유를 점수 계층별로 반환
8. rule score를 모델 feature와 최종 score에 동시에 쓰는 방식의 중복 반영 여부 실험

완료 기준:

- 학습/평가 결과에서 점수 구성요소가 분리되어 확인된다. Task 2 기준 `scoreBreakdown`, `finalRiskScore`, `detectionReasons`, `recommendedAction` 산출을 확인했다.
- 정상 위장형 이상거래 시나리오가 rule 하나에만 의존하지 않고 personal/sequence/anomaly 점수로 잡힌다.
- 관리자 설명 문구가 `triggeredRules`뿐 아니라 feature 기반 사유까지 제공된다.

검증 명령:

```powershell
python "AI Engine\test.py" --write-results
python "AI Engine\train_personal_model.py"
```

### Phase 3. 데이터 시나리오 확장 및 평가 자동화

목표: PRD의 핵심 문제인 클래스 불균형, 정상 위장형 거래, 개념 드리프트를 평가 가능한 형태로 만든다.

진행 상태: Phase 3 1차 구현을 완료했다. `generate_personal_data.py`는 정상 위장형 이상거래와 오탐 방지 정상 케이스를 생성하고, `train_personal_model.py`는 PR-AUC, threshold sweep, component threshold sweep, scenario breakdown, FP/FN 목록을 `personal_model_results.json`에 저장한다.

작업 항목:

1. synthetic 데이터에 정상 위장형 이상거래 추가
   - 소액 테스트 후 고액 결제
   - 평소 시간대 반복 결제
   - 신규 가맹점 고액 결제
   - 동일 금액 반복 결제
   - 여러 가맹점 분산 결제
2. 오탐 방지용 정상 케이스 추가
   - 여행 중 해외 결제
   - 정상 고액 구매
   - 정상 신규 기기 등록 후 거래
   - 급여일/월말 소비 증가
3. 평가 자동화
   - Precision, Recall, F1
   - PR-AUC
   - FP/FN
   - 시나리오별 탐지율
   - threshold별 결과 비교
4. threshold 실험
   - rule threshold
   - hybrid threshold
   - anomaly quantile
   - 개인별 threshold
5. `personal_model_results.json` 구조 개선
   - score breakdown
   - scenario breakdown
   - top false positives
   - top false negatives

완료 기준:

- 현재보다 어려운 synthetic 데이터에서도 미탐과 오탐을 시나리오별로 설명할 수 있다. Phase 3 1차 결과는 `scenarioBreakdown`으로 확인한다.
- PRD의 우선순위인 미탐 감소를 유지하면서 오탐 감소 실험이 가능하다. `mlScore >= 50` 기준 FN 0, Recall 1.0을 유지하면서 FP를 24건까지 낮췄다.
- threshold 변경 근거가 수치로 남는다. `thresholdSweep`과 `componentThresholdSweep`에 hybrid/personal/sequence threshold별 결과를 저장한다.

검증 명령:

```powershell
python "AI Engine\generate_personal_data.py"
python "AI Engine\train_personal_model.py"
```

### Phase 4. 지도학습 ML Score 실험

목표: 라벨이 적은 조건에서 지도학습 점수를 보조적으로 도입할 수 있는지 검증한다.

진행 상태: Phase 4 1차 실험을 완료했다. `train_personal_model.py`는 `LogisticRegression(class_weight='balanced')`를 5-fold stratified out-of-fold 방식으로 평가하고, 예측 확률을 `mlScore`로 변환해 `scoreBreakdown`에 포함한다. 결과는 `supervisedMlExperiment`에 저장된다.

작업 항목:

1. 라벨 기반 train/evaluation split 설계
2. 클래스 불균형 대응 실험
   - `class_weight = "balanced"`
   - threshold 조정
   - 필요 시 oversampling은 별도 실험으로 제한
3. 후보 모델 실험
   - Logistic Regression 또는 RandomForest부터 시작
   - 복잡한 모델은 평가 기준이 안정된 뒤 도입
4. ML Score를 최종 score breakdown에 통합
5. 지도학습 모델이 비지도 모델보다 실제로 개선되는지 비교

완료 기준:

- 지도학습 점수가 PRD의 `ML Score`로 의미 있게 들어갈지 판단된다. 100명/31,900건 검증 기준 supervised ML PR-AUC는 0.9943이다.
- 라벨 부족 때문에 성능이 불안정하면, 운영 구조에서는 `ML Score`를 낮은 가중치 또는 후순위 실험으로 유지한다. 현재 100명/31,900건 synthetic 데이터에서는 `mlScore >= 50` 후보가 OOF 기준 FP 24, FN 0으로 좋지만, 100k 최적화 검증 전 component threshold를 완전히 제거하지는 않는다.

### Phase 5. 운영형 결과 출력 및 보고서 정리

목표: 탐지 결과를 발표/보고/운영 관점에서 설명 가능한 형태로 만든다.

작업 항목:

1. 최종 결과 출력 구조 정리
   - transactionId
   - finalRiskScore
   - riskLevel
   - scoreBreakdown
   - detectionReasons
   - recommendedAction
2. 위험도 구간을 PRD 기준으로 통일
   - 0~39 정상
   - 40~59 주의
   - 60~79 의심
   - 80~100 고위험
3. `MODEL_EVALUATION.md` 업데이트
4. README 실행 방법 보강
5. 발표용 요약과 아키텍처 다이어그램 추가

완료 기준:

- 단순히 "이상거래"라고 표시하지 않고, 왜 이상거래인지 관리자에게 설명할 수 있다.
- PRD의 최종 한 줄 컨셉인 "개인별 소비 패턴과 최근 거래 흐름을 함께 분석하는 하이브리드 이상거래 탐지 모델"이 코드와 결과물에 반영된다.

## 7. Phase 우선순위

권장 진행 순서는 다음과 같다.

1. Phase 1: 현재 한계 확인 및 baseline 고정
2. Phase 2: 개인/거래흐름 점수 계층 구현
3. Phase 3: 데이터 시나리오와 평가 자동화
4. Phase 4: 지도학습 ML Score 실험
5. Phase 5: 운영형 결과 출력 및 문서화

Phase 4는 라벨 수가 적어 성능이 불안정할 수 있으므로 Phase 2, 3 이후에 진행한다. 먼저 비지도 이상탐지와 설명 가능한 룰/패턴 점수 체계를 안정화하는 것이 더 중요하다.

## 8. 작업 전 필수 확인 체크리스트

각 Phase 시작 전 다음을 확인한다.

- 현재 baseline metric이 저장되어 있는가?
- 새 feature가 과거 이력만 사용하고 미래 데이터를 보지 않는가?
- 정상 위장형 이상거래와 오탐 방지용 정상거래가 모두 테스트되는가?
- threshold 변경 전후의 FP/FN 변화가 기록되는가?
- 탐지 사유가 관리자에게 설명 가능한 문장으로 제공되는가?
- generated artifact와 source file이 구분되어 관리되는가?

## 9. subagent 검증 기록

본 계획은 작성 후 subagent를 통해 다음 관점으로 검증했다.

- PRD 요구사항과 현재 코드의 gap이 정확히 반영되었는가?
- Phase 순서가 현재 아키텍처의 리스크를 고려하는가?
- 구현 전 확인해야 할 문제점이 충분히 명시되었는가?
- 아키텍처 변경으로 인한 contract 및 평가 리스크가 포함되었는가?

검증 결과:

- 현재 구조를 `룰 기반 FDS + 개인화 feature + 비지도 이상탐지 IsolationForest + hybrid score` 프로토타입으로 보는 것이 타당하다고 확인했다.
- 초기 PRD 대비 이미 구현된 부분은 고객별 기준선, 직전 거래 대비 feature 일부, 최근 1시간 거래 수, IsolationForest, 고객별 anomaly threshold, `triggeredRules` 기반 설명 가능성이었다.
- 초기 PRD 대비 부족한 부분은 `Supervised ML Score` 부재, `Rule/ML/Personal/Sequence/Anomaly` 점수 미분리, 가맹점/업종 feature 부족, 사기 시나리오 feature 미구현, PR-AUC 미산출, 모델 저장/로드 및 운영 API 부재였다.
- Task 2 수정 후 `risk_scoring.py`, `personal_features.py`, `train_personal_model.py`, `results.json`, `personal_model_results.json`을 subagent가 읽기 전용으로 재검증했다.
- 재검증 결과 `risk_scoring.py`는 `py_compile`을 통과했고, 두 JSON 결과 파일은 `json.tool` 기준 유효했다.
- `amountChangeRatioFromLast >= 5` 기반 sequence reason, PRD 핵심 personal/sequence feature, `scoreBreakdown`, `finalRiskScore`, `detectionReasons`, `recommendedAction`, `label == 0`만 baseline history에 반영하는 로직이 모두 확인되었다.
- 재검증에서 지적된 불통과 항목은 PLAN.md가 Task 2 완료 상태를 반영하지 못한다는 문서 불일치였으며, 본 문서의 3.8, 3.9, Phase 2 진행 상태, subagent 검증 기록을 갱신해 해소했다.
- 현재 남은 주요 리스크는 supervised ML score를 운영 판정에 반영할지에 대한 검증 부족, FP 26건을 줄이기 위한 threshold 정책 미확정, 모델 저장/로드 및 운영 API 부재, `ruleScore`가 비지도 모델 입력과 최종 점수에 중복 반영될 수 있는 구조다.

Task 2 검증 명령과 결과:

```powershell
& 'C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\platform\bundledpython\python.exe' -m py_compile "AI Engine\risk_scoring.py" "AI Engine\personal_features.py" "AI Engine\fraudEngine.py" "AI Engine\train_personal_model.py"
$env:PYTHONPATH = (Resolve-Path .pydeps).Path; & 'C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\platform\bundledpython\python.exe' "AI Engine\test.py" --write-results
$env:PYTHONPATH = (Resolve-Path .pydeps).Path; & 'C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\platform\bundledpython\python.exe' "AI Engine\train_personal_model.py"
```

학습 검증 결과:

- rows: 9860
- actualAnomalies: 60
- predictedAnomalies: 70
- trueNormal_predAnomaly: 10
- trueAnomaly_predNormal: 0
- anomalyPrecision: 0.8571
- anomalyRecall: 1.0
- anomalyF1: 0.9231

Phase 3~4 최신 검증 결과:

- `generate_personal_data.py --customers 100 --normal-per-customer 300` 실행 결과 rows 31,900, normal 30,600, anomaly 1,300
- `train_personal_model.py` 실행 결과 predictedAnomalies 1,324, FP 24, FN 0
- anomalyPrecision: 0.9819
- anomalyRecall: 1.0
- anomalyF1: 0.9909
- 통합 decision PR-AUC: 0.9918
- `personal_model_results.json`에 `prAuc`, `thresholdSweep`, `componentThresholdSweep`, `scenarioBreakdown`, `topFalsePositives`, `topFalseNegatives` 저장 확인

Phase 4 검증 결과:

- `supervisedMlExperiment.enabled`: true
- supervised model: `LogisticRegression(class_weight='balanced')`
- validation: 5-fold stratified out-of-fold probabilities
- supervised ML PR-AUC: 0.9943
- `mlScore >= 50` OOF 후보 기준 predictedAnomalies 1,324, FP 24, FN 0, Precision 0.9819, Recall 1.0, F1 0.9909
- 시간순 holdout `mlScore >= 50`: TP 260, FP 4, FN 0
- 신규 고객 holdout `mlScore >= 50`: TP 260, FP 4, FN 0
- 현재 최종 운영 판정은 `mlScore >= 50` 기준으로 전환했으며, `ruleScore >= 80`은 강제 fallback 탐지로 유지한다. Component threshold는 fallback/설명 계층으로 유지한다.

## 10. Component Threshold vs Supervised ML 추천

현재 비교 결과는 다음과 같다.

| 방식 | 조건 | 예측 이상 | TP | FP | FN | Precision | Recall | F1 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 이전 component threshold | rule/personal/sequence/anomaly/hybrid OR 조건 | 1,557 | 1,300 | 257 | 0 | 0.8349 | 1.0000 | 0.9100 |
| 현재 최종 판정 | `mlScore >= 50` OOF | 1,324 | 1,300 | 24 | 0 | 0.9819 | 1.0000 | 0.9909 |
| supervised ML 보수 후보 | `mlScore >= 90` OOF | 1,320 | 1,300 | 20 | 0 | 0.9848 | 1.0000 | 0.9924 |

추천:

- 현재 100명/31,900건 검증 기준으로는 `mlScore >= 50` 후보가 가장 좋다. 미탐 0건을 유지하면서 오탐을 257건에서 24건으로 줄인다.
- 시간순 holdout에서도 `mlScore >= 50`은 TP 260, FP 4, FN 0으로 component current(TP 260, FP 34, FN 0)보다 좋다.
- 신규 고객 holdout에서도 `mlScore >= 50`은 TP 260, FP 4, FN 0으로 component current(TP 260, FP 54, FN 0)보다 좋다.
- 따라서 프로토타입의 현재 최종 판정 기준은 `mlScore >= 50` 또는 `ruleScore >= 80` fallback이다.
- 다만 supervised ML은 synthetic 생성 규칙에 과적합될 수 있으므로, component threshold를 완전히 제거하지 않는다. component threshold는 설명 가능성, fallback, 강제 차단 룰로 유지한다.
- 100,000건 전체 학습은 현재 feature 생성/IsolationForest 경로가 30분 이상 걸리므로, Phase 5 전에 feature 생성 최적화 또는 fast evaluation 옵션을 추가한 뒤 재검증한다.

## 11. 다음 데이터 확장 계획

현재 학습 데이터는 31,900건, 이상거래 1,300건, 고객 100명이다. 프로토타입 검증과 holdout 비교에는 충분하지만, 100,000건 이상 학습은 feature 생성 성능 최적화 후 다시 완료해야 한다.

다음 목표 데이터 규모:

| 항목 | 현재 | 다음 목표 |
| --- | ---: | ---: |
| 고객 수 | 100명 | 100명 이상 유지 |
| 전체 거래 | 31,900건 완료, 101,900건 생성 가능 | 100,000건 이상 학습 완료 |
| 이상거래 | 1,300건 | 1,000건 이상 유지 |
| 정상 예외 케이스 | 600건 | 2,000건 이상 |
| 검증 방식 | 5-fold OOF + 시간순 holdout + 신규 고객 holdout | 100k 기준 재검증 |

추가할 데이터 시나리오:

- 정상 해외여행/출장 체류 기간
- 정상 반복 구독/정기 결제
- 정상 신규 기기 등록 후 거래
- 급여일/명절/월말 소비 증가
- 정상 소액 반복 구매
- 정상 신규 가맹점 탐색
- 더 약한 정상 위장형 이상거래
- 고객군별 소비 편차와 개념 드리프트

다음 작업 순서:

1. 완료: `generate_personal_data.py`를 고객 수와 정상 거래 수 기준으로 파라미터화했다.
2. 완료: 시간순 holdout과 신규 고객 holdout을 `train_personal_model.py`에 추가했다.
3. 완료: component threshold, `mlScore >= 50`, `mlScore >= 70/90` 후보를 같은 holdout 기준으로 비교했다.
4. 완료: `MODEL_EVALUATION.md`에 holdout별 Precision/Recall/F1/PR-AUC/FP/FN/scenario breakdown을 기록했다.
5. 다음: 100k 학습을 안정적으로 완료하기 위해 `build_context_from_history()` 반복 스캔 최적화, IsolationForest 옵션 분리, `--fast-eval` 옵션을 추가한다.
6. 다음: Phase 5 운영 출력 구조에 `mlScore >= 50` 기반 추천 판정을 1순위 후보로 반영하되, component threshold를 fallback/설명 계층으로 유지한다.
