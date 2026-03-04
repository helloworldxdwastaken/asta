import { useState, useEffect } from "react";
import { listAgents, createAgent, updateAgent, deleteAgent, toggleAgent, getSkills } from "../../lib/api";
import { IconPlus, IconClose, IconSearch, IconEdit, IconTrash, IconCheck, resolveAgentIcon } from "../../lib/icons";

interface Agent {
  id: string; name: string; description?: string; system_prompt?: string;
  icon?: string; avatar?: string; model_override?: string; thinking_level?: string;
  category?: string; skills?: string[]; enabled: boolean; knowledge_path?: string;
}

interface SkillInfo { id: string; name: string; enabled: boolean; }

interface Props { onClose: () => void; onAgentsChange: (a: Agent[]) => void; }

const FILTERS = ["All", "Added", "Not Added"] as const;

const CATEGORIES = [
  "Marketing", "Research", "Engineering", "Data", "Knowledge",
  "Operations", "Sales", "Support", "Design", "General",
];

const THINKING_LEVELS = [
  { value: "", label: "Default" },
  { value: "off", label: "Off" },
  { value: "minimal", label: "Minimal" },
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
  { value: "xhigh", label: "Extra High" },
];

const AGENT_ICONS = [
  "\uD83E\uDD16", "\uD83E\uDDD1\u200D\uD83D\uDCBB", "\uD83D\uDD0D", "\uD83D\uDCCA", "\u270D\uFE0F", "\uD83C\uDFAF", "\uD83D\uDE80", "\uD83E\uDDE0",
  "\uD83D\uDCA1", "\uD83D\uDCDD", "\uD83D\uDCC8", "\uD83D\uDD27", "\uD83C\uDF10", "\uD83D\uDCE7", "\uD83C\uDFA8", "\uD83D\uDEE1\uFE0F",
  "\u2699\uFE0F", "\uD83D\uDCDA", "\uD83D\uDCBC", "\uD83C\uDF1F", "\uD83E\uDD1D", "\uD83D\uDCAC", "\uD83D\uDCC1", "\uD83E\uDDEA",
  "\uD83C\uDFD7\uFE0F", "\uD83D\uDD2C", "\uD83C\uDFB5", "\uD83D\uDCF0", "\uD83D\uDCF1", "\u26A1", "\uD83C\uDF31", "\uD83D\uDCE6",
];

const PROMPT_TEMPLATES = [
  {
    name: "Competitor Analyst", category: "Research", icon: "\uD83D\uDD0D",
    description: "Researches and analyzes competitors",
    prompt: "You are a competitor research analyst. Your job is to research competitors, analyze their strengths and weaknesses, track their product updates, pricing changes, and strategic moves. Provide structured, data-driven reports with actionable insights. Always cite your sources and distinguish between confirmed facts and educated speculation.",
  },
  {
    name: "Code Reviewer", category: "Engineering", icon: "\uD83D\uDD27",
    description: "Reviews code for quality and best practices",
    prompt: "You are an expert code reviewer. Review code for bugs, security vulnerabilities, performance issues, and adherence to best practices. Provide specific, actionable feedback with code examples. Prioritize issues by severity. Be constructive and educational in your feedback, explaining the 'why' behind each suggestion.",
  },
  {
    name: "Research Assistant", category: "Research", icon: "\uD83D\uDCDA",
    description: "Helps research and summarize information",
    prompt: "You are a thorough research assistant. Help gather, analyze, and synthesize information on any topic. Provide well-organized summaries with key findings, supporting evidence, and recommendations for further investigation. Always note the reliability of sources and flag any conflicting information.",
  },
  {
    name: "Data Analyst", category: "Data", icon: "\uD83D\uDCCA",
    description: "Analyzes data and creates insights",
    prompt: "You are a data analyst. Help analyze datasets, identify patterns and trends, create statistical summaries, and generate insights. Write clear, well-commented analysis code. Present findings in a structured format with visualizations when helpful. Always validate data quality and note any limitations in your analysis.",
  },
  {
    name: "Writing Editor", category: "Marketing", icon: "\u270D\uFE0F",
    description: "Edits and improves written content",
    prompt: "You are a skilled writing editor. Help improve clarity, tone, grammar, and structure of written content. Adapt your editing style to the audience and purpose (blog post, email, report, etc.). Preserve the author's voice while enhancing readability. Provide specific suggestions with explanations for major changes.",
  },
];

function AgentForm({
  agent, skills, onSave, onCancel,
}: {
  agent?: Agent; skills: SkillInfo[];
  onSave: (d: Partial<Agent>) => void; onCancel: () => void;
}) {
  const [name, setName] = useState(agent?.name ?? "");
  const [desc, setDesc] = useState(agent?.description ?? "");
  const [prompt, setPrompt] = useState(agent?.system_prompt ?? "");
  const [icon, setIcon] = useState(agent?.icon ?? "");
  const [model, setModel] = useState(agent?.model_override ?? "");
  const [category, setCategory] = useState(agent?.category ?? "");
  const [thinking, setThinking] = useState(agent?.thinking_level ?? "");
  const [avatar, setAvatar] = useState(agent?.avatar ?? "");
  const [selectedSkills, setSelectedSkills] = useState<string[]>(agent?.skills ?? []);
  const [allSkills, setAllSkills] = useState(agent?.skills == null);

  function applyTemplate(t: typeof PROMPT_TEMPLATES[number]) {
    setName(t.name); setDesc(t.description);
    setPrompt(t.prompt); setCategory(t.category);
    setIcon(t.icon);
  }

  function toggleSkill(id: string) {
    setAllSkills(false);
    setSelectedSkills(prev => prev.includes(id) ? prev.filter(s => s !== id) : [...prev, id]);
  }

  return (
    <div className="space-y-4">
      <h3 className="text-15 text-label font-semibold">{agent ? "Edit Agent" : "New Agent"}</h3>

      {/* Prompt templates */}
      {!agent && (
        <div>
          <label className="text-11 text-label-tertiary block mb-1.5">Start from template</label>
          <div className="flex gap-2 flex-wrap">
            {PROMPT_TEMPLATES.map(t => (
              <button key={t.name} onClick={() => applyTemplate(t)}
                className="text-11 bg-white/[.06] hover:bg-white/[.1] text-label-secondary px-2.5 py-1 rounded-lg transition-colors">
                {t.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Identity */}
      <div>
        <label className="text-11 text-label-tertiary block mb-1">Name</label>
        <input autoFocus type="text" value={name} onChange={e => setName(e.target.value)}
          className="w-full bg-white/[.06] border border-separator rounded-mac px-3 py-2 text-13 text-label outline-none focus:border-accent/50" placeholder="Agent name" />
      </div>
      <div>
        <label className="text-11 text-label-tertiary block mb-1">Icon</label>
        <div className="flex flex-wrap gap-1">
          {AGENT_ICONS.map(e => (
            <button key={e} type="button" onClick={() => setIcon(e)}
              className={`w-8 h-8 rounded-lg text-base flex items-center justify-center transition-all duration-150 ${
                icon === e ? "bg-accent/20 border border-accent/40 scale-110" : "bg-white/[.04] hover:bg-white/[.08] border border-transparent"
              }`}>{e}</button>
          ))}
          <input type="text" value={icon} onChange={e => setIcon(e.target.value)} placeholder="or type"
            className="w-16 bg-white/[.04] border border-separator rounded-lg px-2 py-1 text-13 text-label text-center outline-none focus:border-accent/50" />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-11 text-label-tertiary block mb-1">Category</label>
          <select value={category} onChange={e => setCategory(e.target.value)}
            className="w-full bg-white/[.06] border border-separator rounded-mac px-3 py-2 text-13 text-label outline-none focus:border-accent/50">
            <option value="">Select category</option>
            {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label className="text-11 text-label-tertiary block mb-1">Avatar URL (optional)</label>
          <input type="text" value={avatar} onChange={e => setAvatar(e.target.value)} placeholder="https://..."
            className="w-full bg-white/[.06] border border-separator rounded-mac px-3 py-2 text-13 text-label outline-none focus:border-accent/50" />
        </div>
      </div>
      <div>
        <label className="text-11 text-label-tertiary block mb-1">Description</label>
        <input type="text" value={desc} onChange={e => setDesc(e.target.value)} placeholder="Short description"
          className="w-full bg-white/[.06] border border-separator rounded-mac px-3 py-2 text-13 text-label outline-none focus:border-accent/50" />
      </div>
      <div>
        <label className="text-11 text-label-tertiary block mb-1">System Prompt</label>
        <textarea rows={5} value={prompt} onChange={e => setPrompt(e.target.value)} placeholder="You are a helpful assistant..."
          className="w-full bg-white/[.06] border border-separator rounded-mac px-3 py-2 text-13 font-mono text-label outline-none focus:border-accent/50 resize-none" />
      </div>

      {/* Model Overrides */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-11 text-label-tertiary block mb-1">Model Override</label>
          <input type="text" value={model} onChange={e => setModel(e.target.value)} placeholder="Leave blank for default"
            className="w-full bg-white/[.06] border border-separator rounded-mac px-3 py-2 text-13 font-mono text-label outline-none focus:border-accent/50" />
        </div>
        <div>
          <label className="text-11 text-label-tertiary block mb-1">Thinking Level</label>
          <select value={thinking} onChange={e => setThinking(e.target.value)}
            className="w-full bg-white/[.06] border border-separator rounded-mac px-3 py-2 text-13 text-label outline-none focus:border-accent/50">
            {THINKING_LEVELS.map(l => <option key={l.value} value={l.value}>{l.label}</option>)}
          </select>
        </div>
      </div>

      {/* Skills */}
      {skills.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-11 text-label-tertiary">Allowed Skills</label>
            <div className="flex gap-2">
              <button onClick={() => { setAllSkills(true); setSelectedSkills([]); }}
                className="text-[10px] text-accent hover:underline">All</button>
              <button onClick={() => { setAllSkills(false); setSelectedSkills([]); }}
                className="text-[10px] text-label-tertiary hover:underline">Clear</button>
              {!allSkills && <span className="text-[10px] text-label-tertiary">{selectedSkills.length} / {skills.length}</span>}
            </div>
          </div>
          {allSkills ? (
            <p className="text-11 text-label-tertiary bg-white/[.04] rounded-mac px-3 py-2">All skills allowed (no filter)</p>
          ) : (
            <div className="grid grid-cols-2 gap-1.5 max-h-32 overflow-y-auto">
              {skills.map(s => (
                <label key={s.id} className="flex items-center gap-2 px-2 py-1 rounded hover:bg-white/[.04] cursor-pointer">
                  <span className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 transition-colors ${
                    selectedSkills.includes(s.id) ? "bg-accent border-accent" : "border-separator"
                  }`} onClick={() => toggleSkill(s.id)}>
                    {selectedSkills.includes(s.id) && <IconCheck size={10} className="text-white" />}
                  </span>
                  <span className="text-12 text-label truncate" onClick={() => toggleSkill(s.id)}>{s.name}</span>
                </label>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="flex gap-2 justify-end pt-1">
        <button onClick={onCancel} className="px-4 py-2 text-13 text-label-secondary hover:text-label">Cancel</button>
        <button onClick={() => onSave({
          name, description: desc, system_prompt: prompt, icon, avatar: avatar || undefined,
          model_override: model || undefined, category, thinking_level: thinking || undefined,
          skills: allSkills ? undefined : (selectedSkills.length > 0 ? selectedSkills : undefined),
        })}
          disabled={!name.trim()} className="px-5 py-2 text-13 bg-accent hover:bg-accent-hover disabled:opacity-40 text-white rounded-mac transition-colors">
          {agent ? "Save" : "Create"}
        </button>
      </div>
    </div>
  );
}

export default function AgentsSheet({ onClose, onAgentsChange }: Props) {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<typeof FILTERS[number]>("All");
  const [selectedCat, setSelectedCat] = useState<string | null>(null);
  const [editing, setEditing] = useState<Agent | "new" | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  async function load() {
    const r = await listAgents().catch(() => ({ agents: [] }));
    const list = r.agents ?? [];
    setAgents(list);
    onAgentsChange(list);
  }
  useEffect(() => {
    load();
    getSkills().then(r => setSkills(r.skills ?? [])).catch(()=>{});
  }, []);

  async function handleSave(data: Partial<Agent>) {
    if (editing === "new") await createAgent(data);
    else if (editing) await updateAgent(editing.id, data);
    setEditing(null); load();
  }

  async function handleToggle(id: string) {
    await toggleAgent(id);
    setAgents(prev => {
      const next = prev.map(a => a.id === id ? { ...a, enabled: !a.enabled } : a);
      onAgentsChange(next);
      return next;
    });
  }

  async function handleDelete(id: string) {
    await deleteAgent(id);
    setConfirmDelete(null); load();
  }

  // Category tabs from agents
  const categories = [...new Set(agents.map(a => a.category).filter(Boolean))] as string[];

  const filtered = agents.filter(a => {
    if (filter === "Added" && !a.enabled) return false;
    if (filter === "Not Added" && a.enabled) return false;
    if (selectedCat && a.category !== selectedCat) return false;
    if (search && !a.name.toLowerCase().includes(search.toLowerCase()) &&
        !(a.description ?? "").toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="absolute inset-0 bg-black/60 flex items-center justify-center z-40 animate-fade-in" onClick={onClose}>
      <div className="bg-surface-raised rounded-2xl shadow-2xl border border-separator flex flex-col overflow-hidden animate-scale-in" style={{ width: 780, maxHeight: "85vh" }} onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="px-6 py-4 border-b border-separator shrink-0">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-16 text-label font-semibold">Agents</h2>
              <p className="text-11 text-label-tertiary mt-0.5">Specialist AIs with their own personality and expertise</p>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => setEditing("new")}
                className="text-12 bg-accent hover:bg-accent-hover text-white px-3.5 py-1.5 rounded-lg flex items-center gap-1.5 transition-colors font-medium">
                <IconPlus size={12} /> New Agent
              </button>
              <button onClick={onClose} className="w-8 h-8 flex items-center justify-center rounded-lg text-label-tertiary hover:text-label hover:bg-white/[.06] transition-colors"><IconClose size={14} /></button>
            </div>
          </div>
        </div>

        {/* Search + filter */}
        {!editing && (
          <div className="flex items-center gap-3 px-6 py-2.5 border-b border-separator shrink-0">
            <div className="flex-1 relative">
              <IconSearch size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-label-tertiary" />
              <input type="text" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search agents..."
                className="w-full bg-white/[.04] border border-separator rounded-xl pl-8 pr-3 py-1.5 text-13 text-label placeholder-label-tertiary outline-none focus:border-accent/40 transition-colors" />
            </div>
            <div className="flex bg-white/[.04] rounded-xl p-0.5">
              {FILTERS.map(f => (
                <button key={f} onClick={() => setFilter(f)}
                  className={`px-3 py-1 rounded-lg text-12 font-medium transition-all duration-200 ${filter === f ? "bg-white/[.1] text-label shadow-sm" : "text-label-tertiary hover:text-label-secondary"}`}>
                  {f}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Category tabs */}
        {categories.length > 0 && !editing && (
          <div className="flex items-center gap-1.5 px-6 py-2 border-b border-separator overflow-x-auto scrollbar-thin shrink-0">
            <button onClick={() => setSelectedCat(null)}
              className={`text-11 px-3 py-1 rounded-full shrink-0 transition-all duration-200 ${!selectedCat ? "bg-accent/15 text-accent font-medium" : "text-label-tertiary hover:text-label-secondary hover:bg-white/[.04]"}`}>
              All
            </button>
            {categories.map(c => (
              <button key={c} onClick={() => setSelectedCat(selectedCat === c ? null : c)}
                className={`text-11 px-3 py-1 rounded-full shrink-0 transition-all duration-200 ${selectedCat === c ? "bg-accent/15 text-accent font-medium" : "text-label-tertiary hover:text-label-secondary hover:bg-white/[.04]"}`}>
                {c}
              </button>
            ))}
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5 scrollbar-thin">
          {editing ? (
            <AgentForm agent={editing === "new" ? undefined : editing} skills={skills} onSave={handleSave} onCancel={() => setEditing(null)} />
          ) : (
            <div className="grid grid-cols-2 gap-3">
              {filtered.map(a => (
                <div key={a.id}
                  className="bg-white/[.03] hover:bg-white/[.06] border border-separator hover:border-separator-bold rounded-2xl p-4 group transition-all duration-200">
                  <div className="flex items-start gap-3">
                    {/* Avatar */}
                    {(() => {
                      const ai = resolveAgentIcon(a);
                      return (
                        <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 overflow-hidden"
                          style={{ background: ai.bg, color: ai.color }}>
                          {a.avatar ? (
                            <img src={a.avatar} alt="" className="w-full h-full object-cover" />
                          ) : (
                            <ai.Icon size={20} />
                          )}
                        </div>
                      );
                    })()}
                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-13 font-semibold text-label truncate">{a.name}</p>
                        <button onClick={() => handleToggle(a.id)}
                          className={`relative w-9 rounded-full transition-colors shrink-0 ${a.enabled ? "bg-accent" : "bg-white/[.15]"}`}
                          style={{ height: 22 }}>
                          <span className="absolute w-4 h-4 bg-white rounded-full shadow-sm transition-all duration-200"
                            style={{ top: 3, left: a.enabled ? 18 : 3 }} />
                        </button>
                      </div>
                      {a.description && <p className="text-11 text-label-tertiary line-clamp-2 mt-0.5 leading-relaxed">{a.description}</p>}
                    </div>
                  </div>
                  {/* Footer: badges + actions */}
                  <div className="flex items-center justify-between mt-3 pt-2.5 border-t border-separator/50">
                    <div className="flex gap-1.5 flex-wrap">
                      {a.category && (
                        <span className="text-[10px] font-semibold bg-accent/10 text-accent px-2 py-0.5 rounded-full">{a.category}</span>
                      )}
                      {a.model_override && (
                        <span className="text-[10px] font-medium bg-white/[.06] text-label-tertiary px-2 py-0.5 rounded-full font-mono">{a.model_override}</span>
                      )}
                      {a.skills && a.skills.length > 0 && (
                        <span className="text-[10px] bg-white/[.06] text-label-tertiary px-2 py-0.5 rounded-full">
                          {a.skills.length} skill{a.skills.length !== 1 ? "s" : ""}
                        </span>
                      )}
                    </div>
                    <div className="flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button onClick={() => setEditing(a)} className="text-label-tertiary hover:text-label p-1.5 rounded-lg hover:bg-white/[.06] transition-colors"><IconEdit size={12} /></button>
                      <button onClick={() => setConfirmDelete(a.id)} className="text-label-tertiary hover:text-danger p-1.5 rounded-lg hover:bg-danger/10 transition-colors"><IconTrash size={12} /></button>
                    </div>
                  </div>
                </div>
              ))}
              {filtered.length === 0 && (
                <div className="col-span-2 flex flex-col items-center justify-center py-16">
                  <div className="w-12 h-12 rounded-2xl bg-white/[.04] flex items-center justify-center text-2xl mb-3">
                    {search ? "?" : agents.length === 0 ? "+" : "~"}
                  </div>
                  <p className="text-label-secondary text-14 font-medium">
                    {search ? "No agents match your search" : agents.length === 0 ? "No agents yet" : "No agents in this filter"}
                  </p>
                  <p className="text-label-tertiary text-12 mt-1">
                    {agents.length === 0 ? "Create specialist AIs to help with specific tasks" : "Try adjusting your filters"}
                  </p>
                  {agents.length === 0 && (
                    <button onClick={() => setEditing("new")}
                      className="text-12 text-accent hover:text-accent-hover mt-3 font-medium transition-colors">
                      Create your first agent
                    </button>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Delete confirmation */}
      {confirmDelete && (
        <div className="absolute inset-0 bg-black/60 flex items-center justify-center z-50 animate-fade-in" onClick={() => setConfirmDelete(null)}>
          <div className="bg-surface-raised rounded-2xl p-6 w-80 shadow-2xl border border-separator animate-scale-in" onClick={e => e.stopPropagation()}>
            <h3 className="text-label text-15 font-semibold mb-2">Delete Agent</h3>
            <p className="text-13 text-label-secondary mb-5 leading-relaxed">
              Are you sure? This action cannot be undone.
            </p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setConfirmDelete(null)}
                className="px-4 py-2 text-13 text-label-secondary hover:text-label rounded-lg hover:bg-white/[.04] transition-colors">Cancel</button>
              <button onClick={() => handleDelete(confirmDelete)}
                className="px-4 py-2 text-13 bg-danger/15 text-danger hover:bg-danger/25 rounded-lg font-medium transition-colors">Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
