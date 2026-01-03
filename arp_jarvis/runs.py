from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from .config import ResolvedConfig
from .http_client import request_json


DEFAULT_NODE_TYPE_ID = "jarvis.composite.planner.general"


def start_run(
    config: ResolvedConfig,
    *,
    goal: str,
    node_type_id: str | None,
    node_version: str | None,
    input_json: str | None,
    constraints: dict[str, Any] | None,
    bearer_token: str | None,
) -> dict[str, Any]:
    input_payload: dict[str, Any] = {}
    if input_json:
        payload = json.loads(input_json)
        if not isinstance(payload, dict):
            raise RuntimeError("input-json must be a JSON object")
        input_payload.update(payload)
    if goal and "goal" not in input_payload:
        input_payload["goal"] = goal

    resolved_goal = input_payload.get("goal")
    if not resolved_goal:
        raise RuntimeError("Goal is required (use --goal or include it in --input-json)")

    root_node_type = node_type_id or DEFAULT_NODE_TYPE_ID
    root_node_version = node_version or config.stack_version.value
    if not root_node_version:
        raise RuntimeError("Missing stack version; set STACK_VERSION or pass --node-version")

    body: dict[str, Any] = {
        "root_node_type_ref": {"node_type_id": root_node_type, "version": root_node_version},
        "input": input_payload,
    }
    if constraints:
        body["constraints"] = constraints

    headers = _auth_header(bearer_token)
    return request_json("POST", f"{config.gateway_url.value}/v1/runs", headers=headers, body=body)


def get_run(config: ResolvedConfig, run_id: str, *, bearer_token: str | None) -> dict[str, Any]:
    headers = _auth_header(bearer_token)
    return request_json("GET", f"{config.gateway_url.value}/v1/runs/{run_id}", headers=headers)


def cancel_run(config: ResolvedConfig, run_id: str, *, bearer_token: str | None) -> dict[str, Any]:
    headers = _auth_header(bearer_token)
    return request_json("POST", f"{config.gateway_url.value}/v1/runs/{run_id}:cancel", headers=headers)


def get_node_run(
    config: ResolvedConfig,
    node_run_id: str,
    *,
    bearer_token: str | None,
) -> dict[str, Any]:
    headers = _auth_header(bearer_token)
    return request_json(
        "GET",
        f"{config.coordinator_url.value}/v1/node-runs/{node_run_id}",
        headers=headers,
    )


def fetch_events(config: ResolvedConfig, run_id: str, *, bearer_token: str | None) -> list[dict[str, Any]]:
    raw = _fetch_event_stream(config, run_id, bearer_token=bearer_token)
    stripped = raw.lstrip()
    if stripped.startswith('"'):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Failed to decode quoted NDJSON events") from exc
    events: list[dict[str, Any]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Invalid NDJSON event payload") from exc
        if isinstance(event, dict):
            events.append(event)
    return events


def _fetch_event_stream(config: ResolvedConfig, run_id: str, *, bearer_token: str | None) -> str:
    url = f"{config.gateway_url.value}/v1/runs/{run_id}/events"
    req = Request(url)
    req.add_header("Accept", "application/x-ndjson")
    if bearer_token:
        req.add_header("Authorization", f"Bearer {bearer_token}")
    try:
        with urlopen(req, timeout=30) as resp:
            first = resp.read(1)
            if not first:
                return ""
            rest = resp.read()
            raw = first + rest
            return raw.decode("utf-8", errors="replace")
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}: {exc.reason}") from exc
    except URLError as exc:
        raise RuntimeError(f"Events request failed: {exc.reason}") from exc


def summarize_candidates(events: list[dict[str, Any]]) -> dict[str, Any]:
    summaries: list[dict[str, Any]] = []
    for event in events:
        if event.get("type") != "candidate_set_generated":
            continue
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        summaries.append(
            {
                "candidate_set_id": data.get("candidate_set_id"),
                "subtask_id": data.get("subtask_id"),
                "seq": event.get("seq"),
            }
        )
    return {"candidate_sets": summaries}


def _auth_header(bearer_token: str | None) -> dict[str, str]:
    if not bearer_token:
        return {}
    return {"Authorization": f"Bearer {bearer_token}"}
