# Architecture

only-memories is designed as a local memory graph that agents can read and tend over time.

## Core model

A memory has:

- `type`: the semantic class of memory, such as `preference`, `project`, `decision`, `event`, `source`, or `concept`.
- `happened_at`: when the memory became true or relevant.
- `content`: the remembered information.
- `connections`: typed weighted links to other memories.

Some memory types also carry:

- `cadence`: how often the memory naturally becomes relevant again.
- `expiration`: a hard date after which the memory should no longer be surfaced unless explicitly requested.
- `decay`: gradual reduction in importance over time.

## Ranking

The starter implementation ranks memories using:

- Similarity between query and memory content.
- Base importance.
- Recency and decay.
- Cadence boosts.
- Connection centrality.
- Access reinforcement.

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

## Integration surfaces

- HTTP API for local dashboards and apps.
- MCP server for agents and LLM clients.
- Future desktop package for standalone macOS use.
- Future Hermes dashboard integration.
