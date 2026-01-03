from __future__ import annotations

import subprocess
from typing import Sequence

from .config import ResolvedConfig


def compose_base_command(config: ResolvedConfig) -> list[str]:
    if not config.compose_file.exists():
        raise RuntimeError(f"Compose file not found: {config.compose_file}")
    if not config.env_local.exists():
        raise RuntimeError(
            f"Missing env file: {config.env_local} (copy compose/.env.example to compose/.env.local)"
        )
    if not config.profile_env.exists():
        raise RuntimeError(f"Missing profile env file: {config.profile_env}")
    return [
        "docker",
        "compose",
        "--env-file",
        str(config.env_local),
        "--env-file",
        str(config.profile_env),
        "-f",
        str(config.compose_file),
    ]


def run_compose(config: ResolvedConfig, args: Sequence[str], *, print_command: bool = False) -> int:
    cmd = compose_base_command(config) + list(args)
    if print_command:
        print(" ".join(cmd))
    proc = subprocess.run(cmd, check=False)
    return proc.returncode
