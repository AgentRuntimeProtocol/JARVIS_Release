<div align="center">
  <a href="https://agent-runtime-protocol.com/">
    <picture>
      <source srcset="./images/JARVIS_Long_Transparent.png">
      <img alt="ARP Logo" src="./images/JARVIS_Long_Transparent.png" width="80%">
    </picture>
  </a>
</div>

<div align="center">
  <h3>First-party out-of-the-box OSS implementation for ARP.</h3>
  <h4>Ready to use. Ready to integrate. Ready to expand.</h4>
</div>

<div align="center">
  <a href="https://opensource.org/licenses/MIT" target="_blank"><img src="https://img.shields.io/pypi/l/arp-jarvis" alt="PyPI - License"></a>
  <a href="https://pypistats.org/packages/arp-jarvis" target="_blank"><img src="https://img.shields.io/pepy/dt/arp-jarvis" alt="PyPI - Downloads"></a>
  <a href="https://pypi.org/project/arp-jarvis/#history" target="_blank"><img src="https://img.shields.io/pypi/v/arp-jarvis?label=%20" alt="Version"></a>
</div>

<div align="center">
  <a href="https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/agentruntimeprotocol/JARVIS_Release" target="_blank"><img src="https://img.shields.io/static/v1?label=Dev%20Containers%20For%20JARVIS%20Stack&message=Open&color=blue&logo=visualstudiocode" alt="Open in Dev Containers"></a>
  <a href="https://codespaces.new/agentruntimeprotocol/JARVIS_Release" target="_blank"><img src="https://github.com/codespaces/badge.svg" alt="Open JARVIS Stack in Github Codespace" title="Open JARVIS Stack in Github Codespace" width="150" height="20"></a>
</div>

---

**JARVIS** is the *first-party*, *open-source* implementation of the **Agent Runtime Protocol (ARP)** ecosystem.

It is designed to be:
- Standard-first: ARP contracts are the source of truth.
- Modular: swap runtimes, tool registries, and orchestration layers without rewriting your app.
- Runtime-agnostic: run agents locally, in containers, or in managed environments.
- Tool-agnostic: tools can be local functions, remote services, or adapters to other ecosystems.

This repository provides a single access point for *JARVIS* and a unified CLI to run the stack with pinned, known-compatible versions. It is the recommended way of working with the *JARVIS* stack as it evolves over time.

---

## What you can do with **JARVIS**

- Run an *agent as a service* (HTTP API) with a predictable lifecycle: submit runs, stream events, fetch results.
- Attach tools through a Tool Registry (discover tools, validate schemas, invoke tools).
- Orchestrate multiple runtimes through a Daemon (spawn/register instances, route runs).

As an first-party implementation of the ARP protocol, JARVIS is also supported by the owners of the standard, making it the most up-to-date implementation in this rapidly-changing ecosystem.

On the other hand, thanks to the modular nature of ARP, extending on JARVIS or swapping out components for your custom need is extremely easy. Just make sure your component adheres to the ARP Standard, and link them together via configurable endpoints in the JARVIS components. Each component does not need to know how the other parts are implemented, just that they are standard-compliant!

---

## Quickstart with the JARVIS Stack

### Prerequisites
- Python 3.10+ (recommended: a virtualenv)
- Recommended: A shell with multi-tab support.

### Install the *JARVIS* distribution 
This distribution pins compatible OSS component versions, so that you don't need to worry about contract compatibility issues.
```bash
pip install arp-jarvis
```

### Start the Tool Registry

The first step is to make sure the Tool Registry is running. It provides tool discovery and execution capabilities to the agents.

```bash
arp-jarvis tool-registry --host 127.0.0.1 --port 8081
```

### Run a demo

There are 2 ways to see *JARVIS* agents run. You can either directly interact with an agent runtime instance, or you can do it through the daemon that manages multiple agent runtimes. 

Either way is officially supported, but we expect most users to utilize the daemon for its runtime instance lifecycle management capabilities. 

#### Option 1. Start a *runtime* instance directly

After the `tool-registry` is running, open up another terminal tab and spin up a *runtime* instance.

```bash
arp-jarvis runtime serve --host 127.0.0.1 --port 8080 --tool-registry-url http://127.0.0.1:8081
```

Then, you can run a simple request to the *runtime* instance:

```bash
# Create a run
curl -s -X POST http://127.0.0.1:8080/v1/runs \
  -H 'Content-Type: application/json' \
  -d '{"input":{"goal":"What is (19*23)?"}}'

# Then fetch the result (copy run_id from the response)
curl -s http://127.0.0.1:8080/v1/runs/<run_id>/result
```

#### Option 2. Manage the *runtime* instances through the *daemon* service

The other, more capable approach of running *runtime* instances is through the daemon

1) Start the daemon in a new terminal tab:

```bash
arp-jarvis daemon --host 127.0.0.1 --port 8082
```

2) Register a runtime profile (safe list) for managed instances:

```bash
cat > runtime_profile_default.json <<'JSON'
{
  "runtime_name": "jarvis-runtime",
  "defaults": {
    "tool_registry_url": "http://127.0.0.1:8081"
  },
  "extensions": {
    "arp.jarvis.exec": {
      "driver": "command",
      "command_template": ["arp-jarvis-runtime", "serve", "--port", "{port}"]
    }
  }
}
JSON

arp-jarvis daemon runtime-profiles upsert default --request-json runtime_profile_default.json
```

3) Start a managed runtime instance:

```bash
arp-jarvis daemon start --runtime-profile default --count 1
```

4) Submit a run request (via the daemon API):

```bash
curl -s -X POST http://127.0.0.1:8082/v1/runs \
  -H 'Content-Type: application/json' \
  -d '{"input":{"goal":"What is (19*23)?"},"runtime_selector":{"runtime_profile":"default"}}'
```

### Getting run results

*JARVIS* follows an async pattern at the API layer: submit a run, then fetch status/result (and optionally trace data).

```bash
# Status
curl -s http://127.0.0.1:8082/v1/runs/<run_id>

# Result
curl -s http://127.0.0.1:8082/v1/runs/<run_id>/result

# Trace
curl -s http://127.0.0.1:8082/v1/runs/<run_id>/trace
```

> [!NOTE]
> For production deployments, you will want auth, isolation, and observability beyond the MVP defaults. JARVIS is still in its early stage, and these functionalities are being implemented and will be included in future releases.

---

## Architecture (high level)

JARVIS is the first-party implementation of the ARP ecosystem. It accompanies every *ARP Standard* release to provide both an out-of-the-box solution and an implementation reference. 

Here's an diagram of its architecture, closely aligning with the standard:

<div align="center">
  <picture>
    <source srcset="./images/ARP_Ecosystem_Diagram_Basic.png">
    <img alt="ARP_Basic_Diagram" src="./images/ARP_Ecosystem_Diagram_Basic.png" width="80%">
  </picture>
</div>

## Design principles

* ARP is *standard-first*: implementations should strictly follow the spec, not invent new behavior without an extension mechanism. 
  * This *does not* mean there are no ways to extend on the contract for your needs. ARP has built-in `extensions` field in the request body for passing custom fields.
* *Interoperability* is a first-class requirement:
  * Support adapters to other ecosystems (e.g., MCP for tools, A2A/Agent Protocol for agent-to-agent / agent-as-a-service).
  * The ARP standard should never prevent bridging; it should make bridging clean.

---

## Unified CLI 

This meta package installs the pinned OSS components and exposes a single CLI that forwards to component CLIs.

### Examples

```bash
arp-jarvis --help
arp-jarvis runtime --help
arp-jarvis tool-registry --help
arp-jarvis daemon --help
```

If you prefer using the component CLIs directly, you can still do so.

```bash
arp-jarvis-runtime --help
arp-jarvis-tool-registry --help
arp-jarvis-daemon --help
```

---

## Repositories in the ecosystem

### Standard 

Start here for an overview of the ARP Standard Contract. It also covers SDK generation.

* `AgentRuntimeProtocol/ARP_Standard` — ARP standard (OpenAPI/JSON schemas + SDK generation + conformance)

### First-party OSS implementations - *JARVIS* stack

* `AgentRuntimeProtocol/JARVIS_Runtime` — reference agent *runtime* implementation
* `AgentRuntimeProtocol/JARVIS_Tool_Registry` — reference *Tool Registry* implementation for tool discovery + invocation
* `AgentRuntimeProtocol/JARVIS_Daemon` — reference Daemon implementation for runtime instances orchestration

---

## Current Priorities

The development on *ARP* and *JARVIS* is very active and new features are implemented and rolled out on a weekly basis. Some of our immediate focus points on *JARVIS* components include:

* Interop adapters for `tool-registry`: MCP support and integration, Agent Protocol facade, A2A bridge.
* Hardening daemon-managed instances: profile safety, lifecycle management, and isolation.
* Better docs + examples: end-to-end demos, deployment patterns, and interoperability guides.
* Observability improvements: richer traces and easier integrations.

---

## Contributing

If you want to help:

* Start small. Even documentation or codestyle fixes are valuable. 
* It's *okay* and maybe even *expected* that you will use AI coding agents like Claude Code or Codex. But before you want an PR approved, review it first. We will not check in low-quality code.
* Add or improve:
  * documentation that reduces time-to-first-run
  * end-to-end examples
  * integration tests
  * compatibility/interop adapters

Use GitHub Issues for bugs/feature requests and PRs for changes.

---

## License

All OSS projects are under MIT license. See the LICENSE file in each repository.
