# AI Nexus Design System — Flux-inspired

Status: **adopted as the default design direction** on 2026-10-18.

Reference: https://dashboardpack.com/theme-details/flux-dashboard-nextjs/
Reference documentation: https://flux.dashboardpack.com/docs/theming

## Licensing and provenance
Flux is a commercial DashboardPack template, notwithstanding its product-page "MIT" label. Its vendor lists paid licenses and restrictions. **Do not copy template source, proprietary assets, premium components, or branding without checking the purchased license and actual source licenses.** This project currently uses independently authored CSS and markup inspired by general visual principles, not copied theme code.

## Mandatory coverage
All AI Nexus dashboards, settings, documentation UI, research, model, agent, monitoring, resource, and experimentation pages should follow this system. Connected external applications retain their own design unless integrated or explicitly customized. This document should serve as a reference for other projects when the owner asks to reuse the same design.

## Product principles
1. Dark-first, polished, restrained gradient accents. Light and system themes must be supported in the React UI.
2. Discoverability: global navigation, breadcrumbs, search, consistent module naming, useful empty states.
3. Accessibility: keyboard focus, sufficient contrast, semantic HTML, accessible charts and tables, reduced motion, labels, responsive touch targets.
4. Responsive: sidebar on wide screens, drawer or bottom-compatible navigation on narrow screens; no horizontal scrolling for core tasks.
5. Density modes: compact / comfortable; persistent per-user preferences, not hidden one-off CSS adjustments.
6. Visual hierarchy: meaningful status color; charts, KPIs and actions are grouped by task, not decorative.
7. Reuse shared primitives, not unrelated component systems per module.
8. Separate UI presentation schema from data and API contracts.

## Theme tokens (AI Nexus original palette)
These values are **AI Nexus design defaults**, not a claim that Flux uses these exact values.

| Role | Dark | Light |
| --- | --- | --- |
| page | #0b1020 | #f5f7fc |
| surface | #121b2e | #ffffff |
| raised | #1b2840 | #eef2fa |
| border | #2c3b55 | #d5ddeb |
| foreground | #e9f0fa | #16243a |
| secondary text | #a9b8cf | #54647b |
| primary | #7c86ff | #4f46e5 |
| accent | #30d0c0 | #078e85 |
| success | #37c891 | #12805f |
| warning | #f5bb63 | #9d6200 |
| danger | #fa728b | #c92f52 |

Use CSS custom properties / Tailwind theme tokens; define role-based references rather than scattering hardcoded colors. Use OKLCh tokens in the future React/Tailwind implementation for consistent light/dark interpolation.

Other default tokens:
- Font: system-ui / Inter (only when licensed or bundled appropriately); monospace for code and IDs.
- Radius: 12px cards, 8px inputs, 999px badges.
- Spacing: 4px base; 8/12/16/24/32px.
- Transitions: 120–180ms; disable nonessential motion for `prefers-reduced-motion`.
- Gradients: subtle primary-to-accent on prominent brand elements or important controls only.
- Focus rings: clearly visible 2px outline plus offset.
- Page width: adaptive, default 1440px max; data tables can use available width.

## Component contracts
- `AppShell`: app navigation, title, breadcrumbs, scoped actions, responsive menu.
- `MetricCard`: label, value, comparison, status, timestamp; never fake numbers.
- `ResourceTable`: filter, sort, loading/empty/error states, sources, verification timestamps.
- `ProviderCard`: name, capabilities, eligibility, quota/source provenance, live/tested/unknown.
- `ExecutionPanel`: prompt, selected model, progress, cancel where supported, result metadata.
- `TaskTimeline`: explicit state transitions, delegation, artifacts, errors and resumable checkpoints.
- `ThemePreferences`: light/dark/system, density, accent, motion.
- `StatusPill`: semantic status; never communicate state by color alone.
- `ChartPanel`: title, date range, units, legend, accessible tabular alternative.
- `ConfirmDialog`: consequence and scope for potentially destructive/paid actions.

## Resource schema (not theme vendor schema)
A future model/provider registry should hold: id, provider_id, display_name, modality, context_window, supported_features, cost_status, rate_limit, eligibility, quota_reset, verified_at, source_urls, test_results, and provenance/confidence. **Unknown is distinct from zero and unavailable.** Never infer quota availability from model context length.

## Implementation plan
- Current v0.1: progressively upgrade the dependency-free prototype's HTML/CSS using these tokens.
- Next UI milestone: React + TypeScript dashboard with reusable primitives, preference persistence, accessible responsive shell, and a real component gallery.
- Later: Next.js only if server-side routing/rendering genuinely benefits the project; local-first static UI remains acceptable.
- Enforce via UI reviews, visual regression tests, contrast checks, and mobile viewport checks.
- Keep backend and inference services independent of UI framework choice.

## Attribution
Design direction inspired by DashboardPack Flux (https://dashboardpack.com/theme-details/flux-dashboard-nextjs/). No claim of affiliation or ownership.
