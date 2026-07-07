# only-memories

only-memories is a local-first memory service for LLM agents.

It gives agents a memory system they can actually manage over time: typed memories, dated events, decaying or expiring relevance, graph connections, and ranked navigation through related context. The goal is not just storage. The goal is an agent-tended memory layer that can sit next to local assistants, MCP clients, or a dashboard such as Hermes.

## Why this exists

Most memory systems are optimized around ingestion and retrieval. only-memories is built around stewardship:

- Memories have a type, date, content, source metadata, and explicit connections.
- Axioms preserve identity-level facts that should never be muted or deleted.
- Different memory types can use different cadence, decay, and expiration behavior.
- Retrieval is a navigation process through connected memories, not just a top-k vector search.
- New connections are suggested from local embedding similarity and strengthened by use.
- Importance is ranked through both memory properties and graph centrality.
- Agents can continuously maintain the graph instead of waiting for occasional cleanup jobs.
- Source links let an operator or computer-use adapter navigate back to where a memory came from.

## Current scaffold

This repository starts with:

- A Python FastAPI backend.
- A SQLite-backed local memory store.
- Deterministic local embeddings for offline development.
- Connection creation based on cosine similarity.
- Ranked search and graph navigation endpoints.
- Axiom version chains where normal search sees only the newest version.
- Remembering search that can include historical axiom versions.
- Source links for files, settings, accounts, photos, contacts, and other local origins.
- An MCP server exposing memory tools.
- A React + Vite dashboard that calls the backend API.
- Docker Compose for running API and UI together.

## Project layout

```text
only-memories/
  backend/
    only_memories/
      api.py
      config.py
      embeddings.py
      mcp_server.py
      ranking.py
      schemas.py
      store.py
  frontend/
    src/
      App.tsx
      api.ts
      main.tsx
      styles.css
  docs/
    architecture.md
  docker-compose.yml
```

## Quick start

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,mcp]"
only-memories-api
```

The API runs at `http://localhost:8765`.

### UI

```bash
cd frontend
npm install
npm run dev
```

The UI runs at `http://localhost:5173`.

### Docker Compose

```bash
docker compose up --build
```

## API examples

Create a memory:

```bash
curl -X POST http://localhost:8765/memories \
  -H "content-type: application/json" \
  -d '{
    "type": "preference",
    "content": "The user prefers concrete local URLs and verified commands.",
    "source": "manual",
    "cadence": "weekly",
    "base_importance": 0.78
  }'
```

Create a versioned axiom:

```bash
curl -X POST http://localhost:8765/memories \
  -H "content-type: application/json" \
  -d '{
    "type": "axiom",
    "axiom_key": "user-name",
    "content": "The user name is Mauricio.",
    "source": "manual",
    "source_links": [{
      "label": "Contacts card",
      "kind": "mac-contacts",
      "uri": "x-apple-contacts://person/user-name"
    }]
  }'
```

Search ranked memories:

```bash
curl -X POST http://localhost:8765/search \
  -H "content-type: application/json" \
  -d '{"query": "what does the user prefer when debugging local services?", "limit": 5}'
```

Remembering search includes old axiom versions:

```bash
curl -X POST http://localhost:8765/search \
  -H "content-type: application/json" \
  -d '{"query": "what names has the user used?", "scope": "remembering", "limit": 5}'
```

## MCP

Install the backend with MCP extras:

```bash
cd backend
pip install -e ".[mcp]"
only-memories-mcp
```

The MCP server exposes:

- `remember`
- `recall`
- `axiom_versions`
- `navigate_memory`
- `reinforce_connection`

## Roadmap

- Agent maintenance loops for merge, prune, re-rank, and re-connect passes.
- Pluggable embedding providers.
- Source integrations for files, chat logs, browser history, calendars, and agent traces.
- Computer-use source collectors for macOS settings, social accounts, photos, contacts, and recent files.
- Standalone desktop packaging for macOS.
- Hermes dashboard integration.
- Multi-tenant local profiles with import/export.
