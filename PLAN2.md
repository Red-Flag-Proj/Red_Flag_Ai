# FraudGuard Development Data Security Plan

작성 기준일: 2026-05-08

## 1. 목적

이 문서는 `AI Engine/data/db_test_transactions_200.csv` 계열의 테스트 데이터를 실무 기업 기준의 개발용 보안 단계까지 끌어올리기 위한 실행 계획이다.

목표는 다음과 같다.

- 원본 고객 데이터가 개발/테스트 환경에 직접 노출되지 않게 한다.
- 마스킹된 데이터만 DB import, QA, 시연, 디버깅에 사용한다.
- 식별자, 위치, 시간, 금액 정보의 재식별 위험을 낮춘다.
- 개발 편의성과 보안 통제를 동시에 유지한다.
- 이후 실제 기업 환경으로 옮길 때 키 관리, 접근제어, 감사 추적, 보관 정책을 그대로 확장할 수 있게 한다.

## 2. 현재 상태

현재 구현된 상태는 다음과 같다.

- `AI Engine/generate_db_test_data.py`로 200행 DB 테스트 CSV를 생성한다.
- `AI Engine/mask_test_data.py`로 마스킹 CSV를 생성한다.
- `AI Engine/generate_db_test_data_masked.py`로 생성과 마스킹을 한 번에 수행한다.
- `README.md`에는 masked CSV만 DB에 넣도록 안내가 들어 있다.

현재 구현은 엄밀한 의미의 익명화나 비식별화가 아니라, HMAC 기반의 결정적 가명처리(pseudonymization)다. 즉, 내부 개발에서는 유용하지만 공유용 데이터셋으로 바로 쓰기에는 부족하다.

현재 마스킹 방식의 강점은 다음과 같다.

- `transactionId`, `customerRef`, `deviceId`, `merchantId`를 HMAC-SHA256 기반으로 결정적 토큰화한다.
- `customerName`을 가명화한다.
- `occurredAt`은 offset 처리 후 `hour`, `dayOfWeek`, `isDawn`을 다시 계산한다.
- 기본 실행에서는 `latitude`, `longitude`를 제거한다.

하지만 기업용 개발 보안 기준에서는 다음 보완이 필요하다.

- salt가 환경변수 수준에 머문다.
- 키 회전과 환경 분리가 문서화되어 있지 않다.
- 마스킹 전 원본 데이터 접근 권한 분리가 없다.
- 감사 로그와 사용 이력이 없다.
- 데이터 보관/삭제 정책이 없다.
- 재식별 위험 평가 기준이 정량화되어 있지 않다.
- 공유용 데이터셋에 대한 더 강한 de-identification 기준이 없다.

## 3. 보안 원칙

### 3.1 개발용과 공유용을 분리

이 계획은 두 종류의 데이터를 구분한다.

- 개발용 데이터: 내부 팀이 DB import, 기능 검증, 디버깅에 쓰는 데이터
- 공유용 데이터: 외부 협업, 데모, 문서 첨부, 광범위 배포에 쓰는 데이터

개발용 데이터는 결정적 가명처리와 접근 통제로 충분할 수 있다. 공유용 데이터는 더 강한 비식별화 또는 추가 익명화가 필요하다.

### 3.2 최소 공개 원칙

테스트에 필요한 값만 남긴다.

- 고객 이름은 가명으로 대체
- 식별자는 토큰화
- 좌표는 기본 제거
- 시간은 offset만 남기고 원본 날짜는 숨김
- 금액은 필요 시 반올림 또는 구간화

### 3.3 재현 가능성과 추적 가능성

같은 원본 입력은 같은 마스킹 결과를 만들어야 한다. 그래야 QA, 재현, 디버깅이 가능하다.

동시에, 원본에서 마스킹으로 역추적할 수 있는 매핑 파일은 남기지 않는다.

### 3.4 환경 분리

최소한 다음 환경을 분리한다.

- local-dev
- shared-dev
- qa-staging
- production-like test

각 환경은 서로 다른 key material과 다른 접근 권한을 가져야 한다.

## 4. 현재 CSV 스키마

대상 파일:

```text
AI Engine/data/db_test_transactions_200.csv
```

컬럼:

`transactionId`, `customerRef`, `customerName`, `amount`, `occurredAt`, `countryCode`, `city`, `latitude`, `longitude`, `merchantId`, `merchantCategory`, `deviceId`, `paymentMethod`, `hour`, `dayOfWeek`, `isForeign`, `isNewDevice`, `isNewPaymentMethod`, `isDawn`, `label`, `scenario`

민감도 기준은 다음과 같다.

- 높음: `customerRef`, `customerName`, `deviceId`, `merchantId`, `latitude`, `longitude`
- 중간: `transactionId`, `amount`, `occurredAt`, `city`
- 낮음~중간: `countryCode`, `merchantCategory`, `paymentMethod`, `hour`, `dayOfWeek`, `isForeign`, `isNewDevice`, `isNewPaymentMethod`, `isDawn`, `label`, `scenario`

## 5. 마스킹 정책

### 5.1 식별자 토큰화

다음 컬럼은 `HMAC-SHA256` 결정적 가명처리가 기본이다.

- `transactionId`
- `customerRef`
- `deviceId`
- `merchantId`

정책:

- 단순 SHA-256이 아니라 HMAC을 쓴다.
- prefix는 유지하되 토큰 본문은 12자리 이상 hex를 사용한다.
- 환경별 다른 key를 사용한다.
- 같은 환경 안에서는 같은 원본이 같은 토큰으로 변환된다.

### 5.2 이름 처리

`customerName`은 직접 보존하지 않는다.

권장 방식:

- 고객 토큰 기반 가명 생성
- 팀 내부 시각화에 필요한 경우만 표시

예:

```text
Customer_0001
```

### 5.3 위치 정보 처리

기본값은 제거다.

- `latitude`, `longitude`는 기본적으로 빈 값 처리
- `city`는 필요 시 권역 수준의 테스트 값으로 대체 가능

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

개발용 synthetic 데이터는 유지 가능하다. 실제 데이터가 들어오는 경우는 다음 중 하나를 적용한다.

- 1,000원 단위 반올림
- 금액 구간화
- 고위험 고객에 대해서만 추가 마스킹

## 6. 기업용 개발 보안으로 올리기 위한 접근

이 섹션의 순서는 중요하다. DB import보다 먼저 키 관리와 접근 통제를 확정하고, 그 다음에 마스킹을 실행하며, 마지막에 감사 로그와 재식별 평가를 묶는다.

### 6.1 키 관리 강화

지금의 환경변수 방식은 로컬 개발에는 충분하지만 기업용 기준에서는 부족하다. 다음 단계로 올린다.

- local-dev: 환경변수 허용
- shared-dev 이상: Secret Manager 또는 KMS 사용
- production-like test: KMS 또는 HSM 기반 키 사용

추가 정책:

- key rotation 주기 정의
- 환경별 key 분리
- raw secret은 로그와 문서에 남기지 않음
- key owner와 approver를 분리한다
- key access는 role-based access control로 제한한다
- secret 조회 범위는 마스킹 작업 서비스 계정으로 최소화한다
- emergency access는 break-glass 절차로만 허용하고 반드시 사후 승인과 기록을 남긴다

### 6.2 접근 제어

원본과 마스킹 데이터에 대해 접근 권한을 분리한다.

- 원본 CSV는 최소 인원만 접근
- 마스킹 CSV는 개발팀이 사용
- 마스킹 스크립트는 원본 경로와 출력 경로를 분리
- 공유 저장소에는 원본 파일을 두지 않는다
- `separation of duties`를 적용해 생성자와 승인자를 분리한다
- raw data owner, masker, reviewer를 분리한다
- 승인 없이는 shared-dev 이상으로 raw CSV를 업로드하지 못하게 한다
- 예외 접근은 티켓 번호와 승인자를 기록해야 한다

### 6.3 감사 로그

감사 로그는 단순 기록이 아니라, 위변조가 어렵고 추적 가능한 형태여야 한다.

기록 대상:

- 실행 시각
- 실행 주체
- 환경명
- 입력 파일 해시
- 출력 파일 해시
- 사용한 정책 버전
- 사용한 옵션
- 성공/실패 결과
- 거부 사유
- 예외 접근 사유

보관 방식:

- append-only storage 또는 SIEM
- 일반 개발 로그와 분리
- 변경 불가능한 저장소 우선
- 조회 권한은 보안/운영 책임자만 부여
- 검토 주기는 최소 월 1회

위변조 방지:

- 로그 무결성 체크
- 접근 권한 분리
- 로그 삭제는 승인된 운영 절차로만 허용
- 해시 체인 또는 WORM storage 중 하나를 사용

### 6.4 보관과 삭제

보관 정책은 raw, masked, temp, log, backup으로 나눠야 한다.

권장 초안:

- raw test data: 7일 이내 보관
- masked data: 검증 완료 시점까지 보관, 최대 30일
- temp files: 당일 삭제
- audit logs: 1년 보관
- backups: 인프라 정책 따르되 raw 포함 금지

삭제 조건:

- 검증 완료
- 배포 완료
- 보안 사고 대응 종료

삭제 방식:

- raw와 temp는 secure delete 또는 관리형 storage purge를 사용
- masked CSV는 파일 단위 삭제 후 재생성 가능하게 유지
- backup은 수동 삭제가 아니라 보관 정책에 따른 자동 만료를 사용
- 로그는 보존 기간 종료 후에도 무결성 증적은 별도 보관 가능

### 6.5 재식별 위험 평가

마스킹 완료 후 단순 체크리스트가 아니라 최소한의 공격 시나리오와 허용 임계치를 둔다.

공격 시나리오:

- 동일 고객 토큰 추적
- 위치와 시간 조합으로의 재식별
- 금액과 거래 패턴 결합 추정
- label/scenario를 이용한 외부 노출 위험

허용 기준:

- shared-dev용 데이터셋에서는 단일 quasi-identifier 조합으로 고객이 1명만 남는 경우를 허용하지 않는다
- 5건 미만의 희소 조합은 기본적으로 추가 마스킹 대상이다
- 고위험 조합이 발견되면 기본값은 제거 또는 더 강한 마스킹으로 되돌린다
- 공유용 데이터셋은 별도 승인 없이는 배포하지 않는다
- 재식별 시도 샘플 검토를 통해 실패 기준에 걸리면 재평가를 요구한다

## 7. 구현 계획

### Phase 1. 데이터 분류와 계약 고정

목표: 어떤 값이 민감한지와 어떤 값이 테스트에 필요한지 확정한다.

작업:

1. CSV 컬럼별 민감도 분류 문서화
2. 개발용 / 공유용 데이터셋 분리 기준 정의
3. 마스킹 후에도 유지할 feature 목록 확정
4. DB import 계약 고정

완료 기준:

- 입력: raw CSV
- 출력: masked CSV
- 차단 조건: raw CSV를 shared-dev 이상으로 올리려는 시도
- 검증 스크립트: `py_compile`, 컬럼 누락 검사, prefix 잔존 검사
- 판정 조건: 민감도 분류표와 DB import 계약이 문서화되어 승인됨

### Phase 2. 마스킹 엔진 강화

목표: 로컬 개발에서 쓸 수 있는 deterministic masking을 유지하면서 기업용 키 관리로 확장 가능하게 만든다.

작업:

1. `mask_test_data.py`를 설정 기반으로 분리
2. HMAC key를 환경변수 주입에서 secret provider 주입으로 전환 가능하게 설계
3. 토큰 길이, prefix, location policy, amount policy를 옵션화
4. 마스킹 검증 로직 추가
5. 원본 prefix 탐지와 누락 컬럼 탐지 강화

완료 기준:

- 입력: raw CSV + environment secret
- 출력: masked CSV
- 차단 조건: secret 미설정, 필수 컬럼 누락, 원본 prefix 잔존
- 검증 스크립트: `py_compile`, CSV row/column equality, prefix scan

### Phase 3. 운영 통제 추가

목표: 파일 생성 자체보다 누가, 언제, 어떤 키 정책으로, 어떤 데이터에 대해 처리했는지를 남긴다.

작업:

1. 실행 로그 남기기
2. 입력/출력 파일 해시 기록
3. 환경별 실행 제한
4. 원본과 masked 저장 위치 분리
5. temp file 정리

완료 기준:

- 입력: 승인된 실행 환경
- 출력: audit log + masked CSV
- 차단 조건: 승인되지 않은 환경, raw 경로 직출력
- 검증 스크립트: 로그 항목 검사, 파일 해시 대조, 권한 체크
- 판정 조건: 실행 기록이 append-only 저장소에 남고 조회 권한이 제한됨

### Phase 4. 재식별 위험 점검

목표: 현재 정책이 개발용으로 충분한지 정기적으로 확인한다.

작업:

1. 위치 정보 재식별 위험 검토
2. 거래 시간과 금액 결합 위험 검토
3. 동일 고객 연결성 검토
4. 공유용 데이터셋 기준 별도 정의

완료 기준:

- 입력: masked CSV
- 출력: 위험 평가 리포트
- 차단 조건: 허용 임계치 초과
- 검증 스크립트: 고위험 조합 샘플링, unique combination 점검, 희소 조합 카운트
- 판정 조건: 희소 조합이 5건 미만이면 재마스킹 또는 승인 보류

### Phase 5. 실제 DB 연동

목표: DB import 파이프라인이 원본이 아니라 masked CSV만 받도록 고정한다.

작업:

1. DB import 문서화
2. masked CSV만 허용하는 체크 추가
3. raw CSV import 차단
4. 운영 문서에 보안 절차 명시

완료 기준:

- 입력: masked CSV
- 출력: DB 적재 완료
- 차단 조건: raw CSV, secret 노출, 승인되지 않은 스키마 변경
- 검증 스크립트: import 전 파일 검사, 테이블 적재 후 샘플 검증, raw import 거부 테스트
- 판정 조건: raw CSV import가 실패하고 masked CSV만 적재 성공

## 8. 우선순위

1. Phase 1
2. Phase 2
3. Phase 3
4. Phase 4
5. Phase 5

## 9. 검증 기준

각 단계 종료 시 다음을 확인한다.

- 원본 데이터가 shared-dev 이상으로 올라가지 않는다.
- 마스킹 결과에 식별자 prefix가 남지 않는다.
- `occurredAt`과 파생 컬럼이 일치한다.
- 위치 정보 기본 제거가 지켜진다.
- 실행 이력이 남는다.
- 환경별 key 분리가 가능하다.
- raw CSV와 masked CSV가 분리 보관된다.
- masked CSV only import가 지켜진다.
- raw CSV import 시도는 차단된다.
- salt 또는 secret 원문이 로그/문서에 노출되지 않는다.

## 10. 현실적인 판단

이 계획은 기업 운영 보안의 최종형은 아니다. 하지만 실무에서 의미 있는 개발용 보안 단계로는 올릴 수 있다.

즉,

- 로컬 개발과 QA용 내부 데이터 보호
- 재현 가능한 deterministic pseudonymization
- 키 관리와 접근 통제 확장 가능성
- 감사 로그와 보관 정책 도입

까지는 이 계획으로 가는 것이 맞다.

공유/배포용 데이터가 필요해지면, 이 계획 위에 더 강한 비식별화 또는 differential privacy 검토를 추가해야 한다.
