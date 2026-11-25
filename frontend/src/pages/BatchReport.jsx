import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";
import { saveBlob } from "../download.js";
import { formatDay } from "../time.js";
import { Alert, Badge, Button, Card, difficultyColor } from "../ui.jsx";
import { INACTIVE_CHOICES } from "./Reports.jsx";

function Stat({ label, value, note }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-bold text-slate-900">{value}</p>
      {note && <p className="mt-1 text-xs text-slate-500">{note}</p>}
    </div>
  );
}

const STATUS = {
  active: { label: "Active", color: "bg-emerald-100 text-emerald-800" },
  inactive: { label: "Inactive", color: "bg-amber-100 text-amber-800" },
  never_active: { label: "Never active", color: "bg-red-100 text-red-800" },
};

function Bar({ percent, label }) {
  return (
    <div className="flex items-center gap-2">
      <div role="progressbar" aria-label={label} aria-valuenow={Math.round(percent)} aria-valuemin={0} aria-valuemax={100} className="h-2 w-24 overflow-hidden rounded bg-slate-200">
        <div className="h-full bg-emerald-500" style={{ width: `${percent}%` }} />
      </div>
      <span className="text-xs text-slate-600">{percent}%</span>
    </div>
  );
}

export default function BatchReport() {
  const { id } = useParams();
  const [days, setDays] = useState(7);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .batchReport(id, days)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [id, days]);

  async function download() {
    setError("");
    try {
      saveBlob(await api.downloadBatchReport(id, days), `batch-${id}-progress.csv`);
    } catch (err) {
      setError(err.message);
    }
  }

  if (error && !data) {
    return (
      <div className="space-y-3">
        <Alert>{error}</Alert>
        <Link to="/reports" className="text-indigo-700 underline">Back to the class list</Link>
      </div>
    );
  }
  if (!data) return <p className="text-slate-500">Loading…</p>;

  const s = data.summary;
  const attention = data.students.filter((r) => r.status !== "active");

  return (
    <div className="space-y-4">
      <Link to="/reports" className="text-sm text-indigo-700 underline">← All classes</Link>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{s.name}</h1>
          <p className="text-sm text-slate-500">{[s.branch, s.year].filter(Boolean).join(" · ")}</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-600">
            Inactive after
            <select aria-label="Inactive after" className="rounded border border-slate-300 px-2 py-1" value={days} onChange={(e) => setDays(Number(e.target.value))}>
              {INACTIVE_CHOICES.map((n) => (
                <option key={n} value={n}>{n} days</option>
              ))}
            </select>
          </label>
          <Button variant="secondary" onClick={download}>Download CSV</Button>
        </div>
      </div>
      {error && <Alert>{error}</Alert>}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Students" value={s.student_count} />
        <Stat label="Course completion" value={s.total_lessons > 0 ? `${s.avg_completion_percent}%` : "No courses"} note="average of the class" />
        <Stat label="Problems solved" value={s.avg_problems_solved} note="average per student" />
        <Stat label="Need attention" value={s.inactive_count} note={`no activity for ${data.inactive_days} days, or never`} />
      </div>

      <Card title="Students who need attention">
        {attention.length === 0 ? (
          <p className="text-sm text-emerald-700">Everyone has been active in the last {data.inactive_days} days.</p>
        ) : (
          <ul className="divide-y divide-slate-100 text-sm">
            {attention.map((r) => (
              <li key={r.user_id} className="flex flex-wrap items-center gap-3 py-2">
                <Link to={`/reports/students/${r.user_id}`} className="font-medium text-indigo-700 underline">{r.name}</Link>
                <span className="text-slate-600">{r.status === "never_active" ? "Has never been active" : `No activity for ${r.days_inactive} days`}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="All students">
        {data.students.length === 0 ? (
          <p className="text-sm text-slate-500">There are no students in this batch yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 text-slate-500">
                <tr>
                  <th className="py-2 pr-3">Student</th>
                  <th className="py-2 pr-3">Course completion</th>
                  <th className="py-2 pr-3">Lessons</th>
                  <th className="py-2 pr-3">Problems solved</th>
                  <th className="py-2 pr-3">Answers (30 days)</th>
                  <th className="py-2 pr-3">AI helper (30 days)</th>
                  <th className="py-2 pr-3">Last active</th>
                  <th className="py-2 pr-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {data.students.map((r) => (
                  <tr key={r.user_id} className="border-b border-slate-100 last:border-0">
                    <td className="py-2 pr-3">
                      <Link to={`/reports/students/${r.user_id}`} className="font-medium text-indigo-700 underline">{r.name}</Link>
                      <div className="text-xs text-slate-500">{r.email}</div>
                    </td>
                    <td className="py-2 pr-3"><Bar percent={r.completion_percent} label={`Course completion of ${r.name}`} /></td>
                    <td className="py-2 pr-3">{r.lessons_completed}/{r.lessons_total}</td>
                    <td className="py-2 pr-3">{r.problems_solved}</td>
                    <td className="py-2 pr-3">{r.submissions_30d}</td>
                    <td className="py-2 pr-3">{r.ai_requests_30d}</td>
                    <td className="py-2 pr-3 text-slate-600">{r.last_active_at ? formatDay(r.last_active_at) : "Never"}</td>
                    <td className="py-2 pr-3"><Badge color={STATUS[r.status].color}>{STATUS[r.status].label}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Weak topics">
          {data.weak_topics.length === 0 ? (
            <p className="text-sm text-slate-500">No weak topics found. This needs a few answers from several students (last 90 days).</p>
          ) : (
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 text-slate-500">
                <tr>
                  <th className="py-2 pr-3">Topic</th>
                  <th className="py-2 pr-3">Solved</th>
                  <th className="py-2 pr-3">Wrong answers</th>
                  <th className="py-2 pr-3">Hints asked</th>
                </tr>
              </thead>
              <tbody>
                {data.weak_topics.map((t) => (
                  <tr key={t.topic} className="border-b border-slate-100 last:border-0">
                    <td className="py-2 pr-3 font-medium text-slate-900">{t.topic}</td>
                    <td className="py-2 pr-3">{t.solve_rate_percent}% <span className="text-xs text-slate-500">({t.pairs_solved} of {t.pairs_attempted} tries)</span></td>
                    <td className="py-2 pr-3">{t.wrong_submissions}</td>
                    <td className="py-2 pr-3">{t.hint_requests}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="mt-2 text-xs text-slate-500">A topic is weak when students tried its problems but many did not solve them. A weak topic may need another lesson.</p>
        </Card>

        <Card title="Hardest problems">
          {data.weak_problems.length === 0 ? (
            <p className="text-sm text-slate-500">No problem stands out yet.</p>
          ) : (
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 text-slate-500">
                <tr>
                  <th className="py-2 pr-3">Problem</th>
                  <th className="py-2 pr-3">Solved by</th>
                  <th className="py-2 pr-3">Wrong answers</th>
                  <th className="py-2 pr-3">Hints asked</th>
                </tr>
              </thead>
              <tbody>
                {data.weak_problems.map((p) => (
                  <tr key={p.problem_id} className="border-b border-slate-100 last:border-0">
                    <td className="py-2 pr-3">
                      <Link to={`/problems/${p.problem_id}`} className="font-medium text-indigo-700 underline">{p.title}</Link>{" "}
                      <span className={`text-xs font-semibold uppercase ${difficultyColor[p.difficulty]}`}>{p.difficulty}</span>
                    </td>
                    <td className="py-2 pr-3">{p.students_solved} of {p.students_attempted} students</td>
                    <td className="py-2 pr-3">{p.wrong_submissions}</td>
                    <td className="py-2 pr-3">{p.hint_requests}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Courses">
          {data.courses.length === 0 ? (
            <p className="text-sm text-slate-500">No published courses yet.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {data.courses.map((c) => (
                <li key={c.course_id} className="flex items-center justify-between gap-3">
                  <span className="font-medium text-slate-800">{c.title}</span>
                  <Bar percent={c.avg_percent} label={`Average completion of ${c.title}`} />
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Assignments and exams">
          {data.assessments.length === 0 ? (
            <p className="text-sm text-slate-500">No published assignment or exam for this batch yet.</p>
          ) : (
            <ul className="divide-y divide-slate-100 text-sm">
              {data.assessments.map((a) => (
                <li key={a.assessment_id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2">
                  <Link to={`/assessments/${a.assessment_id}/results`} className="font-medium text-indigo-700 underline">{a.title}</Link>
                  <Badge color={a.type === "exam" ? "bg-purple-100 text-purple-800" : "bg-sky-100 text-sky-800"}>{a.type === "exam" ? "Exam" : "Assignment"}</Badge>
                  <span className="text-slate-600">{a.participants} of {a.students} took part</span>
                  <span className="ml-auto font-semibold text-slate-800">{a.avg_percent === null ? "No marks yet" : `Average ${a.avg_percent}%`}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
