from __future__ import annotations

from dataclasses import dataclass
import json
import sys
import time
from typing import Any
from urllib.parse import urlparse, urlunparse

from .http_client import post_form

try:
    import keyring  # type: ignore
except ImportError:  # pragma: no cover
    keyring = None


DEFAULT_DEV_ISSUER = "http://localhost:8080/realms/arp-dev"


@dataclass(frozen=True)
class AuthEndpoints:
    issuer: str
    token_endpoint: str
    device_endpoint: str
    client_id: str
    client_secret: str | None = None


@dataclass(frozen=True)
class TokenResponse:
    access_token: str
    token_type: str | None
    expires_in: int | None
    issued_at: float
    raw: dict[str, Any]

    def expires_at(self) -> float | None:
        if self.expires_in is None:
            return None
        return self.issued_at + float(self.expires_in)


def build_endpoints(
    *,
    issuer: str | None,
    token_endpoint: str | None,
    client_id: str,
    client_secret: str | None,
) -> AuthEndpoints:
    resolved_issuer = (issuer or DEFAULT_DEV_ISSUER).rstrip("/")
    resolved_token = (token_endpoint or f"{resolved_issuer}/protocol/openid-connect/token").rstrip("/")
    device_endpoint = f"{resolved_issuer}/protocol/openid-connect/auth/device"
    return AuthEndpoints(
        issuer=resolved_issuer,
        token_endpoint=resolved_token,
        device_endpoint=device_endpoint,
        client_id=client_id,
        client_secret=client_secret,
    )


def build_public_endpoints(
    *,
    issuer: str | None,
    token_endpoint: str | None,
    client_id: str,
    client_secret: str | None,
    public_base_url: str | None,
) -> AuthEndpoints:
    endpoints = build_endpoints(
        issuer=issuer,
        token_endpoint=token_endpoint,
        client_id=client_id,
        client_secret=client_secret,
    )
    if public_base_url:
        return AuthEndpoints(
            issuer=endpoints.issuer,
            token_endpoint=rewrite_base_url(endpoints.token_endpoint, public_base_url),
            device_endpoint=rewrite_base_url(endpoints.device_endpoint, public_base_url),
            client_id=endpoints.client_id,
            client_secret=endpoints.client_secret,
        )
    return endpoints


def keyring_available() -> bool:
    return keyring is not None


def load_cached_token(endpoints: AuthEndpoints, *, audience: str | None = None) -> TokenResponse | None:
    if keyring is None:
        return None
    raw = keyring.get_password("arp-jarvis", _keyring_key(endpoints, audience))
    if not raw:
        return None
    try:
        payload = json.loads(raw)
        token = TokenResponse(
            access_token=payload["access_token"],
            token_type=payload.get("token_type"),
            expires_in=payload.get("expires_in"),
            issued_at=float(payload.get("issued_at", 0)),
            raw=payload.get("raw", {}),
        )
    except Exception:
        return None
    expires_at = token.expires_at()
    if expires_at is not None and time.time() > expires_at - 10:
        return None
    return token


def store_token(endpoints: AuthEndpoints, token: TokenResponse, *, audience: str | None = None) -> bool:
    if keyring is None:
        return False
    payload = {
        "access_token": token.access_token,
        "token_type": token.token_type,
        "expires_in": token.expires_in,
        "issued_at": token.issued_at,
        "raw": token.raw,
    }
    keyring.set_password("arp-jarvis", _keyring_key(endpoints, audience), json.dumps(payload))
    return True


def clear_token(endpoints: AuthEndpoints, *, audience: str | None = None) -> bool:
    if keyring is None:
        return False
    try:
        keyring.delete_password("arp-jarvis", _keyring_key(endpoints, audience))
        return True
    except Exception:
        return False


def device_login(endpoints: AuthEndpoints, *, audience: str | None = None) -> TokenResponse:
    device_payload = {
        "client_id": endpoints.client_id,
        "scope": "openid",
    }
    if endpoints.client_secret:
        device_payload["client_secret"] = endpoints.client_secret
    device_info = post_form(endpoints.device_endpoint, device_payload)
    device_code = _require_field(device_info, "device_code")
    user_code = _require_field(device_info, "user_code")
    verification_uri = _require_field(device_info, "verification_uri")
    verification_uri_complete = device_info.get("verification_uri_complete")
    expires_in = int(device_info.get("expires_in") or 600)
    interval = int(device_info.get("interval") or 5)

    print("Complete login in your browser:", file=sys.stderr)
    if isinstance(verification_uri_complete, str) and verification_uri_complete.strip():
        print(f"  {verification_uri_complete}", file=sys.stderr)
    else:
        print(f"  {verification_uri}", file=sys.stderr)
        print(f"  Code: {user_code}", file=sys.stderr)

    deadline = time.time() + expires_in
    while time.time() < deadline:
        token_payload = {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device_code,
            "client_id": endpoints.client_id,
        }
        if audience:
            token_payload["audience"] = audience
        if endpoints.client_secret:
            token_payload["client_secret"] = endpoints.client_secret
        try:
            token_info = post_form(endpoints.token_endpoint, token_payload)
        except RuntimeError as exc:
            message = str(exc)
            if "authorization_pending" in message:
                time.sleep(interval)
                continue
            if "slow_down" in message:
                interval += 5
                time.sleep(interval)
                continue
            raise RuntimeError(message) from exc
        access_token = token_info.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise RuntimeError("Token response missing access_token")
        token = TokenResponse(
            access_token=access_token,
            token_type=token_info.get("token_type"),
            expires_in=token_info.get("expires_in"),
            issued_at=time.time(),
            raw=token_info,
        )
        return token
    raise RuntimeError("Device login timed out")


def client_credentials_token(endpoints: AuthEndpoints, *, audience: str | None = None) -> TokenResponse:
    payload = {
        "grant_type": "client_credentials",
        "client_id": endpoints.client_id,
    }
    if endpoints.client_secret:
        payload["client_secret"] = endpoints.client_secret
    if audience:
        payload["audience"] = audience
    token_info = post_form(endpoints.token_endpoint, payload)
    access_token = token_info.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise RuntimeError("Token response missing access_token")
    return TokenResponse(
        access_token=access_token,
        token_type=token_info.get("token_type"),
        expires_in=token_info.get("expires_in"),
        issued_at=time.time(),
        raw=token_info,
    )


def _require_field(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"Missing field in device auth response: {field}")
    return value.strip()


def _keyring_key(endpoints: AuthEndpoints, audience: str | None) -> str:
    suffix = audience or ""
    return f"{endpoints.issuer}|{endpoints.client_id}|{suffix}"


def rewrite_base_url(url: str, base_url: str) -> str:
    parsed = urlparse(url)
    base = urlparse(base_url)
    if not base.scheme or not base.netloc:
        return url
    return urlunparse((base.scheme, base.netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
