import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { formatDay } from "../time.js";
import { Alert, Card } from "../ui.jsx";

export const INACTIVE_CHOICES = [3, 7, 14, 30];

export default function Reports() {
  const [days, setDays] = useState(7);
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setRows(null);
    api
      .batchSummaries(days)
      .then(setRows)
      .catch((e) => setError(e.message));
  }, [days]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-slate-900">Class reports</h1>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          Show a student as inactive after
          <select aria-label="Inactive after" className="rounded border border-slate-300 px-2 py-1" value={days} onChange={(e) => setDays(Number(e.target.value))}>
            {INACTIVE_CHOICES.map((n) => (
              <option key={n} value={n}>{n} days</option>
            ))}
          </select>
          without activity
        </label>
      </div>
      {error && <Alert>{error}</Alert>}
      {rows === null && !error ? (
        <p className="text-slate-500">Loading…</p>
      ) : rows && rows.length === 0 ? (
        <Card>
          <p className="text-sm text-slate-600">You have no batches yet. Create a batch and add students to see how they are doing.</p>
        </Card>
      ) : (
        rows && (
          <Card>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-200 text-slate-500">
                  <tr>
                    <th className="py-2 pr-3">Batch</th>
                    <th className="py-2 pr-3">Students</th>
                    <th className="py-2 pr-3">Course completion</th>
                    <th className="py-2 pr-3">Problems solved (average)</th>
                    <th className="py-2 pr-3">Need attention</th>
                    <th className="py-2 pr-3">Last activity</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((b) => (
                    <tr key={b.batch_id} className="border-b border-slate-100 last:border-0">
                      <td className="py-2 pr-3">
                        <Link to={`/reports/batches/${b.batch_id}`} className="font-medium text-indigo-700 underline">{b.name}</Link>
                        <span className="text-xs text-slate-500">{b.branch ? ` · ${b.branch}` : ""}{b.year ? ` · ${b.year}` : ""}</span>
                      </td>
                      <td className="py-2 pr-3">{b.student_count}</td>
                      <td className="py-2 pr-3">{b.total_lessons > 0 ? `${b.avg_completion_percent}%` : "No courses yet"}</td>
                      <td className="py-2 pr-3">{b.avg_problems_solved}</td>
                      <td className={`py-2 pr-3 ${b.inactive_count > 0 ? "font-semibold text-amber-700" : ""}`}>{b.inactive_count}</td>
                      <td className="py-2 pr-3 text-slate-600">{b.last_active_at ? formatDay(b.last_active_at) : "Never"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-xs text-slate-500">
              &quot;Need attention&quot; counts students with no activity (an answer, a Run, a lesson or an exam) for {days} days, and students who have never been active.
            </p>
          </Card>
        )
      )}
    </div>
  );
}
