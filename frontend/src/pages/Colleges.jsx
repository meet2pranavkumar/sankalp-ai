import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Alert, Button, Card, Field, inputClass } from "../ui.jsx";

const empty = { name: "", city: "", state: "", code: "" };

export default function Colleges() {
  const [colleges, setColleges] = useState([]);
  const [form, setForm] = useState(empty);
  const [error, setError] = useState("");

  const load = () => api.listColleges().then(setColleges).catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      await api.createCollege({ ...form, city: form.city || null, state: form.state || null });
      setForm(empty);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card title="Add a college">
        <form onSubmit={submit} className="space-y-3">
          <Field label="College name">
            <input required className={inputClass} value={form.name} onChange={set("name")} />
          </Field>
          <Field label="Short code (example: GPR)">
            <input required minLength={2} className={inputClass} value={form.code} onChange={set("code")} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="City">
              <input className={inputClass} value={form.city} onChange={set("city")} />
            </Field>
            <Field label="State">
              <input className={inputClass} value={form.state} onChange={set("state")} />
            </Field>
          </div>
          {error && <Alert>{error}</Alert>}
          <Button type="submit">Add college</Button>
        </form>
      </Card>
      <Card title={`Colleges (${colleges.length})`}>
        {colleges.length === 0 ? (
          <p className="text-sm text-slate-500">No colleges yet.</p>
        ) : (
          <ul className="divide-y divide-slate-100 text-sm">
            {colleges.map((c) => (
              <li key={c.id} className="py-2">
                <span className="font-medium text-slate-900">{c.name}</span>{" "}
                <span className="text-slate-500">
                  ({c.code}
                  {c.city ? `, ${c.city}` : ""})
                </span>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-3 text-xs text-slate-500">
          After adding a college, go to People and create its college admin.
        </p>
      </Card>
    </div>
  );
}
