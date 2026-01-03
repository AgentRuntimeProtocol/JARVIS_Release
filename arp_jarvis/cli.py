from __future__ import annotations

import argparse
import json
import sys
from importlib import metadata
from typing import Any

from .auth import (
    build_public_endpoints,
    clear_token,
    device_login,
    keyring_available,
    load_cached_token,
    store_token,
)
from .compose import run_compose
from .config import ResolvedConfig, config_as_dict, public_keycloak_base, resolve_config
from .doctor import run_doctor
from .nodes import get_node, list_nodes
from .output import format_error, print_json, print_text
from .runs import (
    cancel_run,
    DEFAULT_NODE_TYPE_ID,
    fetch_events,
    get_node_run,
    get_run,
    start_run,
    summarize_candidates,
)


_STACK_DISTS: tuple[str, ...] = (
    "arp-jarvis",
    "arp-jarvis-rungateway",
    "arp-jarvis-run-coordinator",
    "arp-jarvis-atomic-executor",
    "arp-jarvis-composite-executor",
    "arp-jarvis-node-registry",
    "arp-jarvis-selection-service",
    "arp-jarvis-pdp",
    "arp-jarvis-runstore",
    "arp-jarvis-eventstream",
    "arp-jarvis-artifactstore",
    "arp-jarvis-atomic-nodes",
)

DEFAULT_AUDIENCE = "arp-run-gateway"


def _normalize_global_flags(argv: list[str]) -> list[str]:
    if not argv:
        return argv
    front: list[str] = []
    rest: list[str] = []
    idx = 0
    while idx < len(argv):
        arg = argv[idx]
        if arg == "--":
            rest.extend(argv[idx:])
            break
        if arg == "--json":
            front.append(arg)
            idx += 1
            continue
        if arg in ("-o", "--output"):
            if idx + 1 < len(argv):
                front.extend([arg, argv[idx + 1]])
                idx += 2
            else:
                front.append(arg)
                idx += 1
            continue
        if arg.startswith("--output="):
            front.append(arg)
            idx += 1
            continue
        rest.append(arg)
        idx += 1
    return front + rest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="arp-jarvis",
        description="Meta CLI for the pinned JARVIS stack.",
    )
    parser.add_argument("-o", "--output", choices=["text", "json"], default="text")
    parser.add_argument("--json", action="store_true", help="Alias for -o json")
    parser.add_argument("--stack-root")
    parser.add_argument("--stack-profile")
    parser.add_argument("--gateway-url")
    parser.add_argument("--coordinator-url")
    parser.add_argument("--keycloak-url")

    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("versions", help="Print installed versions for the pinned stack")

    stack = sub.add_parser("stack", help="Manage the local Docker Compose stack")
    stack_sub = stack.add_subparsers(dest="stack_cmd", required=True)
    stack_up = stack_sub.add_parser("up", help="docker compose up")
    stack_up.add_argument(
        "-d",
        "--detach",
        action="store_true",
        help="Run in background (docker compose up -d)",
    )
    stack_up.add_argument("args", nargs=argparse.REMAINDER)
    stack_sub.add_parser("down").add_argument("args", nargs=argparse.REMAINDER)
    stack_sub.add_parser("pull").add_argument("args", nargs=argparse.REMAINDER)
    stack_ps = stack_sub.add_parser("ps")
    stack_ps.add_argument(
        "-a",
        "--all",
        dest="all_services",
        action="store_true",
        help="Show all containers (docker compose ps --all)",
    )
    stack_ps.add_argument("args", nargs=argparse.REMAINDER)
    stack_logs = stack_sub.add_parser("logs")
    stack_logs.add_argument(
        "-f",
        "--follow",
        action="store_true",
        help="Follow log output (docker compose logs -f)",
    )
    stack_logs.add_argument("args", nargs=argparse.REMAINDER)
    stack_exec = stack_sub.add_parser("exec")
    stack_exec.add_argument("args", nargs=argparse.REMAINDER)
    stack_sub.add_parser("config").add_argument("args", nargs=argparse.REMAINDER)
    stack.add_argument("--print-command", action="store_true")

    sub.add_parser("doctor", help="Run stack diagnostics")

    config_cmd = sub.add_parser("config", help="Show resolved configuration")
    config_sub = config_cmd.add_subparsers(dest="config_cmd", required=True)
    config_sub.add_parser("print")

    auth = sub.add_parser("auth", help="Authentication helpers")
    auth_sub = auth.add_subparsers(dest="auth_cmd", required=True)
    auth_sub.add_parser("login")
    token_cmd = auth_sub.add_parser("token")
    token_cmd.add_argument("--audience")
    token_cmd.add_argument("--header", action="store_true")
    token_cmd.add_argument("--no-newline", action="store_true")
    auth_sub.add_parser("status")
    auth_sub.add_parser("logout")

    nodes = sub.add_parser("nodes", help="Node Registry discovery")
    nodes_sub = nodes.add_subparsers(dest="nodes_cmd", required=True)
    nodes_list = nodes_sub.add_parser("list")
    nodes_list.add_argument("--kind")
    nodes_search = nodes_sub.add_parser("search")
    nodes_search.add_argument("query")
    nodes_search.add_argument("--kind")
    nodes_get = nodes_sub.add_parser("get")
    nodes_get.add_argument("node_type_id")
    nodes_get.add_argument("--version")

    runs = sub.add_parser("runs", help="Run Gateway interactions")
    runs_sub = runs.add_subparsers(dest="runs_cmd", required=True)
    runs_start = runs_sub.add_parser("start")
    runs_start.add_argument("--goal")
    runs_start.add_argument("--node-type")
    runs_start.add_argument("--node-version")
    runs_start.add_argument("--input-json")
    runs_start.add_argument("--constraints-file")
    runs_start.add_argument("--constraints-json")
    runs_get = runs_sub.add_parser("get")
    runs_get.add_argument("run_id")
    runs_cancel = runs_sub.add_parser("cancel")
    runs_cancel.add_argument("run_id")
    runs_events = runs_sub.add_parser("events")
    runs_events.add_argument("run_id")
    runs_inspect = runs_sub.add_parser("inspect")
    runs_inspect.add_argument("run_id")
    runs_inspect.add_argument("--include-node-runs", action="store_true")
    runs_inspect.add_argument("--include-events", action="store_true")
    runs_inspect.add_argument("--include-candidates", action="store_true")

    run_gateway = sub.add_parser("run-gateway", add_help=False, help="Run arp-jarvis-rungateway (pass-through)")
    run_gateway.add_argument("args", nargs=argparse.REMAINDER)

    run_coordinator = sub.add_parser(
        "run-coordinator", add_help=False, help="Run arp-jarvis-run-coordinator (pass-through)"
    )
    run_coordinator.add_argument("args", nargs=argparse.REMAINDER)

    atomic_executor = sub.add_parser(
        "atomic-executor", add_help=False, help="Run arp-jarvis-atomic-executor (pass-through)"
    )
    atomic_executor.add_argument("args", nargs=argparse.REMAINDER)

    composite_executor = sub.add_parser(
        "composite-executor", add_help=False, help="Run arp-jarvis-composite-executor (pass-through)"
    )
    composite_executor.add_argument("args", nargs=argparse.REMAINDER)

    node_registry = sub.add_parser(
        "node-registry", add_help=False, help="Run arp-jarvis-node-registry (pass-through)"
    )
    node_registry.add_argument("args", nargs=argparse.REMAINDER)

    selection_service = sub.add_parser(
        "selection-service", add_help=False, help="Run arp-jarvis-selection-service (pass-through)"
    )
    selection_service.add_argument("args", nargs=argparse.REMAINDER)

    pdp = sub.add_parser("pdp", add_help=False, help="Run arp-jarvis-pdp (pass-through)")
    pdp.add_argument("args", nargs=argparse.REMAINDER)

    run_store = sub.add_parser("run-store", add_help=False, help="Run arp-jarvis-runstore (pass-through)")
    run_store.add_argument("args", nargs=argparse.REMAINDER)

    event_stream = sub.add_parser(
        "event-stream", add_help=False, help="Run arp-jarvis-eventstream (pass-through)"
    )
    event_stream.add_argument("args", nargs=argparse.REMAINDER)

    artifact_store = sub.add_parser(
        "artifact-store", add_help=False, help="Run arp-jarvis-artifactstore (pass-through)"
    )
    artifact_store.add_argument("args", nargs=argparse.REMAINDER)

    argv_list = list(argv) if argv is not None else sys.argv[1:]
    args = parser.parse_args(_normalize_global_flags(argv_list))

    output = "json" if args.json else args.output

    if args.cmd == "versions":
        return _cmd_versions()

    if args.cmd in {"run-gateway", "run-coordinator", "atomic-executor", "composite-executor", "node-registry",
                    "selection-service", "pdp", "run-store", "event-stream", "artifact-store"}:
        raw_args = _strip_leading_double_dash(args.args)
        return _dispatch_passthrough(args.cmd, raw_args)

    try:
        config = resolve_config(
            stack_root_flag=args.stack_root,
            stack_profile_flag=args.stack_profile,
            gateway_url_flag=args.gateway_url,
            coordinator_url_flag=args.coordinator_url,
            keycloak_url_flag=args.keycloak_url,
        )
    except RuntimeError as exc:
        return _emit_error(output, "config_error", str(exc))

    if args.cmd == "stack":
        return _cmd_stack(
            config,
            args.stack_cmd,
            args.args,
            detach=getattr(args, "detach", False),
            follow=getattr(args, "follow", False),
            show_all=getattr(args, "all_services", False),
            print_command=args.print_command,
        )

    if args.cmd == "doctor":
        return _cmd_doctor(config, output)

    if args.cmd == "config":
        return _cmd_config_print(config, output)

    if args.cmd == "auth":
        return _cmd_auth(config, args, output)

    if args.cmd == "nodes":
        return _cmd_nodes(config, args, output)

    if args.cmd == "runs":
        return _cmd_runs(config, args, output)

    return _emit_error(output, "unknown_command", f"Unknown command: {args.cmd}")


def _cmd_versions() -> int:
    versions: dict[str, str] = {}
    for dist in _STACK_DISTS:
        try:
            versions[dist] = metadata.version(dist)
        except metadata.PackageNotFoundError:
            versions[dist] = "not installed"

    width = max(len(k) for k in versions) if versions else 0
    for dist in _STACK_DISTS:
        print(f"{dist:<{width}}  {versions[dist]}")
    return 0


def _dispatch_passthrough(cmd: str, argv: list[str]) -> int:
    if cmd == "run-gateway":
        from jarvis_run_gateway.__main__ import main as gateway_main

        return _call_cli(gateway_main, argv)
    if cmd == "run-coordinator":
        from jarvis_run_coordinator.__main__ import main as coordinator_main

        return _call_cli(coordinator_main, argv)
    if cmd == "atomic-executor":
        from jarvis_atomic_executor.__main__ import main as atomic_main

        return _call_cli(atomic_main, argv)
    if cmd == "composite-executor":
        from jarvis_composite_executor.__main__ import main as composite_main

        return _call_cli(composite_main, argv)
    if cmd == "node-registry":
        from jarvis_node_registry.__main__ import main as registry_main

        return _call_cli(registry_main, argv)
    if cmd == "selection-service":
        from jarvis_selection_service.__main__ import main as selection_main

        return _call_cli(selection_main, argv)
    if cmd == "pdp":
        from jarvis_pdp.__main__ import main as pdp_main

        return _call_cli(pdp_main, argv)
    if cmd == "run-store":
        from jarvis_run_store.__main__ import main as run_store_main

        return _call_cli(run_store_main, argv)
    if cmd == "event-stream":
        from jarvis_event_stream.__main__ import main as event_stream_main

        return _call_cli(event_stream_main, argv)
    if cmd == "artifact-store":
        from jarvis_artifact_store.__main__ import main as artifact_store_main

        return _call_cli(artifact_store_main, argv)
    raise RuntimeError(f"Unknown pass-through command: {cmd}")


def _cmd_stack(
    config: ResolvedConfig,
    stack_cmd: str,
    args: list[str],
    *,
    detach: bool,
    follow: bool,
    show_all: bool,
    print_command: bool,
) -> int:
    raw_args = _strip_leading_double_dash(args)
    compose_args = [stack_cmd]
    if stack_cmd == "up" and detach and "-d" not in raw_args and "--detach" not in raw_args:
        compose_args.append("-d")
    if stack_cmd == "logs" and follow and "-f" not in raw_args and "--follow" not in raw_args:
        compose_args.append("-f")
    if stack_cmd == "ps" and show_all and "-a" not in raw_args and "--all" not in raw_args:
        compose_args.append("--all")
    compose_args.extend(raw_args)
    return run_compose(config, compose_args, print_command=print_command)


def _cmd_doctor(config: ResolvedConfig, output: str) -> int:
    report = run_doctor(config)
    if output == "json":
        print_json(report)
    else:
        lines = ["Doctor report:"]
        compose = report.get("compose", {})
        lines.append(f"  Compose: {'ok' if compose.get('ok') else 'failed'}")
        endpoints = report.get("endpoints", {})
        for name, result in endpoints.items():
            status = "ok" if result.get("ok") else "failed"
            lines.append(f"  {name}: {status}")
        internal = report.get("internal_services", {})
        for name, result in internal.items():
            status = "ok" if result.get("ok") else "failed"
            lines.append(f"  {name}: {status}")
        print_text(lines)
    all_ok = report.get("compose", {}).get("ok", False)
    for group in ("endpoints", "internal_services"):
        for item in report.get(group, {}).values():
            if isinstance(item, dict) and not item.get("ok"):
                all_ok = False
    return 0 if all_ok else 1


def _cmd_config_print(config: ResolvedConfig, output: str) -> int:
    payload = config_as_dict(config)
    if output == "json":
        print_json(payload)
    else:
        lines = [
            f"stack_root: {payload['stack_root']}",
            f"compose_file: {payload['compose_file']}",
            f"env_local: {payload['env_local']}",
            f"profile_env: {payload['profile_env']}",
            f"stack_profile: {payload['stack_profile']['value']} ({payload['stack_profile']['source']})",
            f"stack_version: {payload['stack_version']['value']} ({payload['stack_version']['source']})",
            f"gateway_url: {payload['gateway_url']['value']} ({payload['gateway_url']['source']})",
            f"coordinator_url: {payload['coordinator_url']['value']} ({payload['coordinator_url']['source']})",
            f"keycloak_url: {payload['keycloak_url']['value']} ({payload['keycloak_url']['source']})",
            f"auth_profile: {payload['auth_profile']['value']} ({payload['auth_profile']['source']})",
            f"auth_mode: {payload['auth_mode']['value']} ({payload['auth_mode']['source']})",
            f"auth_issuer: {payload['auth_issuer']['value']} ({payload['auth_issuer']['source']})",
            f"auth_discovery_url: {payload['auth_discovery_url']['value']} ({payload['auth_discovery_url']['source']})",
            f"auth_token_endpoint: {payload['auth_token_endpoint']['value']} ({payload['auth_token_endpoint']['source']})",
            f"dev_cli_client_id: {payload['dev_cli_client_id']['value']} ({payload['dev_cli_client_id']['source']})",
        ]
        print_text(lines)
    return 0


def _cmd_auth(config: ResolvedConfig, args: argparse.Namespace, output: str) -> int:
    public_base = public_keycloak_base(config)
    endpoints = build_public_endpoints(
        issuer=config.auth_issuer.value,
        token_endpoint=config.auth_token_endpoint.value,
        client_id=config.dev_cli_client_id.value or "arp-dev-cli",
        client_secret=None,
        public_base_url=public_base,
    )
    if args.auth_cmd == "login":
        audience = DEFAULT_AUDIENCE
        try:
            token = device_login(endpoints, audience=audience)
        except RuntimeError as exc:
            return _emit_error(output, "auth_login_failed", str(exc))
        cached = store_token(endpoints, token, audience=audience)
        if output == "json":
            payload = _token_payload(token, source="device" if not cached else "device+cache")
            payload["cached"] = cached
            print_json(payload)
        else:
            lines = ["Login complete."]
            if cached:
                lines.append("Token cached in OS credential store.")
            else:
                lines.append("No secure credential store available; token not cached.")
            print_text(lines)
        return 0

    if args.auth_cmd == "status":
        cached = load_cached_token(endpoints, audience=DEFAULT_AUDIENCE)
        available = keyring_available()
        if output == "json":
            print_json(
                {
                    "keyring_available": available,
                    "logged_in": cached is not None,
                    "expires_at": cached.expires_at() if cached else None,
                    "issuer": endpoints.issuer,
                    "client_id": endpoints.client_id,
                    "default_audience": DEFAULT_AUDIENCE,
                }
            )
        else:
            lines = [
                f"keyring_available: {available}",
                f"logged_in: {cached is not None}",
                f"issuer: {endpoints.issuer}",
                f"client_id: {endpoints.client_id}",
                f"default_audience: {DEFAULT_AUDIENCE}",
            ]
            print_text(lines)
        return 0 if cached else 1

    if args.auth_cmd == "logout":
        removed = clear_token(endpoints, audience=DEFAULT_AUDIENCE)
        if output == "json":
            print_json({"logged_out": removed})
        else:
            print_text(["Logged out." if removed else "No cached token to remove."])
        return 0

    if args.auth_cmd == "token":
        audience = args.audience or DEFAULT_AUDIENCE
        token, source = _resolve_token(endpoints, audience=audience)
        if output == "json":
            payload = _token_payload(token, source=source)
            print_json(payload)
        else:
            value = token.access_token
            if args.header:
                value = f"Authorization: Bearer {value}"
            if args.no_newline:
                sys.stdout.write(value)
            else:
                print(value)
        return 0

    return _emit_error(output, "unknown_command", f"Unknown auth command: {args.auth_cmd}")


def _cmd_nodes(config: ResolvedConfig, args: argparse.Namespace, output: str) -> int:
    try:
        if args.nodes_cmd == "list":
            nodes = list_nodes(config, kind=args.kind)
            return _print_nodes(nodes, output)
        if args.nodes_cmd == "search":
            nodes = list_nodes(config, kind=args.kind, query=args.query)
            return _print_nodes(nodes, output)
        if args.nodes_cmd == "get":
            node = get_node(config, args.node_type_id, version=args.version)
            if output == "json":
                print_json(node)
            else:
                lines = [
                    f"node_type_id: {node.get('node_type_id')}",
                    f"version: {node.get('version')}",
                    f"kind: {node.get('kind')}",
                ]
                if node.get("description"):
                    lines.append(f"description: {node.get('description')}")
                print_text(lines)
            return 0
    except RuntimeError as exc:
        return _emit_error(output, "nodes_error", str(exc))
    return _emit_error(output, "unknown_command", f"Unknown nodes command: {args.nodes_cmd}")


def _cmd_runs(config: ResolvedConfig, args: argparse.Namespace, output: str) -> int:
    bearer, auth_source = _maybe_token(config, output, audience=DEFAULT_AUDIENCE)
    if auth_source == "error":
        return 1
    try:
        if args.runs_cmd == "start":
            constraints = _parse_constraints(args.constraints_file, args.constraints_json)
            node_type_id = args.node_type or DEFAULT_NODE_TYPE_ID
            node_version = args.node_version or config.stack_version.value
            run = start_run(
                config,
                goal=args.goal or "",
                node_type_id=node_type_id,
                node_version=node_version,
                input_json=args.input_json,
                constraints=constraints,
                bearer_token=bearer,
            )
            if output == "json":
                payload = {
                    "run": run,
                    "request": {
                        "root_node_type_ref": {
                            "node_type_id": node_type_id,
                            "version": node_version,
                        },
                        "constraints_attached": constraints is not None,
                    },
                    "auth": {"source": auth_source},
                    "next_steps": [
                        f"arp-jarvis runs events {run.get('run_id')}",
                        f"arp-jarvis runs inspect {run.get('run_id')}",
                    ],
                }
                print_json(payload)
            else:
                run_id = run.get("run_id")
                lines = [
                    f"run_id: {run_id}",
                    f"root_node_type_id: {node_type_id}",
                    f"root_node_version: {node_version}",
                    f"constraints: {'attached' if constraints else 'none'}",
                    f"auth_source: {auth_source}",
                    "next:",
                    f"  arp-jarvis runs events {run_id}",
                    f"  arp-jarvis runs inspect {run_id}",
                ]
                print_text(lines)
            return 0
        if args.runs_cmd == "get":
            run = get_run(config, args.run_id, bearer_token=bearer)
            if output == "json":
                print_json(run)
            else:
                lines = [
                    f"run_id: {run.get('run_id')}",
                    f"state: {run.get('state')}",
                    f"root_node_run_id: {run.get('root_node_run_id')}",
                ]
                print_text(lines)
            return 0
        if args.runs_cmd == "cancel":
            run = cancel_run(config, args.run_id, bearer_token=bearer)
            if output == "json":
                print_json(run)
            else:
                lines = [
                    f"run_id: {run.get('run_id')}",
                    f"state: {run.get('state')}",
                ]
                print_text(lines)
            return 0
        if args.runs_cmd == "events":
            events = fetch_events(config, args.run_id, bearer_token=bearer)
            if output == "json":
                for event in events:
                    print(json.dumps(event))
            else:
                for event in events:
                    print(json.dumps(event))
            return 0
        if args.runs_cmd == "inspect":
            run = get_run(config, args.run_id, bearer_token=bearer)
            payload: dict[str, Any] = {"run": run}
            if args.include_node_runs or args.include_candidates:
                root_node_id = run.get("root_node_run_id")
                if root_node_id:
                    node_run = get_node_run(
                        config,
                        root_node_id,
                        bearer_token=bearer,
                    )
                    payload["root_node_run"] = node_run
            if args.include_events or args.include_candidates:
                events = fetch_events(config, args.run_id, bearer_token=bearer)
                if args.include_events:
                    payload["events"] = events
                if args.include_candidates:
                    payload["candidates"] = summarize_candidates(events)
            if output == "json":
                print_json(payload)
            else:
                lines = [
                    f"run_id: {run.get('run_id')}",
                    f"state: {run.get('state')}",
                    f"root_node_run_id: {run.get('root_node_run_id')}",
                ]
                root = payload.get("root_node_run")
                if isinstance(root, dict):
                    lines.append(f"root_node_state: {root.get('state')}")
                candidates = payload.get("candidates")
                if isinstance(candidates, dict):
                    lines.append(f"candidate_sets: {len(candidates.get('candidate_sets') or [])}")
                print_text(lines)
            return 0
    except (RuntimeError, json.JSONDecodeError) as exc:
        return _emit_error(output, "runs_error", str(exc))
    return _emit_error(output, "unknown_command", f"Unknown runs command: {args.runs_cmd}")


def _parse_constraints(path: str | None, raw_json: str | None) -> dict[str, Any] | None:
    if path and raw_json:
        raise RuntimeError("Use only one of --constraints-file or --constraints-json")
    if path:
        content = open(path, "r", encoding="utf-8").read()
        payload = json.loads(content)
        if not isinstance(payload, dict):
            raise RuntimeError("Constraints file must contain a JSON object")
        return payload
    if raw_json:
        payload = json.loads(raw_json)
        if not isinstance(payload, dict):
            raise RuntimeError("constraints-json must be a JSON object")
        return payload
    return None


def _print_nodes(nodes: list[dict[str, Any]], output: str) -> int:
    if output == "json":
        print_json(nodes)
        return 0
    lines = []
    for node in nodes:
        node_id = node.get("node_type_id")
        version = node.get("version")
        kind = node.get("kind")
        desc = node.get("description") or ""
        lines.append(f"{node_id}  {version}  {kind}  {desc}".strip())
    print_text(lines)
    return 0


def _resolve_token(endpoints, *, audience: str | None) -> tuple[Any, str]:
    cached = load_cached_token(endpoints, audience=audience)
    if cached:
        return cached, "cache"
    token = device_login(endpoints, audience=audience)
    cached = store_token(endpoints, token, audience=audience)
    return token, "device+cache" if cached else "device"


def _maybe_token(
    config: ResolvedConfig, output: str, *, audience: str | None = None
) -> tuple[str | None, str]:
    if (config.auth_mode.value or "").lower() == "disabled" or (
        (config.auth_profile.value or "").lower() == "dev-insecure"
    ):
        return None, "disabled"
    public_base = public_keycloak_base(config)
    endpoints = build_public_endpoints(
        issuer=config.auth_issuer.value,
        token_endpoint=config.auth_token_endpoint.value,
        client_id=config.dev_cli_client_id.value or "arp-dev-cli",
        client_secret=None,
        public_base_url=public_base,
    )
    cached = load_cached_token(endpoints, audience=audience)
    if cached:
        return cached.access_token, "cache"
    try:
        token = device_login(endpoints, audience=audience)
    except RuntimeError as exc:
        _emit_error(output, "auth_required", str(exc))
        return None, "error"
    stored = store_token(endpoints, token, audience=audience)
    source = "device+cache" if stored else "device"
    return token.access_token, source


def _token_payload(token, *, source: str) -> dict[str, Any]:
    return {
        "access_token": token.access_token,
        "token_type": token.token_type,
        "expires_in": token.expires_in,
        "issued_at": token.issued_at,
        "source": source,
    }


def _strip_leading_double_dash(argv: list[str]) -> list[str]:
    raw_args: list[str] = list(argv)
    if raw_args and raw_args[0] == "--":
        raw_args = raw_args[1:]
    return raw_args


def _emit_error(output: str, code: str, message: str, hint: str | None = None) -> int:
    payload = format_error(code, message, hint)
    if output == "json":
        print_json(payload)
    else:
        lines = [f"Error: {message}"]
        if hint:
            lines.append(f"Hint: {hint}")
        print_text(lines)
    return 1


def _call_cli(func, argv: list[str]) -> int:
    try:
        return int(func(argv))
    except SystemExit as exc:
        if (code := exc.code) is None:
            return 0
        if isinstance(code, int):
            return code
        print(str(code), file=sys.stderr)
        return 1
