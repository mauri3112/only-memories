import { Archive, Box, CheckSquare, Folder, Heart, Lightbulb, Shield } from "lucide-react";
import { Memory } from "../api";

const icons = { axiom: Shield, preference: Heart, project: Folder, decision: Lightbulb, task: CheckSquare, artifact: Box };

export function MemoryTable({ memories, selectedId, onSelect }: { memories: Memory[]; selectedId?: string; onSelect: (memory: Memory) => void }) {
  return <div className="table-wrap">
    <div className="table-head"><span>Type</span><span>Memory</span><span>Score</span><span>Updated</span></div>
    <div className="memory-rows">
      {memories.length === 0 ? <div className="empty-state"><Archive size={22}/><strong>No memories in this view</strong><span>Add one below or change the filters.</span></div> : memories.map((memory) => {
        const Icon = icons[memory.type as keyof typeof icons] ?? Archive;
        return <button key={memory.id} className={`memory-row ${selectedId === memory.id ? "selected" : ""}`} onClick={() => onSelect(memory)}>
          <span className={`type-cell type-${memory.type}`}><Icon size={16}/>{memory.type}</span>
          <span className="memory-copy">{memory.content}</span>
          <span className="score">{(memory.rank ?? memory.base_importance).toFixed(2)}</span>
          <time>{new Date(memory.updated_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</time>
        </button>;
      })}
    </div>
  </div>;
}
