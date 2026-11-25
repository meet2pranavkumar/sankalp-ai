import { useEffect, useState } from "react";
import { api } from "../api.js";
import { formatWhen } from "../time.js";
import { Alert, Badge, Button, Card } from "../ui.jsx";

const LEVEL_NAME = { 1: "Hint 1 (nudge)", 2: "Hint 2 (method)", 3: "Hint 3 (pseudo-code)" };

function RequestList({ problemId, days }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api
      .aiRequests(problemId, days)
      .then(setItems)
      .catch((e) => setError(e.message));
  }, [problemId, days]);

  if (error) return <Alert>{error}</Alert>;
  if (!items) return <p className="text-sm text-slate-500">Loading…</p>;
  if (items.length === 0) return <p className="text-sm text-slate-500">Nothing in this time.</p>;
  return (
    <ul className="space-y-2">
      {items.map((r) => (
        <li key={r.id} className="rounded border border-slate-200 p-2 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium text-slate-900">{r.student_name}</span>
            <span className="text-slate-600">{r.kind === "explain" ? "Error explained" : LEVEL_NAME[r.level]}</span>
            {r.status === "fallback" && <Badge color="bg-amber-100 text-amber-800">Safe text shown instead</Badge>}
            {r.status === "ok" && r.flagged && <Badge color="bg-amber-100 text-amber-800">First AI answer refused</Badge>}
            {r.status === "error" && <Badge color="bg-red-100 text-red-800">AI service problem</Badge>}
            <span className="ml-auto text-xs text-slate-400">{formatWhen(r.created_at)}</span>
          </div>
          <p className="mt-1 whitespace-pre-wrap text-slate-700">{r.text}</p>
        </li>
      ))}
    </ul>
  );
}

export default function AIInsights() {
  const [days, setDays] = useState(30);
  const [rows, setRows] = useState(null);
  const [open, setOpen] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setRows(null);
    setOpen(null);
    api
      .aiInsights(days)
      .then(setRows)
      .catch((e) => setError(e.message));
  }, [days]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-slate-900">Where students need help</h1>
        <select aria-label="Time" className="rounded border border-slate-300 px-3 py-2 text-sm" value={days} onChange={(e) => setDays(Number(e.target.value))}>
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </div>
      <p className="text-sm text-slate-600">
        Students can ask the AI helper for hints and for explanations of errors. Problems at the top are where help is asked for most.
        If many students need Hint 3 on the same problem, the topic may need another lesson or more practice.
        You see only students of your own batches (admins see the whole college).
      </p>
      {error && <Alert>{error}</Alert>}
      {rows === null && !error ? (
        <p className="text-slate-500">Loading…</p>
      ) : rows && rows.length === 0 ? (
        <Card>
          <p className="text-sm text-slate-600">No one has asked the AI helper for help in this time.</p>
        </Card>
      ) : (
        rows && (
          <Card>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-200 text-slate-500">
                  <tr>
                    <th className="py-2 pr-3">Problem</th>
                    <th className="py-2 pr-3">Students</th>
                    <th className="py-2 pr-3">Requests</th>
                    <th className="py-2 pr-3">Hints</th>
                    <th className="py-2 pr-3">Hint 3</th>
                    <th className="py-2 pr-3">Errors explained</th>
                    <th className="py-2 pr-3">AI tried to give the answer</th>
                    <th className="py-2 pr-3">Service problems</th>
                    <th className="py-2" />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.problem_id} className="border-b border-slate-100 align-top last:border-0">
                      <td className="py-2 pr-3 font-medium text-slate-900">{r.title}</td>
                      <td className="py-2 pr-3">{r.students}</td>
                      <td className="py-2 pr-3 font-semibold">{r.requests}</td>
                      <td className="py-2 pr-3">{r.hints}</td>
                      <td className="py-2 pr-3">{r.level3}</td>
                      <td className="py-2 pr-3">{r.explains}</td>
                      <td className="py-2 pr-3">{r.flagged}</td>
                      <td className="py-2 pr-3">{r.errors}</td>
                      <td className="py-2">
                        <Button variant="secondary" aria-label={`See what students were told for ${r.title}`} onClick={() => setOpen(open === r.problem_id ? null : r.problem_id)}>
                          {open === r.problem_id ? "Hide" : "See details"}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {open !== null && (
              <div className="mt-4 border-t border-slate-200 pt-4">
                <h2 className="mb-2 text-base font-semibold text-slate-900">What students were told</h2>
                <RequestList problemId={open} days={days} />
              </div>
            )}
          </Card>
        )
      )}
    </div>
  );
}
