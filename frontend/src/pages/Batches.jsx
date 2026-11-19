import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Alert, Button, Card, Field, inputClass } from "../ui.jsx";

export function BatchList() {
  const { user } = useAuth();
  const canCreate = user.role === "teacher" || user.role === "admin";
  const canOpen = canCreate;
  const [batches, setBatches] = useState([]);
  const [form, setForm] = useState({ name: "", year: "", branch: "" });
  const [error, setError] = useState("");

  const load = () => api.listBatches().then(setBatches).catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      await api.createBatch({
        name: form.name,
        year: form.year ? Number(form.year) : null,
        branch: form.branch || null,
      });
      setForm({ name: "", year: "", branch: "" });
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {canCreate && (
        <Card title="Create a batch">
          <form onSubmit={submit} className="space-y-3">
            <Field label="Batch name (example: CSE Sem 3)">
              <input required className={inputClass} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Year">
                <input type="number" min={2000} max={2100} className={inputClass} value={form.year} onChange={(e) => setForm({ ...form, year: e.target.value })} />
              </Field>
              <Field label="Branch">
                <input className={inputClass} value={form.branch} onChange={(e) => setForm({ ...form, branch: e.target.value })} />
              </Field>
            </div>
            {error && <Alert>{error}</Alert>}
            <Button type="submit">Create batch</Button>
          </form>
        </Card>
      )}
      <Card title={canCreate ? `Batches (${batches.length})` : "My batches"} className={canCreate ? "" : "md:col-span-2"}>
        {!canCreate && error && <Alert>{error}</Alert>}
        {batches.length === 0 ? (
          <p className="text-sm text-slate-500">No batches yet.</p>
        ) : (
          <ul className="divide-y divide-slate-100 text-sm">
            {batches.map((b) => (
              <li key={b.id} className="py-2">
                {canOpen ? (
                  <Link className="font-medium text-indigo-700 underline" to={`/batches/${b.id}`}>
                    {b.name}
                  </Link>
                ) : (
                  <span className="font-medium text-slate-900">{b.name}</span>
                )}
                <span className="text-slate-500">
                  {b.branch ? ` · ${b.branch}` : ""}
                  {b.year ? ` · ${b.year}` : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

export function BatchDetail() {
  const { id } = useParams();
  const [batch, setBatch] = useState(null);
  const [members, setMembers] = useState([]);
  const [students, setStudents] = useState([]);
  const [picked, setPicked] = useState([]);
  const [error, setError] = useState("");

  const load = () =>
    Promise.all([api.getBatch(id), api.listMembers(id), api.listUsers({ role: "student" })])
      .then(([b, m, s]) => {
        setBatch(b);
        setMembers(m);
        setStudents(s);
      })
      .catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, [id]);

  const memberIds = new Set(members.map((m) => m.id));
  const available = students.filter((s) => !memberIds.has(s.id) && s.is_active);

  async function add() {
    setError("");
    try {
      await api.addMembers(id, picked.map(Number));
      setPicked([]);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function remove(userId) {
    setError("");
    try {
      await api.removeMember(id, userId);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  if (error && !batch) {
    return (
      <div className="space-y-3">
        <Alert>{error}</Alert>
        <Link to="/batches" className="text-indigo-700 underline">
          Back to batches
        </Link>
      </div>
    );
  }
  if (!batch) return <p className="text-slate-500">Loading…</p>;

  return (
    <div className="space-y-4">
      <Link to="/batches" className="text-sm text-indigo-700 underline">
        ← All batches
      </Link>
      <h1 className="text-2xl font-bold text-slate-900">{batch.name}</h1>
      {error && <Alert>{error}</Alert>}
      <div className="grid gap-4 md:grid-cols-2">
        <Card title={`Students in this batch (${members.length})`}>
          {members.length === 0 ? (
            <p className="text-sm text-slate-500">No students yet.</p>
          ) : (
            <ul className="divide-y divide-slate-100 text-sm">
              {members.map((m) => (
                <li key={m.id} className="flex items-center justify-between py-2">
                  <span>
                    {m.name} <span className="text-slate-500">({m.email})</span>
                  </span>
                  <Button variant="danger" onClick={() => remove(m.id)}>
                    Remove
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Add students">
          {available.length === 0 ? (
            <p className="text-sm text-slate-500">No other students to add. Add students in People first.</p>
          ) : (
            <>
              <select multiple aria-label="Students to add" size={Math.min(8, available.length)} className={inputClass} value={picked} onChange={(e) => setPicked([...e.target.selectedOptions].map((o) => o.value))}>
                {available.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.email})
                  </option>
                ))}
              </select>
              <p className="mt-1 text-xs text-slate-500">Hold Ctrl (or Cmd) to pick more than one.</p>
              <Button className="mt-3" disabled={picked.length === 0} onClick={add}>
                Add selected
              </Button>
            </>
          )}
        </Card>
      </div>
    </div>
  );
}
