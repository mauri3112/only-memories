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
- Typed connection relations for related, updating, extending, derived, and supporting facts.
- Ranked search and graph navigation endpoints.
- First-class spaces, knowledge/activity planes, provenance, verification status, and
  idempotent external writes for agent experiments.
- Axiom version chains where normal search sees only the newest version.
- Versioned replacement chains for non-axiom memories through `supersedes_id`.
- Soft forgetting where hidden memories remain inspectable for audit and recovery.
- Remembering search that can include historical memory versions.
- Source links for files, settings, accounts, photos, contacts, and other local origins.
- An MCP server exposing memory tools.
- A React + Vite operator console for search, graph navigation, provenance, version history,
  lifecycle actions, and manual capture.
- Preview-and-approve stewardship for expired and duplicate memories.
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
    memory-types.md
    source-links.md
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

See [Memory Types](docs/memory-types.md) for the type map, Mermaid diagrams, and behavioral differences between axioms, preferences, events, tasks, artifacts, sources, and other memory classes.

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

Experiment retrieval should be explicitly scoped. Normal search defaults to the
`knowledge` plane and excludes agent-generated recaps; audit callers can opt into both:

```bash
curl -X POST http://localhost:8765/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"Northstar evidence","intent":"evidence","space_ids":["experiment:run-two"],"planes":["knowledge"],"provenance_classes":["primary_source"],"verification_statuses":["verified"]}'
```

Writers can supply `external_key` and/or `Idempotency-Key`. Replays return the original
memory; reusing the same key with a different payload returns a conflict. Agent run
recaps belong in the `activity` plane with `provenance_class: "agent_recap"`.

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
- `forget_memory`
- `restore_memory`
- `axiom_versions`
- `navigate_memory`
- `reinforce_connection`
- `preview_maintenance`
- `apply_maintenance_proposal`
- `dismiss_maintenance_proposal`

## V1 operator workflows

- **Memories:** rank and filter current, historical, forgotten, or expired memories; inspect
  typed graph edges, source links, and version chains; create, edit, forget, or restore records.
- **Maintenance:** generate deterministic proposals without changing data, then apply or dismiss
  each proposal individually. Decisions remain in SQLite for audit.
- **Settings:** inspect local API and database availability. No external service is required.

Substantive content edits create a new version that supersedes the prior memory. Metadata-only
edits update the current record in place. The accepted visual reference is
[docs/ui-concept-v1.png](docs/ui-concept-v1.png).

## Post-v1 roadmap

- Pluggable embedding providers.
- Source integrations for files, chat logs, browser history, calendars, and agent traces.
- Computer-use source collectors for macOS settings, social accounts, photos, contacts, and recent files.
- Standalone desktop packaging for macOS.
- Hermes dashboard integration.
- Multi-tenant local profiles with import/export.
