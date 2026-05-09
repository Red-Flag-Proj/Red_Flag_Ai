# FraudGuard Development Data Security Plan

작성 기준일: 2026-05-09

## 1. 목적

이 문서는 `AI Engine/data/db_test_transactions_200.csv` 계열의 DB 테스트 데이터를 기업용 개발 보안 단계로 올리기 위한 실행 계획이다.

목표는 단순한 “테스트용 마스킹”이 아니라, 개발/QA 검증 환경에서 사용할 수 있는 보안 통제 포함 데이터 파이프라인을 만드는 것이다.

- 원본 고객 데이터가 개발/테스트 환경에 직접 노출되지 않게 한다.
- 백엔드 API 적재, QA, 디버깅에는 masked 데이터만 사용한다.
- 식별자, 위치, 시간, 금액 정보의 재식별 위험을 낮춘다.
- 개발 편의성을 유지하면서 키 관리, 접근 통제, 감사 로그, 보관 정책을 붙인다.
- 실제 기업 환경으로 이전할 때 Secret Manager/KMS, RBAC, SIEM, 보관 정책으로 확장 가능하게 한다.

## 2. 현재 상태

현재 구현된 흐름은 다음과 같다.

- `AI Engine/generate_db_test_data.py`가 200행 DB 테스트 CSV를 생성한다.
- `AI Engine/mask_test_data.py`가 raw CSV를 masked CSV로 변환한다.
- `AI Engine/generate_db_test_data_masked.py`가 생성과 마스킹을 한 번에 수행한다.
- `README.md`는 백엔드/API 적재에 masked 데이터만 사용하도록 안내한다.

현재 코드로 구현된 범위는 masked CSV 생성, masked CSV 검증, 감사 로그 생성, 재식별 위험 리포트 생성까지다. JSON command list 생성기, API caller, 백엔드 API 검증은 백엔드 연동 단계에서 구현할 계약으로 남겨둔다.

현재 구현은 엄밀한 의미의 익명화 또는 완전 비식별화가 아니다. HMAC 기반의 결정적 가명처리(pseudonymization)다.

이 방식은 내부 개발과 QA에는 유용하다. 같은 원본 값이 같은 토큰으로 바뀌므로 재현 가능한 테스트가 가능하기 때문이다. 다만 키가 유출되거나 원본 후보군이 좁으면 재식별 위험이 남기 때문에 외부 공유용 데이터셋으로 바로 사용하면 안 된다.

현재 강점은 다음과 같다.

- `transactionId`, `customerRef`, `deviceId`, `merchantId`를 HMAC-SHA256 기반으로 결정적 토큰화한다.
- `customerName`을 고객 토큰 기반 가명으로 대체한다.
- `occurredAt`은 day offset 처리 후 `hour`, `dayOfWeek`, `isDawn`을 다시 계산한다.
- 기본 실행에서는 `latitude`, `longitude`를 제거한다.
- `--round-amount`, `--keep-coarse-location`, `--day-offset`, `--salt-env` 옵션이 있다.
- 마스킹 후 필수 컬럼과 일부 원본 prefix 잔존 여부를 검증한다.

기업용 개발 보안 기준으로는 다음 보완이 필요하다.

- salt/key가 환경변수 수준에 머문다.
- 환경별 키 분리와 rotation 절차가 없다.
- raw CSV 접근 권한과 masked CSV 접근 권한이 분리되어 있지 않다.
- 감사 로그, 실행 주체, 파일 해시, 정책 버전 기록이 없다.
- raw, masked, temp, log, backup 보관 기간이 정의되어 있지 않다.
- 재식별 위험 평가가 정량화되어 있지 않다.
- shared-dev 이상에서 raw CSV import를 차단하는 기술적 장치가 없다.

## 3. 보안 원칙

### 3.1 개발용과 공유용 분리

이 계획은 두 종류의 데이터를 구분한다.

- 개발용 데이터: 내부 팀이 API 적재, 기능 검증, QA, 디버깅에 쓰는 데이터
- 공유용 데이터: 외부 협업, 데모, 문서 첨부, 광범위 배포에 쓰는 데이터

개발용 데이터는 결정적 가명처리와 접근 통제로 충분할 수 있다. 공유용 데이터는 더 강한 비식별화, 추가 익명화, 또는 differential privacy 검토가 필요하다.

### 3.2 최소 공개 원칙

테스트에 필요한 값만 남긴다.

- 고객 이름은 가명으로 대체한다.
- 식별자는 HMAC 기반 토큰으로 대체한다.
- 좌표는 기본 제거한다.
- 시간은 offset 처리하고 원본 날짜를 숨긴다.
- 금액은 실제 데이터가 들어오면 반올림 또는 구간화를 적용한다.

### 3.3 재현 가능성과 추적 가능성

같은 환경, 같은 키, 같은 입력은 같은 마스킹 결과를 만들어야 한다. 그래야 QA, 재현, 디버깅이 가능하다.

동시에 원본에서 마스킹 값으로 역추적할 수 있는 매핑 파일은 남기지 않는다. 역추적이 필요한 경우에도 매핑 파일이 아니라 승인된 원본 접근 절차와 감사 로그로 처리한다.

### 3.4 환경 분리

최소한 다음 환경을 분리한다.

- `local-dev`
- `shared-dev`
- `qa-staging`
- `production-like-test`

각 환경은 서로 다른 key material, 접근 권한, 로그 보관 정책을 가져야 한다.

## 4. 현재 CSV 스키마와 민감도

대상 파일:

```text
AI Engine/data/db_test_transactions_200.csv
```

컬럼:

`transactionId`, `customerRef`, `customerName`, `amount`, `occurredAt`, `countryCode`, `city`, `latitude`, `longitude`, `merchantId`, `merchantCategory`, `deviceId`, `paymentMethod`, `hour`, `dayOfWeek`, `isForeign`, `isNewDevice`, `isNewPaymentMethod`, `isDawn`, `label`, `scenario`

민감도 기준:

- 높음: `customerRef`, `customerName`, `deviceId`, `merchantId`, `latitude`, `longitude`
- 중간: `transactionId`, `amount`, `occurredAt`, `city`
- 낮음~중간: `countryCode`, `merchantCategory`, `paymentMethod`, `hour`, `dayOfWeek`, `isForeign`, `isNewDevice`, `isNewPaymentMethod`, `isDawn`, `label`, `scenario`

`label`과 `scenario`는 직접 식별자는 아니지만, 외부 공유 시 특정 고객 행동이나 리스크 상태를 암시할 수 있으므로 공유용 데이터셋에서는 별도 검토가 필요하다.

## 5. 마스킹 정책

### 5.1 식별자 토큰화

다음 컬럼은 HMAC-SHA256 기반의 결정적 가명처리를 기본으로 한다.

- `transactionId`
- `customerRef`
- `deviceId`
- `merchantId`

정책:

- 단순 SHA-256이 아니라 HMAC을 사용한다.
- token body는 최소 12자리 이상 hex를 사용한다.
- 환경별 다른 key material을 사용한다.
- 같은 환경 안에서는 같은 원본이 같은 토큰으로 변환된다.
- token prefix는 테스트 가독성을 위해 허용하되, 원본 prefix가 그대로 남지 않도록 검증한다.

### 5.2 이름 처리

`customerName`은 직접 보존하지 않는다.

권장 방식:

- 고객 토큰 기반 가명을 생성한다.
- 화면 확인이나 QA에 필요한 경우에만 표시한다.
- 실제 고객 이름 형식과 비슷한 가짜 이름을 만들지 않는다.

예:

```text
Customer_0001_ABCD
```

### 5.3 위치 정보 처리

기본값은 제거다.

- `latitude`, `longitude`는 기본적으로 빈 값 처리한다.
- `city`는 개발 테스트에 필요한 경우 유지할 수 있다.
- 공유용 데이터에서는 `city`도 권역 또는 synthetic city로 대체한다.

예외적으로 위치 기반 feature 검증이 필요하면 coarse location만 허용한다.

- 소수점 1~2자리 반올림
- 도시 centroid 사용
- 고정된 테스트 좌표 사용

### 5.4 시간 정보 처리

`occurredAt`은 고정 day offset으로 이동한다.

이후 반드시 다시 계산한다.

- `hour`
- `dayOfWeek`
- `isDawn`

원본 날짜는 남기지 않는다.

### 5.5 금액 처리

현재 DB 테스트 데이터는 synthetic 데이터이므로 금액 유지가 가능하다. 실제 데이터가 들어오는 경우는 다음 중 하나를 적용한다.

- 1,000원 단위 반올림
- 금액 구간화
- 고위험 고객 또는 희귀 거래에 대한 추가 마스킹

## 6. 기업용 개발 보안 통제

이 섹션의 순서는 중요하다. API 기반 DB 적재보다 먼저 키 관리와 접근 통제를 확정하고, 그 다음 마스킹을 실행하며, 마지막으로 감사 로그와 재식별 평가를 남긴다.

### 6.1 키 관리

현재의 환경변수 방식은 로컬 개발에는 충분하지만 shared-dev 이상에서는 부족하다.

권장 단계:

- `local-dev`: 환경변수 허용
- `shared-dev`: Secret Manager 또는 Vault 사용
- `qa-staging`: Secret Manager 또는 KMS 사용
- `production-like-test`: KMS 또는 HSM 기반 key 사용

필수 정책:

- 환경별 key material 분리
- key rotation 주기 정의
- raw secret을 로그, 문서, CSV, 결과 파일에 남기지 않음
- key owner와 승인자 분리
- key access를 role-based access control로 제한
- emergency access는 break-glass 절차로만 허용하고 사후 리뷰를 남김

### 6.2 접근 제어

raw 데이터와 masked 데이터의 접근 권한을 분리한다.

- raw CSV는 최소 인원만 접근한다.
- masked CSV는 개발팀이 사용할 수 있다.
- raw data owner, masker, reviewer 역할을 분리한다.
- shared-dev 이상에는 승인 없이 raw CSV를 올릴 수 없게 한다.
- API 기반 DB 적재 파이프라인은 masked 데이터만 허용한다.
- raw 파일 경로와 masked 파일 경로를 명확히 분리한다.
- 예외 접근은 티켓 번호, 승인자, 사유, 만료일을 기록한다.

### 6.3 감사 로그

감사 로그는 단순 개발 로그가 아니라, 위변조가 어렵고 추적 가능한 기록이어야 한다.

기록 대상:

- 실행 시각
- 실행 주체
- 실행 환경
- 입력 파일 경로와 해시
- 출력 파일 경로와 해시
- 사용한 정책 버전
- 사용한 옵션
- 성공/실패 결과
- 실패 또는 거부 사유

보관 방식:

- append-only storage 또는 SIEM 사용
- 일반 개발 로그와 분리
- 조회 권한을 보안/운영 책임자로 제한
- 최소 월 1회 검토
- 로그 삭제는 승인된 운영 절차로만 허용

### 6.4 보관과 삭제

보관 정책은 raw, masked, temp, log, backup을 분리해서 정의한다.

권장 초안:

- raw test data: 7일 이내 보관
- masked data: 검증 완료 시점까지 보관, 최대 30일
- temp files: 당일 삭제
- audit logs: 1년 이상 보관
- backups: raw 포함 금지, 불가피하면 별도 암호화와 만료 정책 적용

삭제 조건:

- 검증 완료
- 배포 완료
- 접근 승인 만료
- 보안 사고 대응 종료

삭제 방식:

- managed storage에서는 lifecycle policy 또는 purge 정책을 사용한다.
- 로컬 raw/temp 파일은 작업 종료 후 제거한다.
- backup은 수동 삭제보다 자동 만료 정책을 우선한다.

### 6.5 재식별 위험 평가

마스킹 완료 후 단순 변환 성공만 확인하지 않는다. 최소한의 공격 시나리오를 기준으로 재식별 위험을 점검한다.

공격 시나리오:

- 동일 고객 토큰 추적
- 위치와 시간 조합을 통한 재식별
- 금액과 거래 패턴 결합 추정
- `label`, `scenario`를 통한 민감 상태 노출

허용 기준 초안:

- shared-dev 데이터셋에서 단일 quasi-identifier 조합으로 고객 1명만 남는 경우를 허용하지 않는다.
- 5건 미만의 희소 조합은 추가 마스킹 대상으로 본다.
- 고위험 조합이 발견되면 위치 제거, 금액 구간화, 시간 단위 완화 중 하나를 적용한다.
- 공유용 데이터셋은 별도 승인 없이 배포하지 않는다.

### 6.6 현재 프로젝트의 현실적 보안 범위

현재 프로젝트는 배포하지 않고, AWS 같은 클라우드 리소스도 사용하지 않는다. 따라서 이 단계의 목표는 운영 인프라를 완성하는 것이 아니라, 로컬 검증 환경에서 기업형 보안 흐름을 구현하고 검증하는 것이다.

현재 수준에서 충분하다고 볼 수 있는 범위:

- 개발/QA용 synthetic 데이터 보호
- raw 데이터와 masked 데이터 분리
- HMAC 기반 deterministic pseudonymization
- 위치 정보 기본 제거
- 마스킹 결과 검증
- raw-looking CSV 차단
- 감사 로그 파일 생성
- 재식별 위험 리포트 생성
- 프론트/백엔드 연동 시 masked 데이터만 전달한다는 원칙

현재 수준에서 충분하다고 말하면 안 되는 범위:

- 실제 운영 개인정보 처리 완료
- 완전 익명화 또는 재식별 불가능 보장
- 금융권 운영 보안 인증 수준
- 실제 KMS, SIEM, RBAC, 보관/삭제 자동화 적용 완료

따라서 외부 설명 시 표현은 다음과 같이 제한한다.

```text
FraudGuard는 배포 전 로컬 검증 단계에서 운영 전환 가능한 개발용 보안 데이터 파이프라인을 구현했다.
원본 데이터는 직접 프론트나 DB 적재 흐름으로 보내지 않고, masked 데이터와 검증된 API 입력만 사용한다.
```

### 6.7 JSON command list 기반 백엔드 적재 방식

백엔드 연동은 CSV를 DB에 직접 넣는 방식이 아니라, JSON command list를 API 호출 입력으로 사용하는 방식으로 정리한다.

역할 구분:

- JSON 파일: “어떤 거래를 만들어야 하는지”를 담은 명령 목록
- API caller script: JSON 명령을 읽고 백엔드 API를 호출
- Backend API: 요청을 검증하고 DB에 저장
- DB: 백엔드가 저장한 최종 거래 데이터를 보관

즉 JSON이 DB가 되는 것이 아니라, API 자동 호출을 위한 입력 명세다.

권장 흐름:

```text
raw synthetic CSV
  -> mask_test_data.py
  -> masked CSV
  -> JSON command list
  -> API caller script
  -> Backend API
  -> DB
  -> Frontend
```

보안 원칙:

- JSON command list에는 masked 데이터만 넣는다.
- raw CSV에서 바로 JSON command list를 만들지 않는다.
- API caller는 호출 전 `validate_db_import_file.py`와 동등한 검증을 수행한다.
- 백엔드는 받은 데이터가 masked contract를 만족하는지 한 번 더 검증한다.
- 프론트는 백엔드 DB에 저장된 masked 거래와 risk result만 조회한다.
- ARS가 고객 식별을 담당하더라도 FraudGuard 화면에는 원본 개인정보를 직접 노출하지 않는다.

ARS 연동 기준:

- ARS/고객시스템은 고객 식별을 담당한다.
- FraudGuard는 고객 원장 시스템이 아니라 이상거래 판단 시스템이다.
- ARS가 식별한 고객은 내부 참조값 또는 토큰으로 FraudGuard에 연결한다.
- FraudGuard DB와 프론트에는 `CUST_...`, `TX_...`, `DEV_...`, `MER_...` 같은 가명 식별자와 위험 판단 결과를 사용한다.
- 상담원이 실제 고객 식별이 필요한 경우는 별도 고객시스템 화면 또는 제한된 백엔드 경로에서 처리하고, FraudGuard에는 원본 개인정보를 복제하지 않는다.

### 6.8 운영 전환 시 확장 지점

배포와 클라우드 운영이 필요해질 경우 현재 구조는 다음처럼 확장한다.

| 현재 로컬 구현 | 운영 전환 시 대체/확장 |
| --- | --- |
| 환경변수 salt | Secret Manager, Vault, KMS |
| 로컬 audit JSONL | SIEM, append-only storage, WORM storage |
| 로컬 검증 명령 | CI/CD gate, backend request validator |
| 문서상 역할 분리 | 실제 RBAC, service account, admin role |
| 수동 raw 파일 관리 | lifecycle policy, scheduled cleanup, storage retention |
| masked CSV 검증 | API request schema validation + DB constraint |
| JSON command list | authenticated API ingestion job |

## 7. 구현 계획

### Phase 1. 데이터 분류와 계약 고정

목표: 어떤 값이 민감하고 어떤 값이 테스트에 필요한지 확정한다.

작업:

1. CSV 컬럼별 민감도 분류 문서화
2. 개발용/공유용 데이터셋 분리 기준 정의
3. 마스킹 후에도 유지할 feature 목록 확정
4. API 기반 DB 적재 계약 고정

완료 기준:

- raw data와 masked data의 사용 범위가 명확하다.
- 테스트에 필요한 컬럼과 제거할 컬럼이 확정되어 있다.
- DB 적재는 masked JSON command list와 백엔드 API만 통한다는 계약이 문서화되어 있다.

### Phase 2. 마스킹 엔진 강화

목표: 로컬 deterministic masking을 유지하면서 기업용 key 관리로 확장 가능하게 만든다.

작업:

1. `mask_test_data.py`를 정책/설정 기반으로 분리
2. HMAC key를 환경변수 주입에서 secret provider 주입으로 전환 가능하게 설계
3. token length, location policy, amount policy를 옵션화
4. 마스킹 검증 로직 강화
5. 원본 prefix 탐지와 누락 컬럼 탐지 강화

완료 기준:

- 같은 입력과 같은 key는 같은 출력으로 변환된다.
- 환경에 따라 key source를 바꿀 수 있다.
- 기본값은 위치 제거와 필수 secret 요구처럼 보수적으로 동작한다.
- 원본 prefix가 masked CSV에 남으면 실패한다.

### Phase 3. 운영 통제 추가

목표: 누가, 언제, 어떤 정책과 key source로, 어떤 데이터에 대해 마스킹했는지 남긴다.

작업:

1. 실행 감사 로그 추가
2. 입력/출력 파일 해시 기록
3. 환경별 실행 제한 추가
4. raw와 masked 저장 위치 분리
5. temp file 정리 절차 추가

완료 기준:

- 마스킹 실행 이력이 추적된다.
- raw와 masked 데이터가 섞이지 않는다.
- 승인되지 않은 환경에서 raw CSV를 shared-dev 이상으로 올리는 흐름이 차단된다.

### Phase 4. 재식별 위험 점검

목표: 현재 정책이 개발용으로 충분한지 정기적으로 확인한다.

작업:

1. 위치 정보 재식별 위험 검토
2. 거래 시간과 금액 결합 위험 검토
3. 동일 고객 연결성 검토
4. 희소 조합 카운트 산출
5. 공유용 데이터셋 기준 별도 정의

완료 기준:

- 개발용 허용 범위와 공유용 금지 범위가 구분된다.
- 희소 조합 또는 고위험 조합이 기준을 넘으면 마스킹 정책을 강화한다.

### Phase 5. API 기반 DB 적재 통제

목표: DB 적재 흐름이 raw CSV가 아니라 masked 데이터 기반 JSON command list와 백엔드 API만 받도록 고정한다.

작업:

1. API 기반 DB 적재 절차 문서화
2. masked CSV에서만 JSON command list를 만들도록 계약 정의
3. JSON command list 호출 전 masked contract 검증
4. 백엔드 API에서 raw-looking identifier 차단
5. 운영 문서에 보안 절차 명시

완료 기준:

- DB에는 백엔드 API를 통과한 masked 거래만 들어간다.
- raw CSV 또는 raw-looking JSON command는 실패한다.
- API 호출 전 검증 절차가 있다.
- 프론트는 masked 데이터와 risk result만 조회한다.

## 8. 우선순위

1. Phase 1: 데이터 분류와 API 기반 DB 적재 계약 고정
2. Phase 2: 마스킹 엔진 강화
3. Phase 3: 감사 로그와 접근 통제 추가
4. Phase 4: 재식별 위험 점검 자동화
5. Phase 5: API 기반 DB 적재 차단 로직 적용

## 9. 검증 기준

각 단계 종료 시 다음을 확인한다.

- raw 데이터가 shared-dev 이상으로 올라가지 않는다.
- masked 데이터만 JSON command list와 API 적재에 사용된다.
- 마스킹 결과에 원본 식별자 prefix가 남지 않는다.
- `occurredAt`과 파생 컬럼이 일치한다.
- 위치 정보 기본 제거가 지켜진다.
- 실행 이력이 남는다.
- 입력/출력 파일 해시가 기록된다.
- 환경별 key 분리가 가능하다.
- raw CSV, masked CSV, JSON command list가 분리 보관된다.
- salt 또는 secret raw value가 로그/문서/결과 파일에 노출되지 않는다.

## 10. 현실적인 판단

이 계획은 기업 운영 보안의 최종형은 아니다. 하지만 현재 FraudGuard 구현을 “테스트용 마스킹”에서 “보안 통제를 포함한 개발용 데이터 파이프라인”으로 올리는 데는 충분한 다음 단계다.

이 계획으로 달성할 수 있는 범위는 다음과 같다.

- 로컬 개발과 QA용 내부 데이터 보호
- 재현 가능한 deterministic pseudonymization
- 환경별 key 관리로의 확장 가능성
- raw/masked 데이터 접근 분리
- 감사 로그와 보관 정책 도입
- masked data only API ingestion 원칙 고정

공유/배포용 데이터가 필요해지면 이 계획 위에 더 강한 비식별화, k-anonymity 기준, differential privacy, 또는 완전 synthetic dataset 생성을 별도 단계로 추가해야 한다.
