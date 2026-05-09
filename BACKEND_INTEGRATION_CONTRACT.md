# FraudGuard Backend Integration Contract

Date: 2026-05-09

This document is for the backend developer who will connect FraudGuard to the backend API, DB, frontend, and ARS flow.

## 1. Current Scope

Implemented in this repository:

- Realtime single-transaction inference script
- Request/response JSON contract
- Rule, personal pattern, and sequence pattern scoring for realtime calls
- Offline AI/ML training and evaluation pipeline
- Masked test-data generation and validation pipeline

Not implemented yet:

- HTTP server owned by the AI repository
- Backend API caller for JSON command lists
- Backend DB insert logic
- Persisted ML model serving
- Production KMS/RBAC/SIEM controls

## 2. Recommended Backend Flow

```text
Backend receives transaction
  -> Backend calls FraudGuard inference entrypoint
  -> FraudGuard returns riskScore/riskLevel/reasons/action
  -> Backend stores transaction + detection result
  -> Frontend reads detection result from backend API
  -> ARS combines customer display name from customer system with FraudGuard risk result
```

FraudGuard should not be the source of the real customer name for ARS.

## 3. Script Entrypoint

Use this script when the backend wants to call the AI engine as a process:

```powershell
python "AI Engine\detect_transaction.py" --input "AI Engine\examples\detect_request.json" --pretty
```

The script also accepts JSON from stdin:

```powershell
Get-Content "AI Engine\examples\detect_request.json" | python "AI Engine\detect_transaction.py"
```

Node backend example:

```javascript
const { spawn } = require('node:child_process');

function callFraudGuard(request) {
  return new Promise((resolve, reject) => {
    const child = spawn('python', ['AI Engine/detect_transaction.py']);
    let stdout = '';
    let stderr = '';

    child.stdout.on('data', chunk => {
      stdout += chunk.toString();
    });
    child.stderr.on('data', chunk => {
      stderr += chunk.toString();
    });
    child.on('close', code => {
      if (code !== 0) {
        return reject(new Error(stderr || stdout));
      }
      resolve(JSON.parse(stdout));
    });

    child.stdin.write(JSON.stringify(request));
    child.stdin.end();
  });
}
```

Exit codes:

- `0`: valid request and successful detection
- `1`: invalid JSON, invalid request, or runtime error

## 4. Request JSON Schema

Top-level shape:

```json
{
  "transaction": {},
  "customerHistory": [],
  "sequenceHistory": [],
  "context": {}
}
```

Required `transaction` fields:

```json
{
  "transactionId": "TX_DEMO_0001",
  "customerRef": "CUST_DEMO_0001",
  "amount": 1250000,
  "occurredAt": "2026-05-09T02:35:00",
  "countryCode": "US",
  "city": "New York",
  "merchantId": "MER_DEMO_0001",
  "merchantCategory": "electronics",
  "deviceId": "DEV_NEW_0001",
  "paymentMethod": "CARD"
}
```

Rules:

- `occurredAt` is preferred. `createdAt` is accepted for compatibility.
- `countryCode` is preferred. `ipCountry` is accepted for compatibility.
- `amount` must be numeric.
- `customerHistory` should contain prior confirmed-normal transactions for the same customer when available.
- `sequenceHistory` may contain prior transactions used for burst/sequence checks. If omitted, `customerHistory` is reused.
- `context` is optional. If supplied, it bypasses history-based context generation.

## 5. Response JSON Schema

Successful response:

```json
{
  "ok": true,
  "transactionId": "TX_DEMO_0001",
  "customerRef": "CUST_DEMO_0001",
  "riskScore": 85,
  "finalRiskScore": 42,
  "riskLevel": "critical",
  "scoreBreakdown": {
    "ruleScore": 85,
    "mlScore": 0,
    "personalPatternScore": 66,
    "sequencePatternScore": 0,
    "anomalyScore": 0
  },
  "detectionReasons": [],
  "recommendedAction": "hold transaction and review",
  "triggeredRules": [],
  "modelInfo": {
    "mode": "rule_personal_sequence",
    "mlScore": 0,
    "anomalyScore": 0,
    "modelServing": "not_enabled",
    "persistenceDecision": "Persisted ML model loading is reserved for a later joblib artifact."
  },
  "arsPolicy": {
    "customerNameSource": "customer_identity_service",
    "doNotSpeakMaskedCustomerName": true
  }
}
```

Error response:

```json
{
  "ok": false,
  "transactionId": "TX_DEMO_0001",
  "errors": [
    "transaction.amount must be numeric"
  ]
}
```

## 6. Model Persistence Decision

Current handoff decision:

- Realtime inference uses deterministic rule, personal pattern, and sequence pattern scoring.
- `mlScore` and `anomalyScore` are returned as `0` with `modelServing: "not_enabled"`.
- Offline ML evaluation remains in `AI Engine/train_personal_model.py`.

Production extension decision:

- Save the supervised model as a generated artifact, for example `AI Engine/model/supervised_model.joblib`.
- Save metadata separately, for example `AI Engine/model/model_metadata.json`.
- Do not commit model artifacts unless the team intentionally versions them.
- Load the model in `realtime_inference.py` only after the backend team agrees on model artifact deployment.

This keeps the backend contract stable now while leaving a clear slot for future ML serving.

## 7. ARS Integration Rule

Do not use these fields as the spoken customer name:

- `transaction.customerName`
- `transaction.customer_name`
- `transaction.customerRef`
- masked aliases such as `Customer_0001`
- token values such as `CUST_...`

Recommended ARS composition:

```text
displayName = customer identity service result
amount = backend transaction amount
riskScore = FraudGuard detection riskScore
```

Recommended JavaScript shape:

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

## 8. Backend Storage Recommendation

Store these detection fields with the transaction or in a separate detection table:

- `transactionId`
- `customerRef`
- `riskScore`
- `riskLevel`
- `scoreBreakdown`
- `detectionReasons`
- `recommendedAction`
- `triggeredRules`
- `modelInfo.mode`
- `createdAt` or detection timestamp

Frontend should display masked identifiers and risk results by default. Real customer identity should stay in the customer/ARS system boundary.

---

# FraudGuard 백엔드 연동 계약

## 1. 현재 범위

현재 저장소에 구현된 것:

- 실시간 단건 거래 탐지 script entrypoint
- 요청/응답 JSON 계약
- 실시간 호출용 rule, personal pattern, sequence pattern 점수화
- 오프라인 AI/ML 학습 및 평가 파이프라인
- masked 테스트 데이터 생성 및 검증 파이프라인

아직 구현되지 않은 것:

- AI 저장소가 직접 운영하는 HTTP 서버
- JSON command list 기반 백엔드 API caller
- 백엔드 DB insert 로직
- 저장된 ML 모델 serving
- 운영용 KMS/RBAC/SIEM 통제

## 2. 권장 백엔드 흐름

```text
백엔드가 거래 요청 수신
  -> FraudGuard inference entrypoint 호출
  -> FraudGuard가 riskScore/riskLevel/reasons/action 반환
  -> 백엔드가 거래와 탐지 결과 저장
  -> 프론트가 백엔드 API로 탐지 결과 조회
  -> ARS는 고객 시스템의 표시명과 FraudGuard risk result를 조합
```

FraudGuard는 ARS에서 읽을 실제 고객명의 출처가 아니다.

## 3. 실행 방법

파일 입력:

```powershell
python "AI Engine\detect_transaction.py" --input "AI Engine\examples\detect_request.json" --pretty
```

stdin 입력:

```powershell
Get-Content "AI Engine\examples\detect_request.json" | python "AI Engine\detect_transaction.py"
```

Node 백엔드 예시:

```javascript
const { spawn } = require('node:child_process');

function callFraudGuard(request) {
  return new Promise((resolve, reject) => {
    const child = spawn('python', ['AI Engine/detect_transaction.py']);
    let stdout = '';
    let stderr = '';

    child.stdout.on('data', chunk => {
      stdout += chunk.toString();
    });
    child.stderr.on('data', chunk => {
      stderr += chunk.toString();
    });
    child.on('close', code => {
      if (code !== 0) {
        return reject(new Error(stderr || stdout));
      }
      resolve(JSON.parse(stdout));
    });

    child.stdin.write(JSON.stringify(request));
    child.stdin.end();
  });
}
```

## 4. 요청 계약

필수 top-level:

- `transaction`

선택 top-level:

- `customerHistory`
- `sequenceHistory`
- `context`

필수 거래 필드:

- `transactionId`
- `customerRef`
- `amount`
- `occurredAt` 또는 `createdAt`
- `countryCode` 또는 `ipCountry`
- `deviceId`
- `paymentMethod`

권장 거래 필드:

- `city`
- `merchantId`
- `merchantCategory`
- `latitude`
- `longitude`

`customerHistory`는 가능하면 같은 고객의 과거 정상 거래만 넣는다. 이상거래로 확정된 거래를 고객 baseline에 바로 넣으면 개인 기준선이 오염될 수 있다.

## 5. 응답 계약

백엔드는 다음 값을 저장하거나 프론트/ARS 흐름에 전달하면 된다.

- `ok`
- `transactionId`
- `customerRef`
- `riskScore`
- `finalRiskScore`
- `riskLevel`
- `scoreBreakdown`
- `detectionReasons`
- `recommendedAction`
- `triggeredRules`
- `modelInfo`
- `arsPolicy`

## 6. 모델 저장/로드 결정

현재 인계 기준:

- 실시간 탐지는 rule + personal pattern + sequence pattern 기반으로 동작한다.
- `mlScore`, `anomalyScore`는 아직 실시간 serving에 붙이지 않는다.
- ML 성능 검증은 `AI Engine/train_personal_model.py`의 오프라인 평가 결과로 관리한다.

운영 확장 기준:

- supervised model은 추후 `AI Engine/model/supervised_model.joblib` 같은 artifact로 저장한다.
- feature 목록, threshold, 학습 데이터 버전은 `model_metadata.json`으로 분리한다.
- 모델 artifact는 기본적으로 Git에 커밋하지 않는다.
- 백엔드 배포 방식이 정해진 뒤 `realtime_inference.py`에서 모델 로드를 연결한다.

## 7. ARS 분리 원칙

ARS에서 고객에게 읽는 이름은 FraudGuard의 masked `customerName`이나 `customerRef`를 쓰지 않는다.

올바른 방식:

```text
고객 표시명 = 고객/ARS 시스템에서 조회
거래 금액 = 백엔드 거래 정보
위험 점수 = FraudGuard detection result
```

FraudGuard가 원본 이름을 복호화하거나 저장하는 구조로 바꾸지 않는다. 그 방식은 PLAN2의 masked-data-only 보안 방향과 충돌한다.
