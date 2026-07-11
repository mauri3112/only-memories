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
- `forgetting`: soft lifecycle state for outdated, rejected, or intentionally hidden memories that should remain auditable.

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

Non-axiom memories can also be superseded by passing `supersedes_id` when creating the replacement memory. The old memory is marked non-current, the new memory gets the next version, and an `updates` connection links the new fact back to the prior one.

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

Connections can be created manually or suggested automatically. Each connection has a weight and a semantic relation:

- `related`: a general association, including similarity-suggested links.
- `updates`: the source memory changes or replaces the target memory.
- `extends`: the source memory adds detail without invalidating the target.
- `derives`: the source memory is inferred from the target.
- `supports`: the source memory provides evidence for the target.

The current local embedding implementation uses deterministic hashed token vectors so development works offline. Later providers can replace this with sentence embeddings or model-native embeddings without changing API contracts.

## Forgetting

Forgetting is soft by default. A forgotten memory is marked with `is_forgotten`, `forgotten_at`, and an optional `forget_reason`; it is hidden from normal listing, search, and navigation, but remains available when an audit or remembering flow explicitly includes forgotten memories.

Expiration is time-based hiding. Expired memories are also excluded from normal retrieval unless the caller asks to include expired results. This keeps temporary memories from becoming permanent context while preserving provenance for inspection.

## Agent stewardship

The differentiator is active memory management. V1 makes this approval-based: a preview run
writes auditable proposals but does not modify memories. The operator applies or dismisses each
proposal. Current deterministic proposals retire expired memories and collapse same-type near
duplicates. Duplicate collapse transfers unique source links and outgoing connections to the
canonical memory, then soft-forgets the duplicate.

A future maintenance agent can extend this foundation to:

- Merge duplicate memories.
- Retire expired memories.
- Soft-forget memories that are rejected, contradicted, or no longer relevant.
- Down-rank stale but non-expired memories.
- Strengthen useful paths.
- Create missing bridge memories.
- Import and normalize source data.
- Explain why a memory was surfaced.

Automatic scheduling and unreviewed mutation are intentionally out of scope for v1.

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
