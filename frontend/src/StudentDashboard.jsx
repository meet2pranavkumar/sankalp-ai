import { Link } from "react-router-dom";
import ActivityChart from "./ActivityChart.jsx";
import { formatDay, formatWhen } from "./time.js";
import { Card, ProgressBar, VerdictBadge, Badge } from "./ui.jsx";

function Stat({ label, value, note }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-bold text-slate-900">{value}</p>
      {note && <p className="mt-1 text-xs text-slate-500">{note}</p>}
    </div>
  );
}

const LEVELS = { easy: "Easy", medium: "Medium", hard: "Hard" };

/** One student's progress. Used by the student for themselves and by teachers looking at a student. */
export default function StudentDashboard({ report, staffView = false }) {
  const solved = report.problems.reduce((n, p) => n + p.solved, 0);
  const available = report.problems.reduce((n, p) => n + p.total, 0);
  const noActivity = report.last_active_at === null;

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Streak" value={`${report.streak_days} ${report.streak_days === 1 ? "day" : "days"}`} note={report.streak_days > 0 ? "Days in a row with some practice" : "Practise today to start a streak"} />
        <Stat label="Active days" value={report.active_days_30} note="out of the last 30" />
        <Stat label="Problems solved" value={`${solved} of ${available}`} />
        <Stat label="Accepted answers" value={report.accepted_submissions} note={`of ${report.total_submissions} sent`} />
        {staffView && report.ai_requests_30d !== null && <Stat label="AI helper requests" value={report.ai_requests_30d} note="in the last 30 days" />}
        <Stat label="Last active" value={noActivity ? "Never" : formatDay(report.last_active_at)} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Courses">
          {report.courses.length === 0 ? (
            <p className="text-sm text-slate-500">There are no published courses yet.</p>
          ) : (
            <ul className="space-y-3">
              {report.courses.map((c) => (
                <li key={c.course_id}>
                  <p className="mb-1 text-sm font-medium text-slate-800">
                    {staffView ? c.title : <Link to={`/courses/${c.course_id}`} className="text-indigo-700 underline">{c.title}</Link>}
                  </p>
                  <ProgressBar done={c.completed_lessons} total={c.total_lessons} />
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Problems solved, by level">
          <ul className="space-y-3">
            {report.problems.map((p) => (
              <li key={p.difficulty}>
                <p className="mb-1 flex justify-between text-sm text-slate-800">
                  <span className="font-medium">{LEVELS[p.difficulty]}</span>
                  <span>{p.solved} of {p.total}</span>
                </p>
                <div
                  role="progressbar"
                  aria-label={`${LEVELS[p.difficulty]} problems solved`}
                  aria-valuenow={p.total ? Math.round((p.solved / p.total) * 100) : 0}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  className="h-2 w-full overflow-hidden rounded bg-slate-200"
                >
                  <div className="h-full bg-emerald-500" style={{ width: `${p.total ? (p.solved / p.total) * 100 : 0}%` }} />
                </div>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card title="The last 30 days">
        <ActivityChart days={report.activity} />
      </Card>

      <Card title="Recent answers">
        {report.recent.length === 0 ? (
          <p className="text-sm text-slate-500">No answers sent yet.</p>
        ) : (
          <ul className="divide-y divide-slate-100 text-sm">
            {report.recent.map((r) => (
              <li key={r.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2">
                {r.hidden ? (
                  <>
                    <span className="font-medium text-slate-700">{r.title}</span>
                    <Badge color="bg-indigo-100 text-indigo-800">Result not published yet</Badge>
                  </>
                ) : (
                  <>
                    {r.problem_id && !staffView ? (
                      <Link to={`/problems/${r.problem_id}`} className="font-medium text-indigo-700 underline">{r.title}</Link>
                    ) : (
                      <span className="font-medium text-slate-800">{r.title}</span>
                    )}
                    <VerdictBadge verdict={r.verdict} />
                    <span className="text-slate-500">{r.passed_count}/{r.total_count} tests · {r.language}</span>
                  </>
                )}
                <span className="ml-auto text-xs text-slate-400">{formatWhen(r.created_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
