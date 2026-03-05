import { useState, useEffect } from "react";
import { listUsers, createUser, deleteUser, resetUserPassword } from "../../../lib/api";
import { IconTrash } from "../../../lib/icons";

interface UserRow {
  id: string;
  username: string;
  role: string;
  created_at: string;
}

export default function TabUsers() {
  const [users, setUsers] = useState<UserRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newUser, setNewUser] = useState("");
  const [newPass, setNewPass] = useState("");
  const [newRole, setNewRole] = useState("user");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [resetId, setResetId] = useState<string | null>(null);
  const [resetPass, setResetPass] = useState("");

  async function refresh() {
    try {
      const r = await listUsers();
      setUsers(r.users ?? []);
    } catch {}
    setLoading(false);
  }

  useEffect(() => { refresh(); }, []);

  async function handleCreate() {
    if (!newUser.trim() || !newPass) return;
    setCreating(true);
    setError("");
    try {
      await createUser(newUser.trim(), newPass, newRole);
      setNewUser(""); setNewPass(""); setNewRole("user");
      setShowCreate(false);
      refresh();
    } catch (err: any) {
      setError(err?.message?.includes("409") ? "Username already exists" : "Failed to create user");
    }
    setCreating(false);
  }

  async function handleDelete(id: string, username: string) {
    if (!confirm(`Delete user "${username}"? Their data will remain but they won't be able to log in.`)) return;
    await deleteUser(id).catch(() => {});
    refresh();
  }

  async function handleReset(id: string) {
    if (!resetPass) return;
    await resetUserPassword(id, resetPass).catch(() => {});
    setResetId(null);
    setResetPass("");
  }

  return (
    <div className="text-label space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="text-15 font-semibold">Users</h2>
        <button onClick={() => setShowCreate(!showCreate)}
          className="bg-white/[.06] hover:bg-white/[.10] text-label text-13 rounded-mac px-4 py-2 border border-separator transition-colors">
          {showCreate ? "Cancel" : "Add user"}
        </button>
      </div>

      {showCreate && (
        <div className="bg-white/[.04] rounded-mac p-4 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <input autoFocus value={newUser} onChange={e => setNewUser(e.target.value)}
              placeholder="Username"
              className="bg-white/[.04] border border-separator rounded-mac px-3.5 py-2.5 text-13 text-label outline-none focus:border-accent/50 transition-colors" />
            <input type="password" value={newPass} onChange={e => setNewPass(e.target.value)}
              placeholder="Password"
              className="bg-white/[.04] border border-separator rounded-mac px-3.5 py-2.5 text-13 text-label outline-none focus:border-accent/50 transition-colors" />
          </div>
          <div className="flex items-center gap-3">
            <select value={newRole} onChange={e => setNewRole(e.target.value)}
              className="bg-white/[.04] border border-separator rounded-mac px-3 py-2 text-13 text-label outline-none">
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
            <button onClick={handleCreate} disabled={creating || !newUser.trim() || !newPass}
              className="accent-gradient text-white text-13 rounded-mac px-5 py-2 font-medium disabled:opacity-40 transition-all hover:opacity-90">
              {creating ? "Creating..." : "Create"}
            </button>
          </div>
          {error && <p className="text-13 text-danger">{error}</p>}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-8">
          <div className="w-5 h-5 border-2 border-accent/40 border-t-accent rounded-full animate-spin" />
        </div>
      ) : users.length === 0 ? (
        <p className="text-13 text-label-tertiary text-center py-8">No users created yet. Running in single-user mode.</p>
      ) : (
        <div className="space-y-1">
          {users.map(u => (
            <div key={u.id} className="flex items-center justify-between bg-white/[.04] rounded-mac px-4 py-3">
              <div className="flex items-center gap-3">
                <span className="text-13 font-medium text-label">{u.username}</span>
                <span className={`text-[10px] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded-full ${
                  u.role === "admin" ? "bg-accent/20 text-accent" : "bg-white/[.08] text-label-tertiary"
                }`}>{u.role}</span>
              </div>
              <div className="flex items-center gap-1.5">
                {resetId === u.id ? (
                  <div className="flex items-center gap-1.5">
                    <input type="password" value={resetPass} onChange={e => setResetPass(e.target.value)}
                      placeholder="New password" autoFocus
                      onKeyDown={e => { if (e.key === "Enter") handleReset(u.id); if (e.key === "Escape") setResetId(null); }}
                      className="bg-white/[.04] border border-separator rounded-mac px-2.5 py-1.5 text-12 text-label outline-none focus:border-accent/50 w-36" />
                    <button onClick={() => handleReset(u.id)} disabled={!resetPass}
                      className="text-12 text-accent hover:text-accent-hover disabled:opacity-40">Save</button>
                    <button onClick={() => setResetId(null)} className="text-12 text-label-tertiary">Cancel</button>
                  </div>
                ) : (
                  <button onClick={() => { setResetId(u.id); setResetPass(""); }}
                    className="text-12 text-label-tertiary hover:text-label-secondary transition-colors">
                    Reset password
                  </button>
                )}
                <button onClick={() => handleDelete(u.id, u.username)}
                  className="w-7 h-7 flex items-center justify-center rounded-mac hover:bg-danger/10 text-label-tertiary hover:text-danger transition-colors"
                  title="Delete user">
                  <IconTrash size={12} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
