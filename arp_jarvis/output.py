from __future__ import annotations

import json
from typing import Any, Iterable


def print_text(lines: Iterable[str]) -> None:
    for line in lines:
        print(line)


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=False))


def format_error(code: str, message: str, hint: str | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if hint:
        error["hint"] = hint
    return {"error": error, "extensions": None}

