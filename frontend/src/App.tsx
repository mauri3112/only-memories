import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Activity,
  BrainCircuit,
  CalendarClock,
  GitBranch,
  Network,
  Plus,
  Search,
  Sparkles,
} from "lucide-react";
import {
  Cadence,
  Memory,
  MemoryType,
  SearchScope,
  createMemory,
  listMemories,
  navigateMemory,
  searchMemories,
} from "./api";

const seedMemories: Memory[] = [
  {
    id: "seed-1",
    type: "preference",
    content: "The user prefers verified commands, concrete local URLs, and repo docs that match configuration.",
    happened_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    source: "sample",
    source_links: [
      {
        id: "seed-source-1",
        memory_id: "seed-1",
        label: "Operator note",
        kind: "manual",
        uri: "only-memories://sample/operator-note",
        open_hint: "Open the local source note",
        metadata: {},
        created_at: new Date().toISOString(),
      },
    ],
    cadence: "weekly",
    expires_at: null,
    base_importance: 0.84,
    access_count: 6,
    metadata: {},
    axiom_key: null,
    version: 1,
    supersedes_id: null,
    is_current: true,
    rank: 0.91,
  },
  {
    id: "seed-2",
    type: "axiom",
    content: "A person's identity can change over time, but earlier identity facts should remain preserved.",
    happened_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    source: "sample",
    source_links: [
      {
        id: "seed-source-2",
        memory_id: "seed-2",
        label: "Identity axiom proposal",
        kind: "design-note",
        uri: "only-memories://docs/axioms",
        open_hint: "Open the design note that introduced axiom memory",
        metadata: {},
        created_at: new Date().toISOString(),
      },
    ],
    cadence: "none",
    expires_at: null,
    base_importance: 0.78,
    access_count: 3,
    metadata: {},
    axiom_key: "identity-continuity",
    version: 2,
    supersedes_id: "seed-old-identity",
    is_current: true,
    rank: 0.82,
  },
];

const memoryTypes: MemoryType[] = [
  "axiom",
  "preference",
  "project",
  "decision",
  "concept",
  "source",
  "task",
  "event",
  "artifact",
  "skill",
  "system",
  "note",
];

const cadences: Cadence[] = ["none", "daily", "weekly", "monthly", "seasonal"];

export function App() {
  const [memories, setMemories] = useState<Memory[]>(seedMemories);
  const [selectedId, setSelectedId] = useState(seedMemories[0].id);
  const [connections, setConnections] = useState<Memory[]>([]);
  const [query, setQuery] = useState("");
  const [content, setContent] = useState("");
  const [type, setType] = useState<MemoryType>("note");
  const [cadence, setCadence] = useState<Cadence>("weekly");
  const [searchScope, setSearchScope] = useState<SearchScope>("general");
  const [axiomKey, setAxiomKey] = useState("");
  const [sourceUri, setSourceUri] = useState("");
  const [sourceKind, setSourceKind] = useState("manual");
  const [status, setStatus] = useState("sample data shown until the API responds");

  const selected = memories.find((memory) => memory.id === selectedId) ?? memories[0];

  useEffect(() => {
    listMemories()
      .then((items) => {
        if (items.length > 0) {
          setMemories(items);
          setSelectedId(items[0].id);
          setStatus("connected to local API");
        } else {
          setStatus("connected to local API, no memories yet");
        }
      })
      .catch(() => setStatus("API offline, sample data shown"));
  }, []);

  useEffect(() => {
    if (!selected || selected.id.startsWith("seed-")) {
      setConnections(seedMemories.filter((memory) => memory.id !== selected?.id));
      return;
    }
    navigateMemory(selected.id)
      .then((result) => setConnections(result.connections))
      .catch(() => setConnections([]));
  }, [selected]);

  const rankedMemories = useMemo(
    () => [...memories].sort((a, b) => (b.rank ?? 0) - (a.rank ?? 0)),
    [memories],
  );

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!query.trim()) {
      return;
    }
    const response = await searchMemories(query, searchScope);
    setMemories(response.results.length ? response.results : memories);
    if (response.results[0]) {
      setSelectedId(response.results[0].id);
    }
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!content.trim()) {
      return;
    }
    const sourceLinks = sourceUri.trim()
      ? [
          {
            label: sourceUri.trim(),
            kind: sourceKind.trim() || "manual",
            uri: sourceUri.trim(),
            open_hint: "Open this source with the local handler or computer-use adapter",
          },
        ]
      : [];
    const created = await createMemory({
      type,
      content,
      cadence: type === "axiom" ? "none" : cadence,
      source: "manual-ui",
      base_importance: 0.62,
      axiom_key: type === "axiom" ? axiomKey.trim() || undefined : undefined,
      source_links: sourceLinks,
    });
    setMemories((current) => [created, ...current.filter((memory) => !memory.id.startsWith("seed-"))]);
    setSelectedId(created.id);
    setContent("");
    setAxiomKey("");
    setSourceUri("");
    setStatus("memory added and connections suggested");
  }

  return (
    <main className="app-shell">
      <aside className="rail" aria-label="Primary">
        <div className="brand-mark">
          <BrainCircuit size={24} aria-hidden />
        </div>
        <button className="rail-button active" title="Memories">
          <Network size={20} aria-hidden />
        </button>
        <button className="rail-button" title="Activity">
          <Activity size={20} aria-hidden />
        </button>
        <button className="rail-button" title="Maintenance">
          <Sparkles size={20} aria-hidden />
        </button>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>only-memories</h1>
            <p>{status}</p>
          </div>
          <form className="search" onSubmit={handleSearch}>
            <Search size={18} aria-hidden />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Navigate memory..."
            />
            <select
              aria-label="Search scope"
              value={searchScope}
              onChange={(event) => setSearchScope(event.target.value as SearchScope)}
            >
              <option value="general">current</option>
              <option value="remembering">remembering</option>
            </select>
          </form>
        </header>

        <section className="memory-grid">
          <div className="graph-panel">
            <div className="section-title">
              <GitBranch size={17} aria-hidden />
              <span>Connection map</span>
            </div>
            <div className="graph-canvas" aria-label="Memory connection map">
              {rankedMemories.slice(0, 7).map((memory, index) => (
                <button
                  key={memory.id}
                  className={`node node-${index + 1} ${memory.id === selected?.id ? "selected" : ""}`}
                  onClick={() => setSelectedId(memory.id)}
                  title={memory.content}
                >
                  {memory.type.slice(0, 2)}
                </button>
              ))}
              <span className="edge edge-a" />
              <span className="edge edge-b" />
              <span className="edge edge-c" />
            </div>
          </div>

          <div className="list-panel">
            <div className="section-title">
              <BrainCircuit size={17} aria-hidden />
              <span>Ranked memories</span>
            </div>
            <div className="memory-list">
              {rankedMemories.map((memory) => (
                <button
                  key={memory.id}
                  className={`memory-row ${memory.id === selected?.id ? "selected" : ""}`}
                  onClick={() => setSelectedId(memory.id)}
                >
                  <span className="row-type">{memory.type}</span>
                  <span className="row-content">{memory.content}</span>
                  {memory.type === "axiom" ? (
                    <span className="row-version">v{memory.version}</span>
                  ) : null}
                  <span className="row-rank">{Math.round((memory.rank ?? 0) * 100)}</span>
                </button>
              ))}
            </div>
          </div>
        </section>

        <form className="composer" onSubmit={handleCreate}>
          <textarea
            value={content}
            onChange={(event) => setContent(event.target.value)}
            placeholder="Add a memory manually..."
          />
          <div className="composer-controls">
            <select value={type} onChange={(event) => setType(event.target.value as MemoryType)}>
              {memoryTypes.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
            <select value={cadence} onChange={(event) => setCadence(event.target.value as Cadence)}>
              {cadences.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
            <input
              value={axiomKey}
              onChange={(event) => setAxiomKey(event.target.value)}
              placeholder="axiom key"
              disabled={type !== "axiom"}
            />
            <input
              value={sourceUri}
              onChange={(event) => setSourceUri(event.target.value)}
              placeholder="source URI"
            />
            <input
              value={sourceKind}
              onChange={(event) => setSourceKind(event.target.value)}
              placeholder="source kind"
            />
            <button type="submit">
              <Plus size={18} aria-hidden />
              Add memory
            </button>
          </div>
        </form>
      </section>

      <aside className="inspector" aria-label="Memory detail">
        <div className="section-title">
          <CalendarClock size={17} aria-hidden />
          <span>Inspector</span>
        </div>
        {selected ? (
          <>
            <h2>{selected.type}</h2>
            {selected.type === "axiom" ? (
              <div className="axiom-banner">
                <span>{selected.axiom_key ?? "derived-key"}</span>
                <strong>v{selected.version}</strong>
                <em>{selected.is_current ? "current" : "historic"}</em>
              </div>
            ) : null}
            <p className="selected-content">{selected.content}</p>
            <dl>
              <div>
                <dt>Date</dt>
                <dd>{new Date(selected.happened_at).toLocaleDateString()}</dd>
              </div>
              <div>
                <dt>Cadence</dt>
                <dd>{selected.cadence}</dd>
              </div>
              <div>
                <dt>Expiration</dt>
                <dd>{selected.expires_at ? new Date(selected.expires_at).toLocaleDateString() : "none"}</dd>
              </div>
              <div>
                <dt>Importance</dt>
                <dd>{Math.round(selected.base_importance * 100)}</dd>
              </div>
              <div>
                <dt>Source</dt>
                <dd>{selected.source}</dd>
              </div>
            </dl>
            <div className="source-links">
              <h3>Source links</h3>
              {selected.source_links.length === 0 ? (
                <p>No source links yet.</p>
              ) : (
                selected.source_links.map((sourceLink) => (
                  <a key={sourceLink.id} href={sourceLink.uri}>
                    <span>{sourceLink.kind}</span>
                    {sourceLink.label}
                  </a>
                ))
              )}
            </div>
            <div className="connections">
              <h3>Connected memories</h3>
              {connections.length === 0 ? (
                <p>No connected memories yet.</p>
              ) : (
                connections.map((memory) => (
                  <button key={memory.id} onClick={() => setSelectedId(memory.id)}>
                    <span>{memory.type}</span>
                    {memory.content}
                  </button>
                ))
              )}
            </div>
          </>
        ) : null}
      </aside>
    </main>
  );
}
