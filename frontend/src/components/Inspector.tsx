import { ExternalLink, RotateCcw } from "lucide-react";
import { GraphResponse, Memory, VersionHistory } from "../api";

export function Inspector({ memory, graph, history, onEdit, onForget, onRestore, onSelect }: { memory?: Memory; graph: GraphResponse | null; history: VersionHistory | null; onEdit: () => void; onForget: () => void; onRestore: () => void; onSelect: (memory: Memory) => void }) {
  if (!memory) return <aside className="inspector"><div className="empty-state"><strong>Select a memory</strong><span>Its provenance, history, and connections will appear here.</span></div></aside>;
  const score = memory.rank ?? memory.base_importance;
  return <aside className="inspector">
    <div className="inspector-title"><span className={`type-cell type-${memory.type}`}>{memory.type}</span><span className={`state ${memory.is_forgotten ? "forgotten" : ""}`}>{memory.is_forgotten ? "Forgotten" : memory.is_current ? "Current" : "Historical"}</span></div>
    <h2>{memory.content}</h2>
    <div className="inspector-actions">{memory.is_current ? <button onClick={onEdit}>Edit</button> : null}{memory.type === "axiom" ? <span className="immutable-note">Axioms cannot be forgotten</span> : memory.is_forgotten ? <button onClick={onRestore}><RotateCcw size={14}/>Restore</button> : <button className="danger" onClick={onForget}>Forget</button>}</div>
    <section><h3>Rank breakdown</h3><div className="rank-row"><span>Importance</span><i><b style={{width:`${memory.base_importance*100}%`}}/></i><strong>{memory.base_importance.toFixed(2)}</strong></div><div className="rank-row"><span>Connectedness</span><i><b style={{width:`${Math.min(100,(graph?.edges.length ?? 0)*12)}%`}}/></i><strong>{graph?.edges.length ?? 0}</strong></div><div className="total-row"><span>Total score</span><strong>{score.toFixed(2)}</strong></div></section>
    <dl><div><dt>Cadence</dt><dd>{memory.cadence}</dd></div><div><dt>Happened</dt><dd>{new Date(memory.happened_at).toLocaleDateString()}</dd></div><div><dt>Accesses</dt><dd>{memory.access_count}</dd></div><div><dt>Source</dt><dd>{memory.source}</dd></div></dl>
    <section><h3>Source links</h3>{memory.source_links.length ? memory.source_links.map(link => <a className="source-link" key={link.id} href={link.uri}><span>{link.label}</span><ExternalLink size={13}/></a>) : <p className="muted">No source links.</p>}</section>
    <section><h3>Version history</h3><div className="version-list">{history?.versions.map(version => <button key={version.id} onClick={() => onSelect(version)}><i className={version.is_current ? "current" : "historic"}/><span>v{version.version} {version.is_current ? "(current)" : "(historical)"}</span><time>{new Date(version.updated_at).toLocaleDateString()}</time></button>)}</div></section>
    <section><h3>Connected memories ({graph?.nodes.length ?? 0})</h3><div className="connected-list">{graph?.nodes.map(node => <button key={node.id} onClick={() => onSelect(node)}><span>{node.type}</span>{node.content}</button>)}</div></section>
  </aside>;
}
