# FraudGuard

FraudGuard is a Python-based fraud detection engine built around rule checks, customer history features, anomaly scoring, and supervised ML scoring.

## Tech Stack

- Python
- Pandas
- Scikit-learn

## Main Scripts

- `AI Engine/test.py` runs the smoke test against sample transactions.
- `AI Engine/train_personal_model.py` trains and evaluates the hybrid model.
- `AI Engine/generate_personal_data.py` generates synthetic transaction history.
- `AI Engine/generate_db_test_data.py` generates the 200-row backend/API integration candidate CSV.
- `AI Engine/mask_test_data.py` masks the backend/API test CSV for safe ingestion candidate use.
- `AI Engine/generate_db_test_data_masked.py` generates the raw CSV and masks it in one step.
- `AI Engine/validate_db_import_file.py` validates that a CSV is masked before it is used as a backend/API ingestion candidate.
- `AI Engine/assess_reidentification_risk.py` writes a basic re-identification risk report for a masked CSV.
- `AI Engine/detect_transaction.py` runs realtime single-transaction inference for backend integration.

## Running Tests

```powershell
python "AI Engine\test.py"
python "AI Engine\test.py" --write-results
python "AI Engine\train_personal_model.py"
```

## Backend Test Data Workflow

Use masked data for any backend or DB test. The intended backend integration is:

```text
masked CSV -> JSON command list -> API caller script -> backend API -> DB
```

The JSON file is only a command list for API automation. It is not the DB itself.

```powershell
$env:FRAUDGUARD_MASKING_SALT = "<set-outside-repo>"
python "AI Engine\generate_personal_data.py"
python "AI Engine\generate_db_test_data_masked.py"
python "AI Engine\validate_db_import_file.py"
python "AI Engine\assess_reidentification_risk.py"
```

This produces:

- `AI Engine/data/personal_customers_10_transactions.csv`
- `AI Engine/data/db_test_transactions_200.csv`
- `AI Engine/data/db_test_transactions_200_masked.csv`
- `AI Engine/data/masking_audit.jsonl`
- `AI Engine/data/reidentification_risk_report.json`

These files are generated locally and ignored by Git. Regenerate them when testing or reviewing the integration instead of committing them.

Only validated masked data should be converted into API requests. Run `AI Engine\validate_db_import_file.py` before generating a JSON command list or calling the backend API. The JSON command list generator and API caller are integration steps to implement with the backend. The validation rejects raw-looking identifiers, unexpected schema changes, non-empty location columns by default, and inconsistent time-derived fields.

For non-local environments, pass an explicit environment name:

```powershell
python "AI Engine\generate_db_test_data_masked.py" --environment shared-dev --allow-env-secret-outside-local
```

The override is for local validation only. In a real shared environment, move the masking key to Secret Manager, Vault, KMS, or an equivalent managed secret provider.

## Backend Inference Entrypoint

Use this when the backend needs a risk result for one transaction:

```powershell
python "AI Engine\detect_transaction.py" --input "AI Engine\examples\detect_request.json" --pretty
```

The request/response schema, model persistence decision, and ARS customer-name boundary are documented in `BACKEND_INTEGRATION_CONTRACT.md`.

## Notes

- Keep customer and payment data fully synthetic or pseudonymized.
- Do not commit masking salts or raw customer data.
- Use `BACKEND_INTEGRATION_CONTRACT.md`, `DATA_SECURITY_CONTRACT.md`, `PLAN.md`, and `PLAN2.md` for the current implementation and integration plans.
