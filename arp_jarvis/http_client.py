from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: Any | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = Request(url, method=method)
    req.add_header("Accept", "application/json")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    if headers:
        for key, value in headers.items():
            req.add_header(key, value)
    try:
        with urlopen(req, data=data, timeout=timeout_seconds) as resp:
            raw = resp.read()
    except HTTPError as exc:
        raw = exc.read()
        raise RuntimeError(_format_http_error(exc, raw)) from exc
    except URLError as exc:
        raise RuntimeError(f"Request failed: {exc.reason}") from exc
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON response from {url}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object from {url}")
    return payload


def post_form(
    url: str,
    payload: dict[str, str],
    *,
    headers: dict[str, str] | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    data = urlencode(payload).encode("utf-8")
    req = Request(url, data=data, method="POST")
    req.add_header("Accept", "application/json")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    if headers:
        for key, value in headers.items():
            req.add_header(key, value)
    try:
        with urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read()
    except HTTPError as exc:
        raw = exc.read()
        raise RuntimeError(_format_http_error(exc, raw)) from exc
    except URLError as exc:
        raise RuntimeError(f"Request failed: {exc.reason}") from exc
    try:
        payload_out = json.loads(raw.decode("utf-8")) if raw else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON response from {url}") from exc
    if not isinstance(payload_out, dict):
        raise RuntimeError(f"Expected JSON object from {url}")
    return payload_out


def _format_http_error(exc: HTTPError, raw: bytes) -> str:
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else {}
        if isinstance(payload, dict) and "error" in payload:
            return f"HTTP {exc.code}: {payload.get('error')}"
    except json.JSONDecodeError:
        pass
    return f"HTTP {exc.code}: {exc.reason}"
