# Repository Guidelines

## Project Structure & Module Organization

FraudGuard is a Python fraud-detection prototype. Root-level documents include `README.md`, `PRD.md`, and this guide. Application code lives in `AI Engine/`:

- `fraudEngine.py`: rule orchestration and final risk score output.
- `rules.py`: individual fraud rule checks.
- `personal_features.py`: customer-history feature engineering.
- `generate_personal_data.py`: synthetic transaction dataset generation.
- `train_personal_model.py`: Isolation Forest training and evaluation.
- `test.py` and `test_data.py`: smoke-test runner and sample transactions.
- `data/`: generated CSV input data.

Generated artifacts such as `__pycache__/`, `.pydeps/`, `.tmp/`, and model result JSON files should not be treated as source.

## Build, Test, and Development Commands

Run commands from the repository root unless noted.

```powershell
python -m pip install -r "AI Engine\requirements.txt"
```
Installs runtime dependencies: pandas and scikit-learn.

```powershell
python "AI Engine\test.py"
```
Runs the rule engine against sample transactions and prints risk decisions.

```powershell
python "AI Engine\test.py" --write-results
```
Writes smoke-test output to `AI Engine/results.json`.

```powershell
python "AI Engine\generate_personal_data.py"
python "AI Engine\train_personal_model.py"
```
Regenerates the personal transaction dataset, then trains and evaluates the hybrid rule/ML model.

## Coding Style & Naming Conventions

Use Python 3 with 4-space indentation. Prefer small, pure functions for rule checks and feature builders. Follow existing naming: `snake_case` for functions and variables, `UPPER_CASE` for constants such as `FEATURE_COLUMNS`, and descriptive `check_*` names for fraud rules. Keep transaction/context payload keys stable because scripts share dictionary contracts directly.

## Testing Guidelines

There is no formal test framework configured. Use `AI Engine/test.py` as the current smoke test before and after rule changes. When changing model behavior, also run `train_personal_model.py` and inspect the printed confusion matrix, precision, recall, and F1 values. Add new sample cases to `test_data.py` when introducing or modifying fraud rules.

## Commit & Pull Request Guidelines

This checkout does not include `.git`, so no local commit convention is available. Use concise imperative commit messages, for example `Add country velocity fraud rule` or `Tune hybrid risk threshold`. Pull requests should describe the changed fraud behavior, list commands run, include metric deltas for model changes, and mention any generated files intentionally updated.

## Security & Configuration Tips

Do not commit real customer or payment data. Keep datasets synthetic or anonymized, and document any threshold changes in `MODEL_EVALUATION.md` or the PR description so risk behavior remains auditable.
