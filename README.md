<div align="center">
  <a href="https://agent-runtime-protocol.com/">
    <picture>
      <source srcset="./assets/JARVIS_Long_Transparent.png">
      <img alt="ARP Logo" src="./assets/JARVIS_Long_Transparent.png" width="80%">
    </picture>
  </a>
</div>

# JARVIS Release (Stack Distribution)

`JARVIS_Release` is the version-pinned, runnable stack distribution for JARVIS (ARP `spec/v1`).
It ships a lock file + Docker Compose setup that brings up a full local stack with sensible defaults.

## What this repo ships

Core spec-facing services:
- Run Gateway
- Run Coordinator
- Atomic Executor
- Composite Executor
- Node Registry
- Selection Service
- PDP

Internal JARVIS services:
- Run Store
- Event Stream
- Artifact Store

Local dev STS (default profile):
- Keycloak (`dev-secure-keycloak`)

## Version pinning

- `stack.lock.json` is the stack source of truth (component versions, node pack versions, helper libs).
- `pyproject.toml` pins the same component versions for the `arp-jarvis` meta package.

Decision: **Mode B / per-service GHCR images**.
Each JARVIS component repo publishes a GHCR image on `vX.Y.Z` tags. This repo consumes those images
via Docker Compose and pins the references in `stack.lock.json` (digests can be added for stronger reproducibility).

## Quickstart (dev-secure-keycloak)

1) Copy the env template and keep the default profile:

```bash
cp compose/.env.example compose/.env.local
```

2) Configure the LLM (required for Selection Service + Composite Executor):

- Set `ARP_LLM_API_KEY` and `ARP_LLM_CHAT_MODEL` in `compose/.env.local`.
- OpenAI is the default profile; `ARP_LLM_PROFILE=openai` is optional.
- For offline tests, you can opt into `ARP_LLM_PROFILE=dev-mock` (not the default).

3) Bring up the stack:

```bash
docker compose --env-file compose/.env.local -f compose/docker-compose.yml up -d
```

4) Health check (Run Gateway):

```bash
curl -s http://localhost:8081/v1/health
```

Notes:
- Keycloak is exposed on `http://localhost:8080` (issuer default).
- Run Gateway is exposed on `8081`. Run Coordinator is exposed on `8082` (configure via `RUN_COORDINATOR_HOST_PORT`).
- If you change `KEYCLOAK_HOST_PORT`, update `ARP_AUTH_ISSUER` in `compose/profiles/dev-secure-keycloak.env`.
- `dev-insecure` disables inbound JWT checks but still runs Keycloak for service-to-service token exchange.
- Node Registry runs with `ARP_AUTH_MODE=optional` to allow Selection Service calls (current Selection
  client does not attach bearer tokens).

## Stack profiles

Set `STACK_PROFILE` in `compose/.env.local` to one of:
- `dev-secure-keycloak` (default)
- `dev-insecure`
- `enterprise` (template only)

## Meta CLI (optional)

Install locally and inspect pinned component versions:

```bash
python3 -m pip install -e .
arp-jarvis versions
```

You can also invoke component CLIs via `arp-jarvis`:

```bash
arp-jarvis run-gateway --help
arp-jarvis run-coordinator --help
arp-jarvis atomic-executor --help
```

## Repo layout

```
JARVIS_Release/
  stack.lock.json
  compose/
    docker-compose.yml
    .env.example
    profiles/
      dev-secure-keycloak.env
      dev-insecure.env
      enterprise.env
    keycloak/
      realm-arp-dev.json
  assets/ (diagrams, logos)
```
