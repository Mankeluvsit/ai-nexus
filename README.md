# AI Nexus

Local-first AI resource discovery and execution platform.

## Design standard

AI Nexus uses an independently implemented **Flux-inspired** design standard for its dashboards, resource tools, model pages, agents, research workspaces, settings, and future modules. See [Design System](docs/DESIGN_SYSTEM.md) for palette tokens, responsive patterns, component contracts, accessibility, and licensing boundaries. The current UI is an early prototype; the complete shared React component library is not yet built.

## Evidence-aware model normalization

Catalog metadata now retains a strict distinction between a **provider-reported price** and verified free eligibility: a reported zero price does not imply that an account can access a model for free. Quotas, remaining credits, tool-calling results, and verified compatibility are `unknown` until separately established. Normalization is implemented in `ainexus/normalization.py` and covered by offline tests.

## v0.4 routing policy (experimental)

`ainexus/router.py` implements a **decision-only**, local-first model selector. The default policy blocks all cloud models and treats unknown pricing as ineligible. Cloud selection requires explicit `cloud_enabled=True` and verified price evidence, plus per-token input/output price caps (default zero). An additional opt-in is required to consider provider-reported, unverified zero pricing. Context requirements are fail-closed when metadata is missing. This module **does not perform inference, verify remaining quotas, or authorize spending**; do not treat a selection as proof of actual provider availability. Run `python3 -m unittest discover -s tests -v` for policy tests.

## Opt-in authenticated catalogs (experimental)

Read-only model listing is supported for allowlisted Groq, OpenRouter, Mistral and Cerebras endpoints. Supply keys **locally** via environment variables `AI_NEXUS_GROQ_KEY`, `AI_NEXUS_OPENROUTER_KEY`, `AI_NEXUS_MISTRAL_KEY`, and `AI_NEXUS_CEREBRAS_KEY`. Do not put real keys in GitHub, shell history, screenshots, or shared logs. Never use credentials from another application without that provider's authorization. Keys are transmitted only to their provider's fixed HTTPS endpoint; redirects are disallowed. No model inference or billable requests are issued by this connector, though provider account terms may apply to catalog reads.

`GET /connectors` reports configured/unconfigured state without revealing keys. `POST /discover/authenticated` with JSON body `{"provider":"groq"}` fetches the model list only when the key is available. This endpoint currently returns up to 200 records, does **not** persist them, and is intended for controlled testing. No cloud model is automatically activated. Live provider schemas and access terms have not yet been validated against credentials.

## v0.3 provider catalog (in progress)

The Discovery Hub now supports an opt-in **OpenRouter public model-list refresh**. Click **Refresh OpenRouter catalog** (no API key or inference request) to fetch a read-only HTTPS catalog, reject redirects, validate model IDs/context lengths, and store the result in SQLite with source URL and refresh timestamp. Repeated requests within 1 hour use the cached results. The catalogue has a 2 MB response limit and may fail safely if the remote listing is larger. The dashboard shows model identifiers, context windows, source links, and freshness status, with search and pagination. **Stale** means the cache age exceeds one hour; it does not mean a model has been removed. This does **not** establish whether a model is free, currently available to your account, supports tools, or has remaining quota. Public catalog refresh does not run automatically and is never a paid inference call. API: `GET /discovery/public` (optional `q`, `provider`, `limit` 1–200, and `offset` for paginated search), `POST /discover/public` with `{"provider":"openrouter"}`.

The Discovery Hub now reads `GET /catalog`: an evidence-aware registry of 12 provider and research-service entries with supported capability categories and official documentation links. `GET /catalog/capabilities` lists available tags. **All account eligibility, quotas, and free allowances default to unknown** until separately verified; no keys are requested or used. This is a curated offline catalog, **not** live provider discovery or automatic model enrollment. See `ainexus/catalog.py`.

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
- `GET /providers` — original compatible seven-provider listing (legacy)
- `GET /catalog` — expanded registry of provider capabilities and provenance status
- `GET /catalog/capabilities` — available capability tags
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
