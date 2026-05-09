# FraudGuard Data Security Contract

작성 기준일: 2026-05-09

이 문서는 PLAN2 Phase 1의 실행 산출물이다. DB 테스트 데이터의 민감도, 마스킹 후 유지할 계약, API 기반 DB 적재 허용 조건을 고정한다.

## 1. 데이터 등급

| Column | Sensitivity | Masked output policy | Import requirement |
| --- | --- | --- | --- |
| `transactionId` | Medium | HMAC token, `TX_` prefix | Required |
| `customerRef` | High | HMAC token, `CUST_` prefix | Required |
| `customerName` | High | Synthetic customer alias | Required |
| `amount` | Medium | Keep for synthetic data, round/bin for real data | Required |
| `occurredAt` | Medium | Day-offset timestamp | Required |
| `countryCode` | Low-Medium | Keep | Required |
| `city` | Medium | Keep for internal dev, generalize for shared datasets | Required |
| `latitude` | High | Empty by default, coarse only by explicit option | Required, can be empty |
| `longitude` | High | Empty by default, coarse only by explicit option | Required, can be empty |
| `merchantId` | High | HMAC token, `MER_` prefix | Required |
| `merchantCategory` | Low-Medium | Keep | Required |
| `deviceId` | High | HMAC token, `DEV_` prefix | Required |
| `paymentMethod` | Low-Medium | Keep | Required |
| `hour` | Low-Medium | Recalculate from masked `occurredAt` | Required |
| `dayOfWeek` | Low-Medium | Recalculate from masked `occurredAt` | Required |
| `isForeign` | Low-Medium | Keep | Required |
| `isNewDevice` | Low-Medium | Keep | Required |
| `isNewPaymentMethod` | Low-Medium | Keep | Required |
| `isDawn` | Low-Medium | Recalculate from masked `occurredAt` | Required |
| `label` | Low-Medium | Keep for internal dev only | Required |
| `scenario` | Low-Medium | Keep for internal dev only | Required |

## 2. Allowed Data Flows

Allowed:

1. Generate raw synthetic CSV locally.
2. Mask raw CSV immediately.
3. Validate the masked CSV before any backend ingestion.
4. Before real backend ingestion, implement a JSON command list generator from validated masked data.
5. Before real backend ingestion, implement an API caller script to send the JSON command list to the backend.
6. Before real backend ingestion, implement backend request validation and DB storage.
7. Keep audit logs that record file hashes, policy version, environment, and options.

Blocked:

1. Import raw CSV directly into DB test environments.
2. Store raw customer/payment data in the repository.
3. Write raw secret values to logs, CSV files, README files, or result JSON files.
4. Share deterministic pseudonymized data externally without a separate de-identification review.
5. Build a JSON command list from raw CSV.
6. Send raw-looking identifiers to the backend API.

## 3. Masked CSV Contract

A file is accepted as a backend ingestion candidate only if all conditions are true.

- It contains exactly the required schema from `mask_test_data.py`.
- `transactionId` values start with `TX_`.
- `customerRef` values start with `CUST_`.
- `merchantId` values start with `MER_`.
- `deviceId` values start with `DEV_`.
- `customerName` values start with `Customer_`.
- raw-looking prefixes such as `SIM-`, `CUST-`, `DEV-`, and `MER-` are not present in protected fields.
- `latitude` and `longitude` are empty unless coarse location was explicitly allowed.
- `occurredAt`, `hour`, `dayOfWeek`, and `isDawn` are internally consistent.

## 4. Phase 1 Completion

Phase 1 is complete when:

- this contract is present,
- `README.md` points backend/API ingestion users to the masked CSV validation command,
- the masking script enforces the CSV contract,
- future API ingestion scripts must enforce the JSON command contract rather than relying only on operator discipline.

## 5. JSON Command List Contract

The JSON command list is not a database. It is an API automation input that says which masked transactions should be created through the backend.

Required structure:

```json
{
  "commands": [
    {
      "type": "CREATE_TRANSACTION",
      "payload": {
        "transactionId": "TX_...",
        "customerRef": "CUST_...",
        "customerName": "Customer_...",
        "amount": 79685,
        "occurredAt": "2026-01-07T11:24:00",
        "merchantId": "MER_...",
        "deviceId": "DEV_...",
        "riskLabel": 0,
        "scenario": "NORMAL_BASELINE"
      }
    }
  ]
}
```

Rules:

- Commands must be generated from masked data only.
- API callers must validate the command list before sending requests. This must be implemented before real backend ingestion.
- The backend must reject raw-looking identifiers such as `SIM-...`, unmasked names, raw device IDs, and raw merchant IDs. This must be implemented before real backend ingestion.
- Frontend screens must read data through backend APIs and should display masked identifiers and risk results by default.
- ARS/customer-facing prompts must not use masked `customerName` or `customerRef` as the spoken customer name. ARS should resolve the real display name through an authorized customer identity service and combine it with FraudGuard's risk result.
- FraudGuard should not decrypt or store raw customer names only to support ARS. If customer identity is required, keep it in the ARS/customer system boundary and audit access there.
- Current repository scope: masked CSV generation, validation, audit log, and risk-report scripts. JSON command generation, API caller execution, backend request validation, and production secret/RBAC/SIEM controls are integration or production extension work.
