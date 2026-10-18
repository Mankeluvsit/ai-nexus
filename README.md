# AI Nexus

Local-first AI resource discovery and execution platform.

## Design standard

AI Nexus uses an independently implemented **Flux-inspired** design standard for its dashboards, resource tools, model pages, agents, research workspaces, settings, and future modules. See [Design System](docs/DESIGN_SYSTEM.md) for palette tokens, responsive patterns, component contracts, accessibility, and licensing boundaries. The current UI is an early prototype; the complete shared React component library is not yet built.

## v0.2 dashboard and offline verification

Six responsive views are available: Overview, Discovery Hub, Model Explorer, Execution Lab, Activity, and Preferences. The interface supports dark, light and system appearance plus compact/comfortable density. Preferences are stored in the local browser. The dashboard is rendered from `ainexus/ui.html` and serves on loopback only.

The integration suite starts an isolated fake model API and validates discovery, real HTTP inference flow, persistence, and security checks **without LM Studio**. Run `python3 -m unittest discover -s tests -v` to execute all tests. Hardware, browser rendering, and a real installed model are separate acceptance gates tracked in [issue #1](https://github.com/Mankeluvsit/ai-nexus/issues/1). No cloud inference is enabled.

## v0.1 foundation

A dependency-free Python HTTP API with SQLite persistence. It provides a seeded registry of cloud AI providers, probes a user-specified local OpenAI-compatible model endpoint, and can execute a test chat request. No cloud request or paid API call is made automatically.

### Quick start

```bash
python3 -m ainexus
# Open http://127.0.0.1:8765
```

Optional environment: `AI_NEXUS_HOST` (default `127.0.0.1`), `AI_NEXUS_PORT` (default `8765`), `AI_NEXUS_DB` (default `./ai-nexus.sqlite3`), `AI_NEXUS_LOCAL_ENDPOINT` (default `http://127.0.0.1:1234/v1`), `AI_NEXUS_LOCAL_KEY` (optional).

### API

- `GET /health` — health check
- `GET /providers` — curated starter providers (catalog entries, not verified live quotas)
- `GET /models` — locally discovered model records
- `POST /discover/local` — query local `/models` and save the returned IDs
- `POST /execute` — execute a chat request on an **already discovered** local model; body `{"model":"...", "prompt":"..."}`
- `GET /executions` — latest execution metadata

Requests are restricted to loopback (non-loopback startup is rejected); cross-origin browser POSTs are rejected. The service does not accept arbitrary URLs from the request body, and it does not expose secrets or store response text. Local endpoint configuration is trusted operator input. No claims of free-tier availability or quota are made without independent verification.

### Test

```bash
python3 -m unittest discover -s tests -v
```

### Roadmap

1. Verifiable public provider metadata with source URLs and dates.
2. Explicit opt-in cloud connectors and secure secret handling.
3. Quota-aware routing with spending disabled by default.
4. Responsive dashboard, research agents, and sandboxed task execution.

License: MIT.
