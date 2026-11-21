import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import ExamTimer from "../ExamTimer.jsx";
import { formatMinutes, formatWhen } from "../time.js";
import { Alert, Badge, Button, Card, StatusBadge, difficultyColor } from "../ui.jsx";

export default function AssessmentPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const isStaff = user.role !== "student";
  const [a, setA] = useState(null);
  const [mine, setMine] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    () =>
      api
        .getAssessment(id)
        .then(setA)
        .catch((e) => setError(e.message)),
    [id]
  );
  useEffect(() => {
    load();
  }, [load]);

  // After the work is over, the student asks for their result.
  useEffect(() => {
    if (!a || isStaff || !["finished", "closed"].includes(a.status)) return;
    api.myResult(id).then(setMine).catch(() => {});
  }, [a?.status, a?.results_published]); // eslint-disable-line react-hooks/exhaustive-deps

  // During an exam we count (never block) the times the student leaves this tab.
  const examRunning = a?.type === "exam" && a?.status === "in_progress";
  useEffect(() => {
    if (!examRunning) return undefined;
    const onChange = () => {
      if (document.visibilityState === "hidden") api.tabSwitch(id).catch(() => {});
    };
    document.addEventListener("visibilitychange", onChange);
    return () => document.removeEventListener("visibilitychange", onChange);
  }, [examRunning, id]);

  async function act(task) {
    setError("");
    setBusy(true);
    try {
      setA(await task());
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm(`Delete "${a.title}"?`)) return;
    try {
      await api.deleteAssessment(id);
      navigate("/assessments");
    } catch (err) {
      setError(err.message);
    }
  }

  if (error && !a) {
    return (
      <div className="space-y-3">
        <Alert>{error}</Alert>
        <Link to="/assessments" className="text-indigo-700 underline">
          Back to assessments
        </Link>
      </div>
    );
  }
  if (!a) return <p className="text-slate-500">Loading…</p>;

  const isExam = a.type === "exam";
  const canOpenProblems = a.problems && (isStaff || ["in_progress", "open", "finished", "closed"].includes(a.status));

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Link to="/assessments" className="text-sm text-indigo-700 underline">
        ← All assessments
      </Link>
      <Card>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-bold text-slate-900">{a.title}</h1>
          <Badge color={isExam ? "bg-purple-100 text-purple-800" : "bg-sky-100 text-sky-800"}>{isExam ? "Exam" : "Assignment"}</Badge>
          {isStaff ? !a.is_published && <Badge color="bg-amber-100 text-amber-800">Draft</Badge> : <StatusBadge status={a.status} />}
        </div>
        <p className="mt-1 text-sm text-slate-600">{a.batch_name}</p>
        {a.description && <p className="mt-3 whitespace-pre-line text-sm text-slate-800">{a.description}</p>}
        <dl className="mt-3 grid gap-x-6 gap-y-1 text-sm text-slate-600 sm:grid-cols-2">
          <div>
            <dt className="inline font-medium">Opens: </dt>
            <dd className="inline">{formatWhen(a.starts_at)}</dd>
          </div>
          <div>
            <dt className="inline font-medium">Closes: </dt>
            <dd className="inline">{formatWhen(a.ends_at)}</dd>
          </div>
          {isExam && (
            <div>
              <dt className="inline font-medium">Time for each student: </dt>
              <dd className="inline">{formatMinutes(a.duration_min)}</dd>
            </div>
          )}
          <div>
            <dt className="inline font-medium">Total marks: </dt>
            <dd className="inline">{a.total_marks}</dd>
          </div>
        </dl>
      </Card>

      {error && <Alert>{error}</Alert>}

      {/* ---------- what the student can do now ---------- */}
      {!isStaff && a.status === "upcoming" && (
        <Card>
          <p className="text-sm text-slate-700">This {isExam ? "exam" : "assignment"} opens on {formatWhen(a.starts_at)}.</p>
        </Card>
      )}
      {!isStaff && a.status === "ready" && (
        <Card title="Ready to start?">
          <ul className="mb-3 list-disc space-y-1 pl-5 text-sm text-slate-700">
            <li>You will have {formatMinutes(a.duration_min)} from the moment you press Start. The timer cannot be paused.</li>
            <li>The questions appear only after you press Start.</li>
            <li>Your code is saved while you type. If time ends, the last saved code is submitted for you.</li>
            <li>Your results are shown after your teacher publishes them. Leaving this tab is recorded.</li>
          </ul>
          <Button
            disabled={busy}
            onClick={() => window.confirm("Start the exam now? The timer starts immediately.") && act(() => api.startExam(id))}
          >
            Start the exam
          </Button>
        </Card>
      )}
      {!isStaff && a.status === "in_progress" && a.attempt && (
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <ExamTimer attempt={a.attempt} serverNow={a.server_now} onExpire={load} />
            <Button
              variant="danger"
              disabled={busy}
              onClick={() => window.confirm("Finish the exam? You cannot send more answers after this.") && act(() => api.finishExam(id))}
            >
              Finish the exam
            </Button>
          </div>
        </Card>
      )}
      {!isStaff && a.status === "open" && (
        <Card>
          <p className="text-sm text-slate-700">This assignment is open until {formatWhen(a.ends_at)}. Your marks update as you submit.</p>
        </Card>
      )}
      {!isStaff && a.status === "missed" && (
        <Alert>You did not start this exam before it closed.</Alert>
      )}
      {!isStaff && ["finished", "closed"].includes(a.status) && (
        <Card title={isExam ? "Your exam is over" : "This assignment is closed"}>
          {mine === null ? (
            <p className="text-sm text-slate-500">Loading your result…</p>
          ) : mine.visible ? (
            <div className="space-y-1 text-sm text-slate-800">
              <p>
                Your marks: <strong>{mine.final_marks ?? mine.auto_marks}</strong> out of {mine.total_marks}
              </p>
              {mine.comment && <p className="rounded bg-slate-50 p-2">Teacher&apos;s comment: {mine.comment}</p>}
              {mine.pending > 0 && <p className="text-amber-700">Some answers are still being checked. Look again in a minute.</p>}
            </div>
          ) : (
            <p className="text-sm text-slate-700">Your answers were received. Your marks will be shown after your teacher publishes the results.</p>
          )}
        </Card>
      )}

      {/* ---------- problems ---------- */}
      {a.problems && (
        <Card title="Problems">
          <ul className="divide-y divide-slate-100 text-sm">
            {a.problems.map((p) => (
              <li key={p.problem_id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2">
                {canOpenProblems ? (
                  <Link to={`/assessments/${a.id}/problems/${p.problem_id}`} className="font-medium text-indigo-700 underline">
                    {p.title}
                  </Link>
                ) : (
                  <span className="font-medium">{p.title}</span>
                )}
                <span className={`text-xs font-semibold uppercase ${difficultyColor[p.difficulty]}`}>{p.difficulty}</span>
                <span className="ml-auto text-slate-600">{p.score ? `${p.score.marks} / ${p.marks} marks` : `${p.marks} marks`}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* ---------- teacher tools ---------- */}
      {isStaff && a.can_manage && (
        <Card title="Manage">
          <div className="flex flex-wrap gap-3">
            <Button variant="secondary" disabled={busy} onClick={() => act(() => api.updateAssessment(id, { is_published: !a.is_published }))}>
              {a.is_published ? "Hide from students" : "Publish to students"}
            </Button>
            <Link to={`/assessments/${a.id}/edit`} className="rounded border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
              Edit
            </Link>
            <Link to={`/assessments/${a.id}/results`} className="rounded bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700">
              Results and marks
            </Link>
            {!a.has_activity && (
              <Button variant="danger" onClick={remove}>
                Delete
              </Button>
            )}
          </div>
          {!a.is_published && <p className="mt-2 text-xs text-slate-500">This is a draft. Students cannot see it until you publish it.</p>}
          {a.has_activity && <p className="mt-2 text-xs text-slate-500">Students have started, so the problems can no longer change.</p>}
        </Card>
      )}
    </div>
  );
}
