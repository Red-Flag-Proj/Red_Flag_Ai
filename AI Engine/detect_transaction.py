from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from realtime_inference import detect_transaction


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run FraudGuard realtime inference for one backend transaction request."
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Path to a JSON request file. If omitted, JSON is read from stdin.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Print indented JSON for local debugging.",
    )
    return parser.parse_args()


def load_request(input_path: Path | None) -> dict:
    if input_path:
        with input_path.open("r", encoding="utf-8") as input_file:
            return json.load(input_file)
    return json.load(sys.stdin)


def main() -> int:
    args = parse_args()
    try:
        request = load_request(args.input)
        response = detect_transaction(request)
    except json.JSONDecodeError as exc:
        response = {
            "ok": False,
            "errors": [f"invalid JSON: {exc.msg}"],
        }
    except Exception as exc:
        response = {
            "ok": False,
            "errors": [str(exc)],
        }

    print(json.dumps(response, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if response.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
