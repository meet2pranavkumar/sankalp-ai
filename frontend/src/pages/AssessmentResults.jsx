import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";
import { saveBlob } from "../download.js";
import { Alert, Badge, Button, Card, inputClass } from "../ui.jsx";

const REFRESH_MS = import.meta.env.MODE === "test" ? 40 : 3000;
const STATUS = {
  not_started: "Did not start", in_progress: "In progress", finished: "Finished",
  submitted: "Submitted", no_submission: "No answers",
};

function Row({ row, assessmentId, problems, isExam, onSaved }) {
  const [marks, setMarks] = useState(row.override_marks ?? "");
  const [comment, setComment] = useState(row.comment ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const changed = String(marks) !== String(row.override_marks ?? "") || comment !== (row.comment ?? "");

  async function save() {
    setError("");
    setSaving(true);
    try {
      const updated = await api.setOverride(assessmentId, row.user_id, {
        override_marks: marks === "" ? null : Number(marks),
        comment: comment.trim() || null,
      });
      setMarks(updated.override_marks ?? ""); // show what the server really stored (for example a trimmed comment)
      setComment(updated.comment ?? "");
      onSaved(updated);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <tr className="border-b border-slate-100 align-top last:border-0">
      <td className="py-2 pr-3">
        <div className="font-medium text-slate-900">{row.name}</div>
        <div className="text-xs text-slate-500">{row.email}</div>
      </td>
      <td className="py-2 pr-3 text-xs">
        {STATUS[row.status] ?? row.status}
        {row.pending > 0 && <div className="text-amber-700">{row.pending} being checked…</div>}
        {row.judge_errors > 0 && <div className="text-red-700">{row.judge_errors} not checked</div>}
      </td>
      {problems.map((p, i) => (
        <td key={p.problem_id} className="py-2 pr-3 whitespace-nowrap">
          {row.per_problem[i].marks} / {p.marks}
        </td>
      ))}
      <td className="py-2 pr-3 font-semibold">{row.auto_marks}</td>
      {isExam && <td className="py-2 pr-3 text-slate-600">{row.tab_switches}</td>}
      <td className="py-2 pr-3">
        <input aria-label={`Final marks for ${row.name}`} type="number" min={0} step="any" placeholder={String(row.auto_marks)} className="w-24 rounded border border-slate-300 px-2 py-1" value={marks} onChange={(e) => setMarks(e.target.value)} />
      </td>
      <td className="py-2 pr-3">
        <input aria-label={`Comment for ${row.name}`} className={`${inputClass} !w-48`} value={comment} onChange={(e) => setComment(e.target.value)} />
        {error && <p role="alert" className="mt-1 text-xs text-red-700">{error}</p>}
      </td>
      <td className="py-2">
        <Button variant="secondary" disabled={!changed || saving} onClick={save} aria-label={`Save marks for ${row.name}`}>
          Save
        </Button>
      </td>
    </tr>
  );
}

export default function AssessmentResults() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    () =>
      api
        .assessmentResults(id)
        .then(setData)
        .catch((e) => setError(e.message)),
    [id]
  );
  useEffect(() => {
    load();
  }, [load]);

  // While answers are still being checked, look again every few seconds.
  const waiting = data?.pending_total > 0;
  useEffect(() => {
    if (!waiting) return undefined;
    const timer = setTimeout(load, REFRESH_MS);
    return () => clearTimeout(timer);
  }, [waiting, data, load]);

  async function download() {
    setError("");
    try {
      saveBlob(await api.downloadResults(id), `assessment-${id}-results.csv`);
    } catch (err) {
      setError(err.message);
    }
  }

  async function rejudge() {
    setError("");
    setNotice("");
    setBusy(true);
    try {
      const { requeued } = await api.rejudge(id);
      setNotice(`${requeued} answer${requeued === 1 ? "" : "s"} sent to be checked again.`);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function togglePublish() {
    setError("");
    setBusy(true);
    try {
      await api.updateAssessment(id, { results_published: !data.results_published });
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (error && !data) {
    return (
      <div className="space-y-3">
        <Alert>{error}</Alert>
        <Link to="/assessments" className="text-indigo-700 underline">
          Back to assessments
        </Link>
      </div>
    );
  }
  if (!data) return <p className="text-slate-500">Loading…</p>;

  const isExam = data.type === "exam";
  return (
    <div className="space-y-4">
      <Link to={`/assessments/${id}`} className="text-sm text-indigo-700 underline">
        ← Back to the assessment
      </Link>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold text-slate-900">Results: {data.title}</h1>
        {data.results_published ? <Badge color="bg-emerald-100 text-emerald-800">Students can see results</Badge> : <Badge color="bg-amber-100 text-amber-800">Results are hidden from students</Badge>}
      </div>

      {error && <Alert>{error}</Alert>}
      {notice && <Alert kind="ok">{notice}</Alert>}
      {data.pending_total > 0 && (
        <Alert kind="ok">{data.pending_total} answer{data.pending_total === 1 ? " is" : "s are"} still being checked. This page updates by itself.</Alert>
      )}
      {data.judge_errors_total > 0 && (
        <Alert>
          {data.judge_errors_total} answer{data.judge_errors_total === 1 ? " was" : "s were"} not checked because the code judge had a problem. The marks below may be too low.{" "}
          <button type="button" className="font-semibold underline" disabled={busy} onClick={rejudge}>
            Judge again
          </button>
        </Alert>
      )}

      <div className="flex flex-wrap gap-3">
        <Button variant="secondary" onClick={download}>
          Download CSV
        </Button>
        <Button variant={data.results_published ? "secondary" : "primary"} disabled={busy} onClick={togglePublish}>
          {data.results_published ? "Hide results from students" : "Publish results to students"}
        </Button>
      </div>

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 text-slate-500">
              <tr>
                <th className="py-2 pr-3">Student</th>
                <th className="py-2 pr-3">Status</th>
                {data.problems.map((p) => (
                  <th key={p.problem_id} className="py-2 pr-3">{p.title}</th>
                ))}
                <th className="py-2 pr-3">Automatic (/{data.total_marks})</th>
                {isExam && <th className="py-2 pr-3">Tab switches</th>}
                <th className="py-2 pr-3">Final marks</th>
                <th className="py-2 pr-3">Comment</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row) => (
                <Row
                  key={row.user_id}
                  row={row}
                  assessmentId={id}
                  problems={data.problems}
                  isExam={isExam}
                  onSaved={(updated) => setData({ ...data, rows: data.rows.map((r) => (r.user_id === updated.user_id ? updated : r)) })}
                />
              ))}
            </tbody>
          </table>
          {data.rows.length === 0 && <p className="py-3 text-sm text-slate-500">There are no students in this batch yet.</p>}
        </div>
        <p className="mt-3 text-xs text-slate-500">
          Automatic marks use each student&apos;s best answer to every problem: the marks of a problem times the share of tests passed.
          Type a number under Final marks only if you want to change it by hand. Leave it empty to use the automatic marks.
        </p>
      </Card>
    </div>
  );
}
