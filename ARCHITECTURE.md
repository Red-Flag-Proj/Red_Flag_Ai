# FraudGuard Architecture / FraudGuard 아키텍처

작성 기준일 / Date: 2026-05-09

This document summarizes the current FraudGuard architecture using `PLAN.md`, `PLAN2.md`, and the current codebase. It includes both Korean and English sections for stakeholder review and backend integration work.

이 문서는 `PLAN.md`, `PLAN2.md`, 현재 코드베이스를 기준으로 FraudGuard의 현재 아키텍처를 정리한다. 외부 이해관계자 검토와 백엔드 개발 협업을 위해 한국어와 영어를 함께 포함한다.

---

## 1. Korean Version

### 1.1 한 줄 요약

FraudGuard는 개인별 거래 이력, 거래 흐름, 룰 기반 탐지, 비지도 이상탐지, 지도학습 실험 점수를 바탕으로 이상거래 위험도를 평가하는 Python 기반 FDS 엔진이다.

보안 측면에서는 원본 테스트 데이터를 직접 DB/프론트로 보내지 않고, HMAC 기반 가명처리와 검증을 거친 masked 데이터만 백엔드 API 적재 후보로 사용하도록 계약을 정의한다.

### 1.2 현재 보안 수준 판단

현재 수준은 배포 전 로컬 검증 환경 기준으로 충분한 개발/QA 보안 구조다.

가능한 표현:

- 기업형 개발/QA 데이터 보안 흐름을 로컬에서 구현했다.
- raw 데이터와 masked 데이터를 분리했다.
- masked 데이터만 API 적재 후보가 되도록 로컬 검증 단계를 구현했다.
- HMAC 기반 deterministic pseudonymization을 사용한다.
- 감사 로그와 재식별 위험 리포트를 남긴다.
- 운영 전환 시 Secret Manager/KMS, RBAC, SIEM으로 확장 가능하다.

피해야 할 표현:

- 완전 익명화
- 재식별 불가능
- 실제 금융권 운영 보안 인증 수준
- KMS/SIEM/RBAC 실제 적용 완료
- 실제 개인정보 운영 환경에 즉시 투입 가능

권장 설명 문구:

```text
FraudGuard는 배포 전 로컬 검증 단계에서 운영 전환 가능한 개발용 보안 데이터 파이프라인을 구현했다.
현재 구현은 masked CSV 생성과 검증까지 완료했고, API 적재는 masked 데이터만 허용하는 계약으로 정의했다.
```

### 1.3 현재 구현된 흐름

```text
Synthetic Data Generator
  -> Raw synthetic CSV
  -> Masking Engine
  -> Masked CSV
  -> Masked CSV Validation
  -> Audit Log
  -> Re-identification Risk Report
```

### 1.4 백엔드 연동 계약 흐름

아래 흐름은 현재 코드에 모두 구현된 것이 아니라, 백엔드 개발자와 맞춰야 하는 API 기반 적재 계약이다.

```text
Validated Masked CSV
  -> JSON Command List
  -> API Caller Script
  -> Backend API
  -> DB
  -> Frontend
```

탐지/학습 파이프라인은 별도 흐름으로 관리한다.

```text
Fraud Engine / Model Pipeline
  -> Feature Engineering
  -> Rule Score
  -> Personal Pattern Score
  -> Sequence Pattern Score
  -> Anomaly Score
  -> Supervised ML Score experiment
  -> Final Risk Score
  -> Detection Reasons / Recommended Action
```

### 1.5 데이터 적재 방식

백엔드 개발자와 합의한 방식은 JSON 파일을 DB로 직접 쓰는 것이 아니다.

정확한 의미:

- JSON 파일은 “어떤 거래를 만들어야 하는지”를 담은 명령 목록이다.
- 스크립트가 JSON command list를 읽는다.
- 스크립트가 백엔드 API를 호출한다.
- 백엔드가 요청을 검증하고 DB에 저장한다.
- 결국 DB에 들어가는 경로는 백엔드 API다.

연동 계약 흐름:

```text
masked CSV
  -> validate_db_import_file.py
  -> JSON command list
  -> API caller script
  -> Backend API
  -> DB
```

JSON command 예시:

```json
{
  "commands": [
    {
      "type": "CREATE_TRANSACTION",
      "payload": {
        "transactionId": "TX_BA0AFA78B065",
        "customerRef": "CUST_15CDB0BFCF80",
        "customerName": "Customer_0001_15CD",
        "amount": 79685,
        "occurredAt": "2026-01-07T11:24:00",
        "merchantId": "MER_5242EA3E095F",
        "deviceId": "DEV_2572D270F65A",
        "paymentMethod": "E-PAY",
        "riskLabel": 0,
        "scenario": "NORMAL_BASELINE"
      }
    }
  ]
}
```

구현/연동 전제 조건:

- raw CSV에서 바로 JSON command list를 만들지 않는다.
- JSON command list는 masked CSV 검증 후에만 만든다.
- JSON command list 생성기와 API caller는 아직 현재 저장소에 구현되어 있지 않다.
- 백엔드는 `SIM-...`, 실제 이름, raw device ID, raw merchant ID처럼 보이는 값을 거부하도록 구현해야 한다.
- 프론트는 백엔드 DB에 저장된 masked 데이터와 risk result만 조회한다.

### 1.6 주요 코드 구성

| 영역 | 파일 | 역할 |
| --- | --- | --- |
| 데이터 생성 | `AI Engine/generate_personal_data.py` | 고객별 synthetic 거래 이력과 이상거래 시나리오 생성 |
| DB/API 테스트 데이터 샘플링 | `AI Engine/generate_db_test_data.py` | 200행 테스트 CSV 생성 |
| 마스킹 | `AI Engine/mask_test_data.py` | HMAC tokenization, 이름 가명화, 시간 offset, 위치 제거, 감사 로그 생성 |
| 생성+마스킹 통합 | `AI Engine/generate_db_test_data_masked.py` | raw CSV 생성 후 masked CSV 생성 |
| API 적재 전 후보 검증 | `AI Engine/validate_db_import_file.py` | masked schema, token prefix, location removal, time consistency 검증 |
| 재식별 위험 점검 | `AI Engine/assess_reidentification_risk.py` | 희소 quasi-identifier 조합과 위치 잔존 여부 평가 |
| 개인 feature | `AI Engine/personal_features.py` | 고객 history 기반 personal/sequence feature 생성 |
| 룰 | `AI Engine/rules.py` | 고액, 반복, 해외, 새벽, 신규기기, 국가 이동 탐지 |
| 탐지 엔진 | `AI Engine/fraudEngine.py` | rule 결과와 risk output 생성 |
| 점수화 | `AI Engine/risk_scoring.py` | Rule/ML/Personal/Sequence/Anomaly score 구조와 final score 계산 |
| 학습/평가 | `AI Engine/train_personal_model.py` | IsolationForest, supervised ML experiment, threshold 평가 |
| 실시간 백엔드 entrypoint | `AI Engine/detect_transaction.py` | 단건 거래 JSON을 받아 risk result 반환 |
| 실시간 inference | `AI Engine/realtime_inference.py` | backend request 검증, context 생성, rule/personal/sequence score 결합 |
| Smoke test | `AI Engine/test.py` | sample transaction 탐지 결과 출력 |

### 1.7 위험 점수 아키텍처

`PLAN.md`의 AI 파트는 FraudGuard의 핵심 탐지 아키텍처다. 보안 파이프라인은 "어떤 데이터를 안전하게 넣을 것인가"를 다루고, AI 파이프라인은 "그 데이터로 어떻게 이상거래를 판단할 것인가"를 다룬다.

AI 탐지 흐름:

```text
Transaction + Customer History
  -> personal_features.py
  -> rules.py
  -> IsolationForest anomaly experiment
  -> Supervised ML experiment
  -> risk_scoring.py
  -> finalRiskScore / riskLevel / detectionReasons / recommendedAction
```

계층별 책임:

- Rule Score: 명시적 FDS 룰 기반 위험 신호
- Personal Pattern Score: 고객 개인 기준선 대비 이탈 정도
- Sequence Pattern Score: 최근 거래 흐름, 반복, 급증, 분산 거래 패턴
- Anomaly Score: 정상 거래 분포에서 벗어난 정도
- ML Score: 라벨이 있는 synthetic 이상거래를 활용한 지도학습 실험 점수

PRD 기준 최종 점수 구조:

```text
Final Risk Score =
0.30 * Rule Score
+ 0.35 * ML Score
+ 0.20 * Personal Pattern Score
+ 0.10 * Sequence Pattern Score
+ 0.05 * Anomaly Score
```

현재 구현 상태:

- `risk_scoring.py`에 점수 breakdown 구조가 있다.
- `train_personal_model.py`는 personal/sequence/anomaly/ML 관련 오프라인 학습/평가 결과를 생성한다.
- `fraudEngine.py`의 실시간 smoke path는 현재 rule 중심 output을 반환한다.
- supervised ML은 `LogisticRegression(class_weight='balanced')` 기반 실험 결과로 관리된다.
- component threshold는 설명 가능성과 fallback 용도로 유지한다.
- 모델 저장/로드와 운영 API는 아직 구현되지 않았다.

구현 경계:

- 실시간 API serving에서 ML 모델을 로드해 판단하는 구조는 아직 없다.
- 백엔드가 프로세스로 호출할 수 있는 단건 inference script는 `AI Engine/detect_transaction.py`로 제공한다.
- JSON command generator, API caller, backend validation은 현재 구현이 아니라 백엔드 연동 계약이다.
- KMS/RBAC/SIEM은 현재 적용 완료가 아니라 운영 전환 시 확장 지점이다.

### 1.8 ARS 연동 판단

ARS 연동이 있다고 해서 FraudGuard DB나 프론트에 원본 개인정보를 많이 넣는 구조가 좋은 것은 아니다. 특히 ARS 음성 문구에서 `transaction.customer_name || transaction.customer_ref`를 그대로 읽으면, masked CSV 기반 환경에서는 `Customer_0001` 또는 `CUST_...` 같은 가명/토큰이 고객에게 들릴 수 있다.

권장 책임 분리:

```text
ARS / Customer System
  -> 실제 고객 식별
  -> 인증/상담 흐름 담당
  -> ARS 표시용 고객명 또는 호칭 제공

FraudGuard
  -> masked customerRef 또는 내부 token 기준 탐지
  -> 이상거래 risk result 제공
  -> 원본 이름/전화번호를 저장하거나 복호화하지 않음

Frontend
  -> 기본적으로 masked identifier와 risk result 표시
```

ARS 문구 생성 방식:

```text
ARS request
  -> customer_identity_service에서 phoneNumber 또는 internalCustomerId로 고객 표시명 조회
  -> FraudGuard detection result에서 amount/riskScore/transactionId 조회
  -> ARS prompt 조립
```

즉, ARS는 FraudGuard의 masked `customerName`을 고객명으로 읽지 않는다. ARS가 고객에게 읽어야 하는 이름은 별도의 고객/ARS 시스템에서 권한 있게 가져오고, FraudGuard는 위험 점수와 거래 정보만 제공한다.

권장 코드 방향:

```javascript
function buildArsPrompt(transaction, detection, customerProfile) {
  const displayName = customerProfile?.displayName || '고객';
  const amount = Number(transaction.amount).toLocaleString('ko-KR');
  const riskScore = detection.risk_score ?? detection.riskScore;

  return [
    'RedFlag 이상거래 탐지 ARS 서비스입니다.',
    `${displayName} 고객님 계정에서 이상거래가 감지되었습니다.`,
    `거래 금액 ${amount}원, 위험 점수 ${riskScore}점입니다.`,
    '본인이 요청한 거래가 맞으시면 1번, 아니면 2번을 눌러주세요.'
  ].join(' ');
}
```

상담원이 고객 식별이 필요한 경우:

- ARS 또는 고객시스템에서 처리한다.
- FraudGuard 화면에는 원본 개인정보를 복제하지 않는다.
- 꼭 필요한 경우에도 이름 일부 마스킹, 전화번호 뒤 4자리 같은 부분 표시로 제한한다.
- 원본 조회가 필요하면 별도 승인/감사 로그 대상이 되어야 한다.

### 1.9 운영 확장 가능성

현재는 배포와 클라우드 없이 로컬에서 검증한다. 운영 전환 시에는 다음으로 확장한다.

| 현재 로컬 구현 | 운영 전환 |
| --- | --- |
| 환경변수 salt | Secret Manager, Vault, KMS |
| 로컬 audit JSONL | SIEM, append-only storage |
| 로컬 검증 스크립트 | CI/CD gate, backend request validator |
| 문서상 역할 분리 | 실제 RBAC, service account |
| masked CSV 검증 | API request validation + DB constraint |
| JSON command list 계약 | JSON generator + authenticated API ingestion job |
| 수동 raw 파일 관리 | retention/lifecycle cleanup |

### 1.10 아키텍처 설명 문구

```text
FraudGuard는 로컬 검증 단계에서 synthetic 거래 데이터를 생성하고, 이를 HMAC 기반으로 가명처리한 뒤, 검증된 masked 데이터만 API 적재 후보로 허용하는 보안 계약을 정의했다.
현재 구현은 masked CSV 생성, 검증, 감사 로그, 재식별 위험 리포트까지 포함한다.
백엔드 연동 시에는 JSON command list를 API 호출 입력으로 사용하고, 프론트는 원본 개인정보가 아니라 masked 거래 정보와 risk result를 표시한다.
운영 전환 시 Secret Manager, RBAC, SIEM, API validation으로 확장 가능하다.
```

---

## 2. English Version

### 2.1 One-line Summary

FraudGuard is a Python-based fraud detection engine that evaluates transaction risk using customer history, transaction sequence patterns, rule-based detection, unsupervised anomaly detection, and supervised ML experiments.

From a security perspective, raw test data is not intended to be sent directly to the database or frontend. Only masked and validated data is eligible for the planned backend API ingestion flow.

### 2.2 Security Level Assessment

The current security level is sufficient for a non-deployed local validation environment.

Accurate claims:

- The project implements an enterprise-style development/QA data security flow locally.
- Raw and masked datasets are separated.
- Only masked data is eligible for backend ingestion, based on the local validation step.
- Deterministic HMAC-based pseudonymization is used.
- Audit logs and re-identification risk reports are generated.
- The design can be extended to Secret Manager/KMS, RBAC, and SIEM in production.

Claims to avoid:

- Complete anonymization
- Re-identification is impossible
- Production-grade financial security certification
- KMS/SIEM/RBAC fully implemented
- Ready for real personal-data production operation

Recommended architecture wording:

```text
FraudGuard implements a locally verifiable development data security pipeline that can be extended to production operations.
The current implementation covers masked CSV generation and validation; API ingestion is defined as a masked-data-only integration contract.
```

### 2.3 Currently Implemented Flow

```text
Synthetic Data Generator
  -> Raw synthetic CSV
  -> Masking Engine
  -> Masked CSV
  -> Masked CSV Validation
  -> Audit Log
  -> Re-identification Risk Report
```

### 2.4 Planned Backend Integration Contract

The following flow is not fully implemented in this repository yet. It is the agreed integration contract for backend development.

```text
Validated Masked CSV
  -> JSON Command List
  -> API Caller Script
  -> Backend API
  -> DB
  -> Frontend
```

The detection/training pipeline is managed separately.

```text
Fraud Engine / Model Pipeline
  -> Feature Engineering
  -> Rule Score
  -> Personal Pattern Score
  -> Sequence Pattern Score
  -> Anomaly Score
  -> Supervised ML Score experiment
  -> Final Risk Score
  -> Detection Reasons / Recommended Action
```

### 2.5 Backend Data Ingestion Method

The agreed backend integration method does not treat JSON as the database.

Correct interpretation:

- The JSON file is a command list that describes which transactions should be created.
- A script reads the JSON command list.
- The script calls the backend API.
- The backend validates the request and stores it in the database.
- The database is populated through the backend API path.

Integration contract flow:

```text
masked CSV
  -> validate_db_import_file.py
  -> JSON command list
  -> API caller script
  -> Backend API
  -> DB
```

Implementation and integration requirements:

- Do not build the JSON command list directly from raw CSV.
- Build command lists only after masked CSV validation.
- The JSON command list generator and API caller are not implemented in this repository yet.
- The backend must be implemented to reject raw-looking identifiers such as `SIM-...`, real names, raw device IDs, and raw merchant IDs.
- The frontend should read masked transactions and risk results from backend APIs.

### 2.6 Main Code Components

| Area | File | Responsibility |
| --- | --- | --- |
| Data generation | `AI Engine/generate_personal_data.py` | Generates synthetic customer transaction history and fraud scenarios |
| DB/API test sample | `AI Engine/generate_db_test_data.py` | Creates a 200-row test CSV |
| Masking | `AI Engine/mask_test_data.py` | HMAC tokenization, customer aliases, time offset, location removal, audit log |
| Generate + mask | `AI Engine/generate_db_test_data_masked.py` | Generates raw CSV and masked CSV in one flow |
| Pre-ingestion candidate validation | `AI Engine/validate_db_import_file.py` | Validates masked schema, token prefixes, removed location, and time consistency |
| Re-identification review | `AI Engine/assess_reidentification_risk.py` | Checks sparse quasi-identifier groups and location exposure |
| Personal features | `AI Engine/personal_features.py` | Builds customer-history and sequence features |
| Rules | `AI Engine/rules.py` | Detects high amount, repeated transactions, foreign transactions, dawn activity, new devices, and country velocity |
| Detection engine | `AI Engine/fraudEngine.py` | Produces rule-based risk output |
| Scoring | `AI Engine/risk_scoring.py` | Defines Rule/ML/Personal/Sequence/Anomaly score structure |
| Training/evaluation | `AI Engine/train_personal_model.py` | Runs IsolationForest, supervised ML experiment, and threshold evaluation |
| Realtime backend entrypoint | `AI Engine/detect_transaction.py` | Accepts one transaction JSON request and returns a risk result |
| Realtime inference | `AI Engine/realtime_inference.py` | Validates backend requests, builds context, and combines rule/personal/sequence scores |
| Smoke test | `AI Engine/test.py` | Prints detection results for sample transactions |

### 2.7 Risk Scoring Architecture

The AI section from `PLAN.md` is a core part of the architecture, not a separate document-only concern. The security pipeline answers "which data is safe to ingest"; the AI pipeline answers "how FraudGuard evaluates transaction risk."

AI detection flow:

```text
Transaction + Customer History
  -> personal_features.py
  -> rules.py
  -> IsolationForest anomaly experiment
  -> Supervised ML experiment
  -> risk_scoring.py
  -> finalRiskScore / riskLevel / detectionReasons / recommendedAction
```

Score component responsibilities:

- Rule Score: explicit FDS rule signals
- Personal Pattern Score: deviation from each customer's baseline
- Sequence Pattern Score: recent flow, repeat, burst, and distributed transaction patterns
- Anomaly Score: distance from normal transaction distribution
- ML Score: supervised experiment score using labeled synthetic fraud scenarios

PRD target score formula:

```text
Final Risk Score =
0.30 * Rule Score
+ 0.35 * ML Score
+ 0.20 * Personal Pattern Score
+ 0.10 * Sequence Pattern Score
+ 0.05 * Anomaly Score
```

Current implementation status:

- `risk_scoring.py` contains the score breakdown structure.
- `train_personal_model.py` generates offline training/evaluation results for personal, sequence, anomaly, and ML-related scoring.
- `fraudEngine.py` currently returns a rule-centered realtime smoke-test output.
- Supervised ML is tracked as a `LogisticRegression(class_weight='balanced')` experiment.
- Component thresholds remain useful for explanation and fallback decisions.
- Model persistence/loading and production API serving are not implemented yet.

Implementation boundary:

- Realtime API serving with a persisted ML model is not implemented yet.
- A process-callable single-transaction inference script is available at `AI Engine/detect_transaction.py`.
- The JSON command generator, API caller, and backend validation are an integration contract, not current source-code implementation.
- KMS, RBAC, and SIEM are production extension points, not completed local features.

### 2.8 ARS Integration Position

ARS integration does not mean FraudGuard should store or display raw personal data by default. If the ARS prompt reads `transaction.customer_name || transaction.customer_ref` directly, a masked-data environment may speak aliases or tokens such as `Customer_0001` or `CUST_...` to the customer.

Recommended responsibility split:

```text
ARS / Customer System
  -> Identifies the real customer
  -> Handles authentication and customer-service flow
  -> Provides the customer display name or greeting for ARS

FraudGuard
  -> Uses masked customerRef or internal token for detection
  -> Provides fraud risk results
  -> Does not store or decrypt raw names/phone numbers

Frontend
  -> Displays masked identifiers and risk results by default
```

Recommended ARS prompt flow:

```text
ARS request
  -> Customer identity service resolves phoneNumber or internalCustomerId to a display name
  -> FraudGuard detection result provides amount/riskScore/transactionId
  -> ARS prompt is assembled
```

In other words, ARS should not read FraudGuard's masked `customerName` as the real customer name. The customer-facing name should come from an authorized customer/ARS system, while FraudGuard provides risk data only.

Recommended code direction:

```javascript
function buildArsPrompt(transaction, detection, customerProfile) {
  const displayName = customerProfile?.displayName || '고객';
  const amount = Number(transaction.amount).toLocaleString('ko-KR');
  const riskScore = detection.risk_score ?? detection.riskScore;

  return [
    'RedFlag 이상거래 탐지 ARS 서비스입니다.',
    `${displayName} 고객님 계정에서 이상거래가 감지되었습니다.`,
    `거래 금액 ${amount}원, 위험 점수 ${riskScore}점입니다.`,
    '본인이 요청한 거래가 맞으시면 1번, 아니면 2번을 눌러주세요.'
  ].join(' ');
}
```

If a counselor needs real customer identity:

- Handle it in the ARS/customer system.
- Do not duplicate raw personal information into FraudGuard screens.
- If partial display is necessary, use partial masking such as a masked name or last four digits.
- Full raw access should require separate approval and audit logging.

### 2.9 Production Extension Path

The current project is local and not cloud-deployed. If it moves to production, extend the following parts:

| Current local implementation | Production extension |
| --- | --- |
| Environment-variable salt | Secret Manager, Vault, KMS |
| Local audit JSONL | SIEM, append-only storage |
| Local validation script | CI/CD gate, backend request validator |
| Documented role separation | Actual RBAC, service account |
| Masked CSV validation | API request validation + DB constraint |
| JSON command list contract | JSON generator + authenticated API ingestion job |
| Manual raw file handling | Retention/lifecycle cleanup |

### 2.10 Architecture Statement

```text
FraudGuard generates synthetic transaction data locally, pseudonymizes it with HMAC-based masking, and defines a masked-data-only security contract for backend API ingestion.
The current implementation includes masked CSV generation, validation, audit logging, and a re-identification risk report.
For backend integration, a JSON command list should be used as API automation input, and the frontend should display masked transaction information and risk results.
The architecture can be extended to Secret Manager, RBAC, SIEM, and backend API validation for production.
```

---

## 3. Current Recommendation

For this non-deployed local validation environment, the current security level is appropriate when framed within its implementation boundary:

- Say: "local development/QA security pipeline with production extension points."
- Do not say: "production-grade privacy/security implementation."
- Use masked data for frontend display.
- Use JSON only as a planned API command list format, not as a database replacement.
- Keep ARS/customer identity handling outside FraudGuard unless a controlled and audited backend path is added.
