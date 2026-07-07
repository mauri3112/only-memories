# Agent Notes

This repo is a local-first memory service for LLM agents. Prefer changes that keep local operation simple, inspectable, and portable.

## Principles

- The backend must run without external services by default.
- External model or embedding providers should be optional plugins, not required startup dependencies.
- Memory ranking should combine typed metadata, dates, decay/expiration, graph connections, and similarity.
- Axioms are special: current versions should surface in normal search, but historical versions should remain accessible through remembering/audit flows.
- Source links should remain inspectable and navigable by future computer-use adapters.
- The dashboard should remain a usable operator surface, not a marketing page.
- Keep API contracts stable and documented as the project grows.

## Verification

Before committing backend changes:

```bash
cd backend
python -m compileall only_memories
pytest
```

Before committing frontend changes:

```bash
cd frontend
npm install
npm run build
```
