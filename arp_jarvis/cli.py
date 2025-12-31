from __future__ import annotations

import argparse
import sys
from importlib import metadata


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="arp-jarvis",
        description="Meta CLI for the pinned JARVIS stack.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("versions", help="Print installed versions for the pinned stack")

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

    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.cmd == "versions":
        return _cmd_versions()

    raw_args: list[str] = list(args.args)
    if raw_args and raw_args[0] == "--":
        raw_args = raw_args[1:]

    if args.cmd == "run-gateway":
        return _run_run_gateway(raw_args)
    if args.cmd == "run-coordinator":
        return _run_run_coordinator(raw_args)
    if args.cmd == "atomic-executor":
        return _run_atomic_executor(raw_args)
    if args.cmd == "composite-executor":
        return _run_composite_executor(raw_args)
    if args.cmd == "node-registry":
        return _run_node_registry(raw_args)
    if args.cmd == "selection-service":
        return _run_selection_service(raw_args)
    if args.cmd == "pdp":
        return _run_pdp(raw_args)
    if args.cmd == "run-store":
        return _run_run_store(raw_args)
    if args.cmd == "event-stream":
        return _run_event_stream(raw_args)
    if args.cmd == "artifact-store":
        return _run_artifact_store(raw_args)

    raise RuntimeError(f"Unknown command: {args.cmd}")


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


def _run_run_gateway(argv: list[str]) -> int:
    from jarvis_run_gateway.__main__ import main as gateway_main

    return _call_cli(gateway_main, argv)


def _run_run_coordinator(argv: list[str]) -> int:
    from jarvis_run_coordinator.__main__ import main as coordinator_main

    return _call_cli(coordinator_main, argv)


def _run_atomic_executor(argv: list[str]) -> int:
    from jarvis_atomic_executor.__main__ import main as atomic_main

    return _call_cli(atomic_main, argv)


def _run_composite_executor(argv: list[str]) -> int:
    from jarvis_composite_executor.__main__ import main as composite_main

    return _call_cli(composite_main, argv)


def _run_node_registry(argv: list[str]) -> int:
    from jarvis_node_registry.__main__ import main as registry_main

    return _call_cli(registry_main, argv)


def _run_selection_service(argv: list[str]) -> int:
    from jarvis_selection_service.__main__ import main as selection_main

    return _call_cli(selection_main, argv)


def _run_pdp(argv: list[str]) -> int:
    from jarvis_pdp.__main__ import main as pdp_main

    return _call_cli(pdp_main, argv)


def _run_run_store(argv: list[str]) -> int:
    from jarvis_run_store.__main__ import main as run_store_main

    return _call_cli(run_store_main, argv)


def _run_event_stream(argv: list[str]) -> int:
    from jarvis_event_stream.__main__ import main as event_stream_main

    return _call_cli(event_stream_main, argv)


def _run_artifact_store(argv: list[str]) -> int:
    from jarvis_artifact_store.__main__ import main as artifact_store_main

    return _call_cli(artifact_store_main, argv)


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
