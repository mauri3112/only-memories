from __future__ import annotations

from .config import get_settings
from .schemas import MemoryCreate, ReinforceConnectionRequest, SearchRequest, SearchScope, SourceLinkCreate
from .store import MemoryStore

store = MemoryStore(get_settings().db_path)


def run() -> None:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise SystemExit("Install MCP extras first: pip install -e '.[mcp]'") from exc

    mcp = FastMCP("only-memories")

    @mcp.tool()
    def remember(
        content: str,
        type: str = "note",
        source: str = "mcp",
        axiom_key: str | None = None,
        source_uri: str | None = None,
        source_label: str | None = None,
        source_kind: str = "mcp",
    ) -> dict:
        """Create a new local memory."""

        source_links = []
        if source_uri:
            source_links.append(
                SourceLinkCreate(
                    label=source_label or source_uri,
                    kind=source_kind,
                    uri=source_uri,
                )
            )
        memory = store.create_memory(
            MemoryCreate(
                content=content,
                type=type,
                source=source,
                axiom_key=axiom_key,
                source_links=source_links,
            )
        )
        return memory.model_dump(mode="json")

    @mcp.tool()
    def recall(query: str, limit: int = 5, include_versions: bool = False) -> list[dict]:
        """Search ranked memories. Set include_versions for remembering searches."""

        request = SearchRequest(
            query=query,
            limit=limit,
            scope=SearchScope.remembering if include_versions else SearchScope.general,
        )
        return [
            memory.model_dump(mode="json")
            for memory in store.search(request.query, limit=limit, scope=request.scope)
        ]

    @mcp.tool()
    def axiom_versions(axiom_key: str) -> dict:
        """Return the current and historical versions of an axiom."""

        current, versions = store.version_history_for_axiom(axiom_key)
        return {
            "current": current.model_dump(mode="json"),
            "versions": [memory.model_dump(mode="json") for memory in versions],
        }

    @mcp.tool()
    def navigate_memory(memory_id: str, limit: int = 8) -> dict:
        """Navigate from one memory to connected memories."""

        origin, connections = store.navigate(memory_id, limit=limit)
        return {
            "origin": origin.model_dump(mode="json"),
            "connections": [memory.model_dump(mode="json") for memory in connections],
        }

    @mcp.tool()
    def reinforce_connection(
        source_id: str,
        target_id: str,
        amount: float = 0.1,
        reason: str = "mcp reinforcement",
    ) -> dict:
        """Strengthen a memory graph edge."""

        request = ReinforceConnectionRequest(
            source_id=source_id,
            target_id=target_id,
            amount=amount,
            reason=reason,
        )
        store.reinforce_connection(
            request.source_id,
            request.target_id,
            amount=request.amount,
            reason=request.reason,
        )
        return {"status": "ok"}

    mcp.run()


if __name__ == "__main__":
    run()
