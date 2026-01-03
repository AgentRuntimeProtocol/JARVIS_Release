from __future__ import annotations

import json
import subprocess
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .auth import DEFAULT_DEV_ISSUER, rewrite_base_url
from .compose import compose_base_command
from .config import ResolvedConfig, public_keycloak_base


_INTERNAL_SERVICES = {
    "atomic-executor": 8082,
    "composite-executor": 8083,
    "node-registry": 8084,
    "selection-service": 8085,
    "pdp": 8086,
    "run-store": 8091,
    "artifact-store": 8092,
    "event-stream": 8093,
}


def run_doctor(config: ResolvedConfig) -> dict[str, Any]:
    report: dict[str, Any] = {
        "compose": _compose_status(config),
        "endpoints": {
            "run_gateway": _check_http(f"{config.gateway_url.value}/v1/health"),
            "run_coordinator": _check_http(f"{config.coordinator_url.value}/v1/health"),
            "keycloak": _check_http(_discovery_url(config)),
        },
        "internal_services": {},
    }
    internal: dict[str, Any] = {}
    for service, port in _INTERNAL_SERVICES.items():
        internal[service] = _check_internal_service(config, service, port)
    report["internal_services"] = internal
    return report


def _compose_status(config: ResolvedConfig) -> dict[str, Any]:
    cmd = compose_base_command(config) + ["ps", "--all", "--format", "json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return {
            "ok": False,
            "error": proc.stderr.strip() or "docker compose ps failed",
        }
    raw = (proc.stdout or "").strip()
    if not raw:
        return {"ok": False, "error": "docker compose ps returned no data"}
    payload: Any | None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = None
        lines = raw.splitlines()
        for idx, line in enumerate(lines):
            if line.lstrip().startswith("["):
                json_text = "\n".join(lines[idx:])
                try:
                    payload = json.loads(json_text)
                except json.JSONDecodeError:
                    payload = None
                break
        if payload is None:
            items: list[Any] = []
            for line in lines:
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    return {"ok": False, "error": "Unable to parse docker compose ps output"}
            payload = items if items else None
        if payload is None:
            return {"ok": False, "error": "Unable to parse docker compose ps output"}
    if isinstance(payload, dict):
        if "Service" in payload:
            payload = [payload]
        else:
            return {"ok": False, "error": "Unexpected docker compose ps output"}
    if not isinstance(payload, list):
        return {"ok": False, "error": "Unexpected docker compose ps output"}
    services = {item.get("Service"): item for item in payload if isinstance(item, dict)}
    required = ["keycloak", "run-gateway", "run-coordinator"] + list(_INTERNAL_SERVICES.keys())
    missing = [svc for svc in required if svc not in services]
    statuses: dict[str, Any] = {}
    for name in required:
        item = services.get(name)
        if not item:
            statuses[name] = {"ok": False, "status": "missing"}
            continue
        state = item.get("State") or ""
        statuses[name] = {"ok": state.lower() == "running", "status": state}
    return {"ok": not missing, "services": statuses, "missing": missing}


def _check_http(url: str) -> dict[str, Any]:
    req = Request(url)
    req.add_header("Accept", "application/json")
    try:
        with urlopen(req, timeout=5) as resp:
            raw = resp.read().decode("utf-8")
    except HTTPError as exc:
        return {"ok": False, "error": f"HTTP {exc.code}: {exc.reason}"}
    except URLError as exc:
        return {"ok": False, "error": f"Request failed: {exc.reason}"}
    except Exception as exc:
        detail = f"{exc.__class__.__name__}: {exc}".rstrip(": ")
        return {"ok": False, "error": f"Request failed: {detail}"}
    return {"ok": True, "body": raw}


def _check_internal_service(config: ResolvedConfig, service: str, port: int) -> dict[str, Any]:
    url = f"http://localhost:{port}/v1/health"
    cmd = compose_base_command(config) + [
        "exec",
        "-T",
        service,
        "python",
        "-c",
        _PYTHON_FETCH,
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return {"ok": False, "error": proc.stderr.strip() or proc.stdout.strip() or "exec failed"}
    stdout = proc.stdout.strip()
    if not stdout:
        return {"ok": False, "error": "empty response"}
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": "invalid json response"}
    if isinstance(payload, dict) and "error" in payload:
        return {"ok": False, "error": payload["error"].get("message")}
    return {"ok": True, "body": payload}


def _discovery_url(config: ResolvedConfig) -> str:
    issuer = config.auth_issuer.value or DEFAULT_DEV_ISSUER
    if config.auth_discovery_url.value:
        discovery = config.auth_discovery_url.value
    else:
        discovery = issuer.rstrip("/") + "/.well-known/openid-configuration"
    public_base = public_keycloak_base(config)
    if public_base:
        return rewrite_base_url(discovery, public_base)
    return discovery


_PYTHON_FETCH = (
    "import json\n"
    "import sys\n"
    "import urllib.request\n"
    "url = sys.argv[1]\n"
    "req = urllib.request.Request(url, headers={'Accept': 'application/json'})\n"
    "try:\n"
    "    with urllib.request.urlopen(req, timeout=5) as resp:\n"
    "        data = resp.read().decode('utf-8')\n"
    "    print(data)\n"
    "except Exception as exc:\n"
    "    payload = {'error': {'code': 'request_failed', 'message': str(exc)}, 'extensions': None}\n"
    "    print(json.dumps(payload))\n"
    "    sys.exit(1)\n"
)
