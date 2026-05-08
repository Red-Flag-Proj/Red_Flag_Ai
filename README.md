# FraudGuard

FraudGuard is a Python-based fraud detection prototype built around rule checks, customer history features, anomaly scoring, and supervised ML scoring.

## Tech Stack

- Python
- Pandas
- Scikit-learn

## Main Scripts

- `AI Engine/test.py` runs the smoke test against sample transactions.
- `AI Engine/train_personal_model.py` trains and evaluates the hybrid model.
- `AI Engine/generate_personal_data.py` generates synthetic transaction history.
- `AI Engine/generate_db_test_data.py` generates the 200-row DB integration CSV.
- `AI Engine/mask_test_data.py` masks the DB test CSV for safe import.
- `AI Engine/generate_db_test_data_masked.py` generates the raw CSV and masks it in one step.

## Running Tests

```powershell
python "AI Engine\test.py"
python "AI Engine\test.py" --write-results
python "AI Engine\train_personal_model.py"
```

## DB Test Data Workflow

Use the masked CSV for any DB import test.

```powershell
$env:FRAUDGUARD_MASKING_SALT = "<set-outside-repo>"
python "AI Engine\generate_db_test_data_masked.py"
```

This produces:

- `AI Engine/data/db_test_transactions_200.csv`
- `AI Engine/data/db_test_transactions_200_masked.csv`

Only `AI Engine/data/db_test_transactions_200_masked.csv` should be imported into a shared or test database.

## Notes

- Keep customer and payment data synthetic or anonymized.
- Do not commit masking salts or raw customer data.
- Use `PLAN.md` and `PLAN2.md` for the current implementation and security plans.
