import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Alert, Button, Card, Field, inputClass } from "../ui.jsx";

const blankTest = (hidden = false) => ({ input: "", expected_output: "", is_hidden: hidden });

export function parseTags(text) {
  return text
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);
}

export default function ProblemEditor() {
  const { id } = useParams(); // no id = creating a new problem
  const editing = Boolean(id);
  const { user } = useAuth();
  const navigate = useNavigate();
  const isSuper = user.role === "super_admin";

  const [loaded, setLoaded] = useState(!editing);
  const [form, setForm] = useState({
    title: "",
    statement_md: "## Task\n\n\n## Input\n\n\n## Output\n\n",
    difficulty: "easy",
    tags: "",
    time_limit_ms: 1000,
    memory_limit_mb: 256,
    is_public: false,
  });
  const [tests, setTests] = useState([blankTest(false), blankTest(true)]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!editing) return;
    api
      .getProblem(id)
      .then((p) => {
        if (!p.can_edit) {
          setError("You are not allowed to edit this problem.");
          return;
        }
        setForm({
          title: p.title,
          statement_md: p.statement_md,
          difficulty: p.difficulty,
          tags: p.tags.join(", "),
          time_limit_ms: p.time_limit_ms,
          memory_limit_mb: p.memory_limit_mb,
          is_public: p.is_public,
        });
        setTests(p.test_cases.map((t) => ({ input: t.input, expected_output: t.expected_output, is_hidden: t.is_hidden })));
        setLoaded(true);
      })
      .catch((e) => setError(e.message));
  }, [editing, id]);

  const setF = (key) => (e) => setForm({ ...form, [key]: e.target.value });
  const setTest = (index, patch) => setTests(tests.map((t, i) => (i === index ? { ...t, ...patch } : t)));

  async function save(e) {
    e.preventDefault();
    setError("");
    setSaving(true);
    const body = {
      title: form.title,
      statement_md: form.statement_md,
      difficulty: form.difficulty,
      tags: parseTags(form.tags),
      time_limit_ms: Number(form.time_limit_ms),
      memory_limit_mb: Number(form.memory_limit_mb),
      is_public: isSuper ? form.is_public : false, // only the platform owner can share problems
      test_cases: tests,
    };
    try {
      const saved = editing ? await api.updateProblem(id, body) : await api.createProblem(body);
      navigate(`/problems/${saved.id}`);
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
        <Link to="/problems" className="text-indigo-700 underline">
          Back to problems
        </Link>
      </div>
    ) : (
      <p className="text-slate-500">Loading…</p>
    );
  }

  return (
    <form onSubmit={save} className="space-y-4">
      <h1 className="text-2xl font-bold text-slate-900">{editing ? "Edit problem" : "New problem"}</h1>
      <Card title="Problem">
        <div className="space-y-3">
          <Field label="Title">
            <input required className={inputClass} value={form.title} onChange={setF("title")} />
          </Field>
          <Field label="Statement (you can use Markdown)">
            <textarea required rows={10} className={`${inputClass} font-mono`} value={form.statement_md} onChange={setF("statement_md")} />
          </Field>
          <div className="grid gap-3 md:grid-cols-4">
            <Field label="Level">
              <select className={inputClass} value={form.difficulty} onChange={setF("difficulty")}>
                <option value="easy">Easy</option>
                <option value="medium">Medium</option>
                <option value="hard">Hard</option>
              </select>
            </Field>
            <Field label="Topics (comma separated)">
              <input className={inputClass} placeholder="arrays, loops" value={form.tags} onChange={setF("tags")} />
            </Field>
            <Field label="Time limit (ms)">
              <input type="number" min={100} max={10000} className={inputClass} value={form.time_limit_ms} onChange={setF("time_limit_ms")} />
            </Field>
            <Field label="Memory limit (MB)">
              <input type="number" min={16} max={512} className={inputClass} value={form.memory_limit_mb} onChange={setF("memory_limit_mb")} />
            </Field>
          </div>
          {isSuper && (
            <p className="text-xs text-slate-500">Problems made by the platform owner are shared with every college.</p>
          )}
        </div>
      </Card>

      <Card title={`Test cases (${tests.length})`}>
        <p className="mb-3 text-sm text-slate-600">
          Sample tests are shown to students. Hidden tests are used only for marking and are never sent to students.
          You need at least one sample test.
        </p>
        <div className="space-y-3">
          {tests.map((t, i) => (
            <div key={i} className="rounded border border-slate-200 p-3">
              <div className="mb-2 flex items-center justify-between text-sm">
                <span className="font-medium">Test {i + 1}</span>
                <span className="flex items-center gap-4">
                  <label className="flex items-center gap-1">
                    <input type="checkbox" checked={t.is_hidden} onChange={(e) => setTest(i, { is_hidden: e.target.checked })} />
                    Hidden
                  </label>
                  {tests.length > 1 && (
                    <button type="button" className="text-red-700 underline" onClick={() => setTests(tests.filter((_, j) => j !== i))}>
                      Remove
                    </button>
                  )}
                </span>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <Field label={`Input for test ${i + 1}`}>
                  <textarea rows={3} className={`${inputClass} font-mono`} value={t.input} onChange={(e) => setTest(i, { input: e.target.value })} />
                </Field>
                <Field label={`Expected output for test ${i + 1}`}>
                  <textarea required rows={3} className={`${inputClass} font-mono`} value={t.expected_output} onChange={(e) => setTest(i, { expected_output: e.target.value })} />
                </Field>
              </div>
            </div>
          ))}
        </div>
        <div className="mt-3 flex gap-3">
          <Button type="button" variant="secondary" onClick={() => setTests([...tests, blankTest(false)])}>
            Add sample test
          </Button>
          <Button type="button" variant="secondary" onClick={() => setTests([...tests, blankTest(true)])}>
            Add hidden test
          </Button>
        </div>
      </Card>

      {error && <Alert>{error}</Alert>}
      <div className="flex gap-3">
        <Button type="submit" disabled={saving}>
          {saving ? "Saving…" : "Save problem"}
        </Button>
        <Link to="/problems" className="rounded border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
          Cancel
        </Link>
      </div>
    </form>
  );
}
