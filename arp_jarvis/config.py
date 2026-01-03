from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any

from .envfile import load_env_file


@dataclass(frozen=True)
class ResolvedValue:
    value: str | None
    source: str


@dataclass(frozen=True)
class ResolvedConfig:
    stack_root: Path
    compose_file: Path
    env_local: Path
    profile_env: Path
    stack_profile: ResolvedValue
    stack_version: ResolvedValue
    gateway_url: ResolvedValue
    coordinator_url: ResolvedValue
    keycloak_url: ResolvedValue
    auth_profile: ResolvedValue
    auth_mode: ResolvedValue
    auth_issuer: ResolvedValue
    auth_discovery_url: ResolvedValue
    auth_token_endpoint: ResolvedValue
    dev_cli_client_id: ResolvedValue


def find_stack_root(start: Path) -> Path | None:
    candidates = [start] + list(start.parents)
    for base in candidates:
        if (base / "stack.lock.json").exists() and (base / "compose" / "docker-compose.yml").exists():
            return base
    return None


def _resolve_value(
    *,
    key: str,
    flags: dict[str, str | None],
    environ: dict[str, str],
    env_local: dict[str, str],
    env_profile: dict[str, str],
    default: str | None,
) -> ResolvedValue:
    if (flag_value := flags.get(key)) is not None:
        return ResolvedValue(flag_value, f"flag:{key}")
    if (env_value := environ.get(key)) is not None:
        return ResolvedValue(env_value, f"env:{key}")
    if (local_value := env_local.get(key)) is not None:
        return ResolvedValue(local_value, f"file:.env.local:{key}")
    if (profile_value := env_profile.get(key)) is not None:
        return ResolvedValue(profile_value, f"file:profile:{key}")
    return ResolvedValue(default, "default")


def _resolve_stack_version(stack_root: Path, env_local: dict[str, str]) -> ResolvedValue:
    if (env_value := env_local.get("STACK_VERSION")) is not None:
        return ResolvedValue(env_value, "file:.env.local:STACK_VERSION")
    lock_path = stack_root / "stack.lock.json"
    if lock_path.exists():
        try:
            payload = json.loads(lock_path.read_text(encoding="utf-8"))
            value = str(payload.get("stack_version") or "").strip() or None
            if value:
                return ResolvedValue(value, "file:stack.lock.json:stack_version")
        except json.JSONDecodeError:
            pass
    return ResolvedValue(None, "default")


def _normalize_base_url(url: str | None) -> str | None:
    if not url:
        return None
    trimmed = url.rstrip("/")
    if trimmed.endswith("/v1"):
        trimmed = trimmed[: -len("/v1")]
    return trimmed


def _host_url(host: str, port: str) -> str:
    return f"http://{host}:{port}"


def resolve_config(
    *,
    stack_root_flag: str | None,
    stack_profile_flag: str | None,
    gateway_url_flag: str | None,
    coordinator_url_flag: str | None,
    keycloak_url_flag: str | None,
) -> ResolvedConfig:
    environ = dict(os.environ)

    stack_root_override = stack_root_flag or environ.get("ARP_JARVIS_STACK_ROOT")
    if stack_root_override:
        stack_root = Path(stack_root_override).expanduser().resolve()
    else:
        found = find_stack_root(Path.cwd())
        if found is None:
            raise RuntimeError("Unable to locate stack root (missing stack.lock.json and compose/docker-compose.yml).")
        stack_root = found

    compose_file = stack_root / "compose" / "docker-compose.yml"
    env_local_path = stack_root / "compose" / ".env.local"
    env_profile_path = stack_root / "compose" / "profiles"

    env_local = load_env_file(env_local_path)

    stack_profile = _resolve_value(
        key="STACK_PROFILE",
        flags={"STACK_PROFILE": stack_profile_flag},
        environ=environ,
        env_local=env_local,
        env_profile={},
        default="dev-secure-keycloak",
    )

    profile_file = env_profile_path / f"{stack_profile.value}.env" if stack_profile.value else None
    env_profile = load_env_file(profile_file) if profile_file else {}

    stack_version = _resolve_stack_version(stack_root, env_local)

    gateway_port = env_local.get("RUN_GATEWAY_HOST_PORT") or "8081"
    coordinator_port = env_local.get("RUN_COORDINATOR_HOST_PORT") or "8082"
    keycloak_port = env_local.get("KEYCLOAK_HOST_PORT") or "8080"

    gateway_url = _resolve_value(
        key="ARP_JARVIS_GATEWAY_URL",
        flags={"ARP_JARVIS_GATEWAY_URL": gateway_url_flag},
        environ=environ,
        env_local=env_local,
        env_profile=env_profile,
        default=_host_url("localhost", gateway_port),
    )
    coordinator_url = _resolve_value(
        key="ARP_JARVIS_COORDINATOR_URL",
        flags={"ARP_JARVIS_COORDINATOR_URL": coordinator_url_flag},
        environ=environ,
        env_local=env_local,
        env_profile=env_profile,
        default=_host_url("localhost", coordinator_port),
    )
    keycloak_url = _resolve_value(
        key="ARP_JARVIS_KEYCLOAK_URL",
        flags={"ARP_JARVIS_KEYCLOAK_URL": keycloak_url_flag},
        environ=environ,
        env_local=env_local,
        env_profile=env_profile,
        default=_host_url("localhost", keycloak_port),
    )

    auth_issuer = _resolve_value(
        key="ARP_AUTH_ISSUER",
        flags={},
        environ=environ,
        env_local=env_local,
        env_profile=env_profile,
        default=None,
    )
    auth_profile = _resolve_value(
        key="ARP_AUTH_PROFILE",
        flags={},
        environ=environ,
        env_local=env_local,
        env_profile=env_profile,
        default=None,
    )
    auth_mode = _resolve_value(
        key="ARP_AUTH_MODE",
        flags={},
        environ=environ,
        env_local=env_local,
        env_profile=env_profile,
        default=None,
    )
    auth_discovery = _resolve_value(
        key="ARP_AUTH_OIDC_DISCOVERY_URL",
        flags={},
        environ=environ,
        env_local=env_local,
        env_profile=env_profile,
        default=None,
    )
    auth_token = _resolve_value(
        key="ARP_AUTH_TOKEN_ENDPOINT",
        flags={},
        environ=environ,
        env_local=env_local,
        env_profile=env_profile,
        default=None,
    )

    dev_cli_client_id = _resolve_value(
        key="ARP_DEV_CLI_CLIENT_ID",
        flags={},
        environ=environ,
        env_local=env_local,
        env_profile=env_profile,
        default="arp-dev-cli",
    )

    return ResolvedConfig(
        stack_root=stack_root,
        compose_file=compose_file,
        env_local=env_local_path,
        profile_env=profile_file or (env_profile_path / "dev-secure-keycloak.env"),
        stack_profile=stack_profile,
        stack_version=stack_version,
        gateway_url=ResolvedValue(_normalize_base_url(gateway_url.value), gateway_url.source),
        coordinator_url=ResolvedValue(_normalize_base_url(coordinator_url.value), coordinator_url.source),
        keycloak_url=ResolvedValue(_normalize_base_url(keycloak_url.value), keycloak_url.source),
        auth_profile=auth_profile,
        auth_mode=auth_mode,
        auth_issuer=ResolvedValue(_normalize_base_url(auth_issuer.value), auth_issuer.source),
        auth_discovery_url=ResolvedValue(_normalize_base_url(auth_discovery.value), auth_discovery.source),
        auth_token_endpoint=ResolvedValue(_normalize_base_url(auth_token.value), auth_token.source),
        dev_cli_client_id=dev_cli_client_id,
    )


def config_as_dict(config: ResolvedConfig) -> dict[str, Any]:
    return {
        "stack_root": str(config.stack_root),
        "compose_file": str(config.compose_file),
        "env_local": str(config.env_local),
        "profile_env": str(config.profile_env),
        "stack_profile": {"value": config.stack_profile.value, "source": config.stack_profile.source},
        "stack_version": {"value": config.stack_version.value, "source": config.stack_version.source},
        "gateway_url": {"value": config.gateway_url.value, "source": config.gateway_url.source},
        "coordinator_url": {"value": config.coordinator_url.value, "source": config.coordinator_url.source},
        "keycloak_url": {"value": config.keycloak_url.value, "source": config.keycloak_url.source},
        "auth_profile": {"value": config.auth_profile.value, "source": config.auth_profile.source},
        "auth_mode": {"value": config.auth_mode.value, "source": config.auth_mode.source},
        "auth_issuer": {"value": config.auth_issuer.value, "source": config.auth_issuer.source},
        "auth_discovery_url": {"value": config.auth_discovery_url.value, "source": config.auth_discovery_url.source},
        "auth_token_endpoint": {"value": config.auth_token_endpoint.value, "source": config.auth_token_endpoint.source},
        "dev_cli_client_id": {"value": config.dev_cli_client_id.value, "source": config.dev_cli_client_id.source},
    }


def public_keycloak_base(config: ResolvedConfig) -> str | None:
    profile = (config.auth_profile.value or "").lower()
    if profile.startswith("dev-") and config.keycloak_url.value:
        return config.keycloak_url.value
    return None
