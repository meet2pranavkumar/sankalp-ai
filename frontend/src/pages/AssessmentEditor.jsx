import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import { fromLocalInput, toLocalInput } from "../time.js";
import { Alert, Button, Card, Field, inputClass } from "../ui.jsx";

export function moveItem(items, index, direction) {
  const target = index + direction;
  if (target < 0 || target >= items.length) return items;
  const copy = [...items];
  [copy[index], copy[target]] = [copy[target], copy[index]];
  return copy;
}

const inHours = (hours) => toLocalInput(new Date(Date.now() + hours * 3600_000).toISOString());

export default function AssessmentEditor() {
  const { id } = useParams(); // no id = a new assessment
  const editing = Boolean(id);
  const navigate = useNavigate();

  const [loaded, setLoaded] = useState(!editing);
  const [batches, setBatches] = useState([]);
  const [pool, setPool] = useState([]);
  const [search, setSearch] = useState("");
  const [locked, setLocked] = useState(false);
  const [form, setForm] = useState({
    batch_id: "", type: "exam", title: "", description: "",
    starts: inHours(1), ends: inHours(3), duration: 60,
  });
  const [picked, setPicked] = useState([]); // [{problem_id, title, marks}]
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.listBatches().then(setBatches).catch((e) => setError(e.message));
    api.listProblems().then(setPool).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!editing) return;
    api
      .getAssessment(id)
      .then((a) => {
        if (!a.can_manage) {
          setError("You are not allowed to edit this assessment.");
          return;
        }
        setForm({
          batch_id: String(a.batch_id), type: a.type, title: a.title, description: a.description,
          starts: toLocalInput(a.starts_at), ends: toLocalInput(a.ends_at), duration: a.duration_min ?? 60,
        });
        setPicked(a.problems.map((p) => ({ problem_id: p.problem_id, title: p.title, marks: p.marks })));
        setLocked(a.has_activity);
        setLoaded(true);
      })
      .catch((e) => setError(e.message));
  }, [editing, id]);

  const setF = (key) => (e) => setForm({ ...form, [key]: e.target.value });
  const pickedIds = useMemo(() => new Set(picked.map((p) => p.problem_id)), [picked]);
  const shown = pool.filter((p) => p.title.toLowerCase().includes(search.trim().toLowerCase()));
  const total = picked.reduce((sum, p) => sum + (Number(p.marks) || 0), 0);

  const toggle = (problem) =>
    setPicked(
      pickedIds.has(problem.id)
        ? picked.filter((p) => p.problem_id !== problem.id)
        : [...picked, { problem_id: problem.id, title: problem.title, marks: 10 }]
    );

  async function save(e) {
    e.preventDefault();
    setError("");
    if (picked.length === 0) {
      setError("Pick at least one problem.");
      return;
    }
    setSaving(true);
    const problems = picked.map((p) => ({ problem_id: p.problem_id, marks: Number(p.marks) }));
    const shared = {
      title: form.title,
      description: form.description,
      starts_at: fromLocalInput(form.starts),
      ends_at: fromLocalInput(form.ends),
      duration_min: form.type === "exam" ? Number(form.duration) : null,
    };
    try {
      let saved;
      if (editing) {
        saved = await api.updateAssessment(id, locked ? shared : { ...shared, problems });
      } else {
        saved = await api.createAssessment({ ...shared, batch_id: Number(form.batch_id), type: form.type, problems });
      }
      navigate(`/assessments/${saved.id}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  if (!loaded) {
    return error ? (
      <div className="space-y-3">
        <Alert>{error}</Alert>
        <Link to="/assessments" className="text-indigo-700 underline">
          Back to assessments
        </Link>
      </div>
    ) : (
      <p className="text-slate-500">Loading…</p>
    );
  }

  return (
    <form onSubmit={save} className="space-y-4">
      <h1 className="text-2xl font-bold text-slate-900">{editing ? "Edit assessment" : "New assessment"}</h1>

      <Card title="Details">
        <div className="space-y-3">
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="Batch">
              <select required disabled={editing} className={inputClass} value={form.batch_id} onChange={setF("batch_id")}>
                <option value="">Choose a batch…</option>
                {batches.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Type">
              <select disabled={editing} className={inputClass} value={form.type} onChange={setF("type")}>
                <option value="exam">Exam (each student gets a timer)</option>
                <option value="assignment">Assignment (open for days)</option>
              </select>
            </Field>
          </div>
          <Field label="Title">
            <input required className={inputClass} value={form.title} onChange={setF("title")} />
          </Field>
          <Field label="Instructions for students (optional)">
            <textarea rows={3} className={inputClass} value={form.description} onChange={setF("description")} />
          </Field>
          <div className="grid gap-3 md:grid-cols-3">
            <Field label="Opens at">
              <input type="datetime-local" required className={inputClass} value={form.starts} onChange={setF("starts")} />
            </Field>
            <Field label="Closes at">
              <input type="datetime-local" required className={inputClass} value={form.ends} onChange={setF("ends")} />
            </Field>
            {form.type === "exam" && (
              <Field label="Minutes for each student">
                <input type="number" min={5} max={600} required className={inputClass} value={form.duration} onChange={setF("duration")} />
              </Field>
            )}
          </div>
          <p className="text-xs text-slate-500">
            {form.type === "exam"
              ? "Students can press Start any time between opening and closing. The timer never runs past the closing time."
              : "Students can send answers any time between opening and closing."}{" "}
            Times are in your own time zone.
          </p>
        </div>
      </Card>

      <Card title={`Problems (${picked.length}) · ${total} marks in total`}>
        {locked && <p className="mb-3 text-sm text-amber-800">Students have already started, so the problems cannot be changed.</p>}
        {picked.length > 0 && (
          <ol className="mb-4 space-y-2">
            {picked.map((p, i) => (
              <li key={p.problem_id} className="flex flex-wrap items-center gap-2 rounded border border-slate-200 p-2 text-sm">
                <span className="font-medium">{p.title}</span>
                <span className="ml-auto flex items-center gap-2">
                  <label className="flex items-center gap-1 text-slate-600">
                    Marks
                    <input
                      aria-label={`Marks for ${p.title}`}
                      type="number" min={1} step="any" disabled={locked}
                      className="w-20 rounded border border-slate-300 px-2 py-1"
                      value={p.marks}
                      onChange={(e) => setPicked(picked.map((x, j) => (j === i ? { ...x, marks: e.target.value } : x)))}
                    />
                  </label>
                  {!locked && (
                    <>
                      <button type="button" aria-label={`Move ${p.title} up`} disabled={i === 0} onClick={() => setPicked(moveItem(picked, i, -1))} className="rounded border border-slate-300 px-2 disabled:opacity-30">↑</button>
                      <button type="button" aria-label={`Move ${p.title} down`} disabled={i === picked.length - 1} onClick={() => setPicked(moveItem(picked, i, 1))} className="rounded border border-slate-300 px-2 disabled:opacity-30">↓</button>
                      <button type="button" aria-label={`Remove ${p.title}`} onClick={() => setPicked(picked.filter((x) => x.problem_id !== p.problem_id))} className="text-red-700 underline">Remove</button>
                    </>
                  )}
                </span>
              </li>
            ))}
          </ol>
        )}
        {!locked && (
          <>
            <input aria-label="Search problems" placeholder="Search problems by title" className={`${inputClass} mb-2 !w-72`} value={search} onChange={(e) => setSearch(e.target.value)} />
            <ul className="max-h-64 divide-y divide-slate-100 overflow-auto rounded border border-slate-200 text-sm">
              {shown.map((p) => (
                <li key={p.id}>
                  <label className="flex cursor-pointer items-center gap-2 px-2 py-1.5 hover:bg-slate-50">
                    <input type="checkbox" checked={pickedIds.has(p.id)} onChange={() => toggle(p)} aria-label={`Use ${p.title}`} />
                    <span>{p.title}</span>
                    <span className="ml-auto text-xs uppercase text-slate-500">{p.difficulty}</span>
                  </label>
                </li>
              ))}
              {shown.length === 0 && <li className="px-2 py-2 text-slate-500">No problems found.</li>}
            </ul>
            <p className="mt-1 text-xs text-slate-500">
              Problems used in an exam are hidden from students until the exam window is over.
            </p>
          </>
        )}
      </Card>

      {error && <Alert>{error}</Alert>}
      <div className="flex gap-3">
        <Button type="submit" disabled={saving}>
          {saving ? "Saving…" : editing ? "Save changes" : "Create (as a draft)"}
        </Button>
        <Link to={editing ? `/assessments/${id}` : "/assessments"} className="rounded border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
          Cancel
        </Link>
      </div>
    </form>
  );
}
