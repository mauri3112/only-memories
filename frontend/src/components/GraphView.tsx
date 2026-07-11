import { Maximize2, Minus, Plus } from "lucide-react";
import { GraphResponse, Memory } from "../api";

const positions = [[50,18],[78,32],[79,67],[50,82],[21,67],[21,32],[50,50],[63,50]];
export function GraphView({ graph, selected, onSelect }: { graph: GraphResponse | null; selected?: Memory; onSelect: (memory: Memory) => void }) {
  const nodes = graph?.nodes.slice(0, 6) ?? [];
  return <section className="graph-panel">
    <header><span>Relationship graph</span><span className="graph-tools"><button aria-label="Zoom in"><Plus size={15}/></button><button aria-label="Zoom out"><Minus size={15}/></button><button aria-label="Fit graph"><Maximize2 size={14}/></button></span></header>
    <div className="graph-stage">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden>{nodes.map((node, index) => <line key={node.id} x1="50" y1="50" x2={positions[index][0]} y2={positions[index][1]} />)}</svg>
      {selected ? <button className={`graph-node central type-${selected.type}`} style={{left:"50%",top:"50%"}} onClick={() => onSelect(selected)}><span>{selected.type}</span>{selected.content}</button> : null}
      {nodes.map((node, index) => <button key={node.id} className={`graph-node type-${node.type}`} style={{left:`${positions[index][0]}%`,top:`${positions[index][1]}%`}} onClick={() => onSelect(node)}><span>{node.type}</span>{node.content}</button>)}
      {nodes.map((node, index) => <span key={`label-${node.id}`} className="edge-label" style={{left:`${(positions[index][0]+50)/2}%`,top:`${(positions[index][1]+50)/2}%`}}>{graph?.edges.find(edge => edge.target_id === node.id)?.relation ?? "related"}</span>)}
    </div>
    <footer><span><i className="legend updates"/>updates</span><span><i className="legend supports"/>supports</span><span><i className="legend extends"/>extends</span><span><i className="legend related"/>related</span></footer>
  </section>;
}
