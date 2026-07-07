# Architecture

only-memories is designed as a local memory graph that agents can read and tend over time.

## Core model

A memory has:

- `type`: the semantic class of memory, such as `axiom`, `preference`, `project`, `decision`, `event`, `source`, or `concept`.
- `happened_at`: when the memory became true or relevant.
- `content`: the remembered information.
- `connections`: typed weighted links to other memories.
- `source_links`: one or more local or remote origins that explain where the memory came from.

Some memory types also carry:

- `cadence`: how often the memory naturally becomes relevant again.
- `expiration`: a hard date after which the memory should no longer be surfaced unless explicitly requested.
- `decay`: gradual reduction in importance over time.

See [Memory Types](memory-types.md) for a Mermaid diagram of the memory type taxonomy and the behavioral differences between each type.

## Axioms

Axioms are identity-level memories that should never be muted or deleted. They can be superseded, but the concept stays alive.

For example, a user's name can change after marriage. The newest name should be the version normal searches return, while the earlier name should remain available on a second plane for remembering, audit, and identity continuity.

The starter implementation models this with:

- `axiom_key`: the stable concept, such as `user-name`.
- `version`: the version number for that axiom.
- `supersedes_id`: the prior version.
- `is_current`: whether this is the version normal search should read.

General search and memory listing return only current versions. Remembering search can include older versions.

## Ranking

The starter implementation ranks memories using:

- Similarity between query and memory content.
- Base importance.
- Recency and decay.
- Cadence boosts.
- Connection centrality.
- Access reinforcement.

Current axioms do not decay. Historical axiom versions are preserved but ranked as second-plane context unless remembering search is requested.

The ranking module is intentionally small and replaceable. The long-term direction is closer to a search engine over a personal knowledge graph than a plain vector database.

## Connections

Connections can be created manually or suggested automatically. The current local embedding implementation uses deterministic hashed token vectors so development works offline. Later providers can replace this with sentence embeddings or model-native embeddings without changing API contracts.

## Agent stewardship

The differentiator is active memory management. A future maintenance agent should:

- Merge duplicate memories.
- Retire expired memories.
- Down-rank stale but non-expired memories.
- Strengthen useful paths.
- Create missing bridge memories.
- Import and normalize source data.
- Explain why a memory was surfaced.

## Source collection

Source links make memories inspectable. A memory can link to a file path, a settings pane, a contact card, a photo library item, a social account profile, a browser page, or an app-specific deep link.

A future Mac collector can use computer use and local APIs to populate memories from:

- Computer settings: host name, locale, installed apps, accessibility settings, network names.
- Social media accounts: profile names, handles, relationship context, public profile metadata.
- Photos: locations, recurring people, travel patterns, events, and time ranges.
- Contacts: names, addresses, birthdays, organizations, relationship hints.
- File history: recently used files, project folders, document titles, and app recents.

Computer-use adapters can then navigate back to the source from the stored link when the operator asks why a memory exists or wants to inspect the origin.

## Integration surfaces

- HTTP API for local dashboards and apps.
- MCP server for agents and LLM clients.
- Future desktop package for standalone macOS use.
- Future Hermes dashboard integration.
