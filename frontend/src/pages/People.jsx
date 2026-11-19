import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Alert, Button, Card, Field, inputClass, roleLabel } from "../ui.jsx";

const ROLES_BY_ACTOR = {
  super_admin: ["admin", "teacher", "student"],
  admin: ["teacher", "student"],
  teacher: ["student"],
};

// "Name, email" per line  ->  [{name, email}]
export function parseStudentLines(text) {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const parts = line.split(/[,\t]/).map((p) => p.trim());
      return { name: parts[0], email: parts[1] || "" };
    });
}

export default function People() {
  const { user: me } = useAuth();
  const isSuper = me.role === "super_admin";
  const canDisable = me.role === "admin" || isSuper;
  const roles = ROLES_BY_ACTOR[me.role];

  const [colleges, setColleges] = useState([]);
  const [batches, setBatches] = useState([]);
  const [people, setPeople] = useState([]);
  const [filterRole, setFilterRole] = useState("");
  const [filterCollege, setFilterCollege] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState(null);

  const [form, setForm] = useState({ name: "", email: "", password: "", role: roles[0], college_id: "", batch_id: "" });
  const [bulkText, setBulkText] = useState("");
  const [bulkBatch, setBulkBatch] = useState("");
  const [bulkCollege, setBulkCollege] = useState("");
  const [bulkResult, setBulkResult] = useState(null);

  const loadPeople = useCallback(() => {
    api
      .listUsers({ role: me.role === "teacher" ? "" : filterRole, college_id: isSuper ? filterCollege : "" })
      .then(setPeople)
      .catch((e) => setError(e.message));
  }, [filterRole, filterCollege, me.role, isSuper]);

  useEffect(loadPeople, [loadPeople]);
  useEffect(() => {
    if (isSuper) api.listColleges().then(setColleges).catch(() => {});
    else api.listBatches().then(setBatches).catch(() => {});
  }, [isSuper]);

  const setF = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  async function addPerson(e) {
    e.preventDefault();
    setError("");
    setNotice(null);
    try {
      await api.createUser({
        name: form.name,
        email: form.email,
        password: form.password,
        role: form.role,
        college_id: isSuper ? Number(form.college_id) || null : null,
        batch_id: form.role === "student" && form.batch_id ? Number(form.batch_id) : null,
      });
      setForm({ ...form, name: "", email: "", password: "" });
      setNotice({ kind: "ok", text: `${form.name} was added. Share the password with them safely.` });
      loadPeople();
    } catch (err) {
      setError(err.message);
    }
  }

  async function addBulk(e) {
    e.preventDefault();
    setError("");
    setBulkResult(null);
    const students = parseStudentLines(bulkText);
    if (students.some((s) => !s.email)) {
      setError("Every line needs a name and an email, like: Ravi Kumar, ravi@example.com");
      return;
    }
    try {
      const result = await api.bulkCreate({
        students,
        batch_id: bulkBatch ? Number(bulkBatch) : null,
        college_id: isSuper ? Number(bulkCollege) || null : null,
      });
      setBulkResult(result);
      setBulkText("");
      loadPeople();
    } catch (err) {
      setError(err.message);
    }
  }

  async function resetPassword(person) {
    setError("");
    setNotice(null);
    try {
      const { temp_password } = await api.resetPassword(person.id);
      setNotice({ kind: "ok", text: `New password for ${person.name}: ${temp_password} (shown only once)` });
    } catch (err) {
      setError(err.message);
    }
  }

  async function toggleActive(person) {
    setError("");
    try {
      await api.updateUser(person.id, { is_active: !person.is_active });
      loadPeople();
    } catch (err) {
      setError(err.message);
    }
  }

  const canManage = (p) => p.id !== me.id && (roles || []).includes(p.role);
  const created = bulkResult?.filter((r) => r.temp_password) ?? [];
  const copyText = created.map((r) => `${r.name}, ${r.email}, ${r.temp_password}`).join("\n");

  return (
    <div className="space-y-4">
      {error && <Alert>{error}</Alert>}
      {notice && <Alert kind={notice.kind}>{notice.text}</Alert>}

      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Add one person">
          <form onSubmit={addPerson} className="space-y-3">
            <Field label="Full name">
              <input required className={inputClass} value={form.name} onChange={setF("name")} />
            </Field>
            <Field label="Email">
              <input type="email" required className={inputClass} value={form.email} onChange={setF("email")} />
            </Field>
            <Field label="Password (at least 8 characters)">
              <input required minLength={8} className={inputClass} value={form.password} onChange={setF("password")} />
            </Field>
            <Field label="Role">
              <select className={inputClass} value={form.role} onChange={setF("role")}>
                {roles.map((r) => (
                  <option key={r} value={r}>
                    {roleLabel[r]}
                  </option>
                ))}
              </select>
            </Field>
            {isSuper && (
              <Field label="College">
                <select required className={inputClass} value={form.college_id} onChange={setF("college_id")}>
                  <option value="">Choose a college…</option>
                  {colleges.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            {!isSuper && form.role === "student" && (
              <Field label="Add to batch (optional)">
                <select className={inputClass} value={form.batch_id} onChange={setF("batch_id")}>
                  <option value="">No batch</option>
                  {batches.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            <Button type="submit">Add person</Button>
          </form>
        </Card>

        <Card title="Add many students at once">
          <form onSubmit={addBulk} className="space-y-3">
            <Field label="One student per line: name, email">
              <textarea
                rows={6}
                className={inputClass}
                placeholder={"Ravi Kumar, ravi@example.com\nAnita Singh, anita@example.com"}
                value={bulkText}
                onChange={(e) => setBulkText(e.target.value)}
              />
            </Field>
            {isSuper ? (
              <Field label="College">
                <select required className={inputClass} value={bulkCollege} onChange={(e) => setBulkCollege(e.target.value)}>
                  <option value="">Choose a college…</option>
                  {colleges.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </Field>
            ) : (
              <Field label="Add to batch (optional)">
                <select className={inputClass} value={bulkBatch} onChange={(e) => setBulkBatch(e.target.value)}>
                  <option value="">No batch</option>
                  {batches.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            <Button type="submit" disabled={!bulkText.trim()}>
              Add students
            </Button>
          </form>
          {bulkResult && (
            <div className="mt-4 space-y-2 text-sm">
              <Alert kind="ok">
                {created.length} added. Save these passwords now. They are shown only once.
              </Alert>
              <textarea readOnly rows={Math.min(8, Math.max(2, bulkResult.length))} className={`${inputClass} font-mono text-xs`} value={copyText} aria-label="New student passwords" />
              {bulkResult.filter((r) => r.error).map((r) => (
                <p key={r.email + r.error} className="text-red-700">
                  {r.email}: {r.error}
                </p>
              ))}
            </div>
          )}
        </Card>
      </div>

      <Card title={`People (${people.length})`}>
        <div className="mb-3 flex flex-wrap gap-3">
          {me.role !== "teacher" && (
            <select aria-label="Filter by role" className={`${inputClass} !w-auto`} value={filterRole} onChange={(e) => setFilterRole(e.target.value)}>
              <option value="">All roles</option>
              <option value="admin">College admins</option>
              <option value="teacher">Teachers</option>
              <option value="student">Students</option>
            </select>
          )}
          {isSuper && (
            <select aria-label="Filter by college" className={`${inputClass} !w-auto`} value={filterCollege} onChange={(e) => setFilterCollege(e.target.value)}>
              <option value="">All colleges</option>
              {colleges.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          )}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 text-slate-500">
              <tr>
                <th className="py-2 pr-3">Name</th>
                <th className="py-2 pr-3">Email</th>
                <th className="py-2 pr-3">Role</th>
                <th className="py-2 pr-3">Status</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {people.map((p) => (
                <tr key={p.id} className="border-b border-slate-100 last:border-0">
                  <td className="py-2 pr-3 font-medium text-slate-900">{p.name}</td>
                  <td className="py-2 pr-3 text-slate-600">{p.email}</td>
                  <td className="py-2 pr-3">{roleLabel[p.role]}</td>
                  <td className="py-2 pr-3">{p.is_active ? "Active" : "Disabled"}</td>
                  <td className="space-x-2 py-2 text-right whitespace-nowrap">
                    {canManage(p) && (
                      <Button variant="secondary" onClick={() => resetPassword(p)}>
                        New password
                      </Button>
                    )}
                    {canDisable && canManage(p) && (
                      <Button variant={p.is_active ? "danger" : "secondary"} onClick={() => toggleActive(p)}>
                        {p.is_active ? "Disable" : "Enable"}
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {people.length === 0 && <p className="py-3 text-sm text-slate-500">No people yet.</p>}
        </div>
      </Card>
    </div>
  );
}
