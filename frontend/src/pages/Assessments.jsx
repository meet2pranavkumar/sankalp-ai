import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { formatMinutes, formatWhen } from "../time.js";
import { Alert, Badge, Card, StatusBadge } from "../ui.jsx";

export default function Assessments() {
  const { user } = useAuth();
  const isStaff = user.role !== "student";
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .listAssessments()
      .then(setItems)
      .catch((e) => setError(e.message));
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-slate-900">Assignments and exams</h1>
        {isStaff && (
          <Link to="/assessments/new" className="rounded bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700">
            New assessment
          </Link>
        )}
      </div>
      {error && <Alert>{error}</Alert>}
      {items === null ? (
        <p className="text-slate-500">Loading…</p>
      ) : items.length === 0 ? (
        <Card>
          <p className="text-sm text-slate-600">
            {isStaff ? "You have not created any assignment or exam yet." : "Nothing here yet. Your teacher will publish assignments and exams for your batch."}
          </p>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {items.map((a) => (
            <Card key={a.id}>
              <div className="flex flex-wrap items-center gap-2">
                <Link to={`/assessments/${a.id}`} className="text-lg font-semibold text-indigo-700 underline">
                  {a.title}
                </Link>
                <Badge color={a.type === "exam" ? "bg-purple-100 text-purple-800" : "bg-sky-100 text-sky-800"}>
                  {a.type === "exam" ? "Exam" : "Assignment"}
                </Badge>
                {isStaff ? (
                  !a.is_published && <Badge color="bg-amber-100 text-amber-800">Draft</Badge>
                ) : (
                  <StatusBadge status={a.status} />
                )}
              </div>
              <p className="mt-1 text-sm text-slate-600">{a.batch_name}</p>
              <p className="mt-2 text-xs text-slate-500">
                {formatWhen(a.starts_at)} to {formatWhen(a.ends_at)}
                {a.duration_min ? ` · ${formatMinutes(a.duration_min)} per student` : ""}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                {a.problem_count} problem{a.problem_count === 1 ? "" : "s"} · {a.total_marks} marks
                {a.my_marks !== null && a.my_marks !== undefined ? ` · You scored ${a.my_marks}` : ""}
              </p>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
