from __future__ import annotations

import argparse
import sys
from importlib import metadata


_STACK_DISTS: tuple[str, ...] = (
    "arp-jarvis",
    "arp-standard-py",
    "arp-jarvis-daemon",
    "arp-jarvis-runtime",
    "arp-jarvis-tool-registry",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="arp-jarvis",
        description="Meta CLI for the pinned JARVIS OSS stack (daemon, runtime, tool registry, standard).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("versions", help="Print installed versions for the pinned stack")

    daemon = sub.add_parser("daemon", add_help=False, help="Run arp-jarvis-daemon (pass-through)")
    daemon.add_argument("args", nargs=argparse.REMAINDER)

    runtime = sub.add_parser("runtime", add_help=False, help="Run arp-jarvis-runtime (pass-through)")
    runtime.add_argument("args", nargs=argparse.REMAINDER)

    tool_registry = sub.add_parser("tool-registry", add_help=False, help="Run arp-jarvis-tool-registry (pass-through)")
    tool_registry.add_argument("args", nargs=argparse.REMAINDER)

    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.cmd == "versions":
        return _cmd_versions()

    raw_args: list[str] = list(args.args)
    if raw_args and raw_args[0] == "--":
        raw_args = raw_args[1:]

    if args.cmd == "daemon":
        return _run_daemon(raw_args)
    if args.cmd == "runtime":
        return _run_runtime(raw_args)
    if args.cmd == "tool-registry":
        return _run_tool_registry(raw_args)

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


def _run_daemon(argv: list[str]) -> int:
    from arp_jarvis_daemon.cli import main as daemon_main

    return _call_cli(daemon_main, argv)


def _run_runtime(argv: list[str]) -> int:
    from jarvis_runtime.cli import main as runtime_main

    return _call_cli(runtime_main, argv)


def _run_tool_registry(argv: list[str]) -> int:
    from tool_registry.main import main as tool_registry_main

    return _call_cli(tool_registry_main, argv)


def _call_cli(func, argv: list[str]) -> int:
    try:
        return int(func(argv))
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        print(str(code), file=sys.stderr)
        return 1

