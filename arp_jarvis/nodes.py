from __future__ import annotations

import json
import subprocess
from typing import Any
from urllib.parse import urlencode

from .compose import compose_base_command
from .config import ResolvedConfig


_NODE_REGISTRY_PORT = 8084


def list_nodes(config: ResolvedConfig, *, kind: str | None = None, query: str | None = None) -> list[dict[str, Any]]:
    params: dict[str, str] = {}
    if kind:
        params["kind"] = kind
    if query:
        params["q"] = query
    payload = _exec_node_registry(config, path="/v1/node-types", params=params)
    if not isinstance(payload, list):
        raise RuntimeError("Unexpected node list response")
    return payload


def get_node(config: ResolvedConfig, node_type_id: str, *, version: str | None = None) -> dict[str, Any]:
    params = {"version": version} if version else {}
    payload = _exec_node_registry(config, path=f"/v1/node-types/{node_type_id}", params=params)
    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected node type response")
    return payload


def _exec_node_registry(config: ResolvedConfig, *, path: str, params: dict[str, str]) -> Any:
    base_url = f"http://localhost:{_NODE_REGISTRY_PORT}{path}"
    url = f"{base_url}?{urlencode(params)}" if params else base_url
    code = _PYTHON_FETCH
    cmd = compose_base_command(config) + [
        "exec",
        "-T",
        "node-registry",
        "python",
        "-c",
        code,
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        raise RuntimeError(stderr or "Node Registry request failed")
    stdout = proc.stdout.strip()
    if not stdout:
        raise RuntimeError("Empty response from Node Registry")
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Invalid JSON from Node Registry") from exc
    if isinstance(payload, dict) and "error" in payload:
        raise RuntimeError(payload["error"].get("message") or "Node Registry request failed")
    return payload


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
