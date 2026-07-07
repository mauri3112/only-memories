from __future__ import annotations

from .config import get_settings
from .schemas import MemoryCreate, ReinforceConnectionRequest, SearchRequest
from .store import MemoryStore

store = MemoryStore(get_settings().db_path)


def run() -> None:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise SystemExit("Install MCP extras first: pip install -e '.[mcp]'") from exc

    mcp = FastMCP("only-memories")

    @mcp.tool()
    def remember(content: str, type: str = "note", source: str = "mcp") -> dict:
        """Create a new local memory."""

        memory = store.create_memory(MemoryCreate(content=content, type=type, source=source))
        return memory.model_dump(mode="json")

    @mcp.tool()
    def recall(query: str, limit: int = 5) -> list[dict]:
        """Search ranked memories."""

        request = SearchRequest(query=query, limit=limit)
        return [memory.model_dump(mode="json") for memory in store.search(request.query, limit=limit)]

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
