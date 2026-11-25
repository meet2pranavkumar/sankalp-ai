import { useEffect, useState } from "react";
import { api } from "./api.js";
import Markdown from "./Markdown.jsx";
import { Alert, Button, Card } from "./ui.jsx";

const TICK_MS = import.meta.env.MODE === "test" ? 50 : 500;

const LEVELS = [
  { level: 1, button: "Give me a nudge", title: "Hint 1: a nudge" },
  { level: 2, button: "Explain the method", title: "Hint 2: the method" },
  { level: 3, button: "Show pseudo-code", title: "Hint 3: pseudo-code" },
];

const titleOf = (answer) => (answer.kind === "explain" ? "Your error, explained" : LEVELS[answer.level - 1].title);

/**
 * The AI helper for one problem. It gives hints in three steps and explains errors. It never gives the full answer
 * (the server checks every answer), it has a daily limit, and it is closed during exams.
 * `lastError` is the latest compiler or runtime message from the student's own Run or Submit, if any.
 */
export default function AIHelper({ problemId, language, code, lastError }) {
  const [usage, setUsage] = useState(null);
  const [answers, setAnswers] = useState([]); // newest first
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [waitUntil, setWaitUntil] = useState(0);
  const [, tick] = useState(0);

  const applyUsage = (u) => {
    setUsage(u);
    setWaitUntil(u.retry_after_seconds > 0 ? Date.now() + u.retry_after_seconds * 1000 : 0);
  };

  useEffect(() => {
    setUsage(null);
    setError("");
    api
      .aiUsage(problemId)
      .then((u) => {
        applyUsage(u);
        setAnswers(u.recent); // answers from the last 24 hours, so a refresh loses nothing
      })
      .catch((e) => setError(e.message));
  }, [problemId]);

  // While the student must wait before the next hint, show a countdown.
  const waiting = waitUntil > Date.now();
  useEffect(() => {
    if (!waiting) return undefined;
    const timer = setInterval(() => tick((n) => n + 1), TICK_MS);
    return () => clearInterval(timer);
  }, [waiting]);
  const secondsLeft = waiting ? Math.ceil((waitUntil - Date.now()) / 1000) : 0;

  async function ask(task) {
    setError("");
    setBusy(true);
    try {
      const answer = await task();
      setAnswers((old) => [{ id: answer.id, kind: answer.kind, level: answer.level, text: answer.text }, ...old]);
      applyUsage(answer.usage);
    } catch (err) {
      setError(err.message);
      api.aiUsage(problemId).then(applyUsage).catch(() => {}); // the real numbers, in case ours were out of date
    } finally {
      setBusy(false);
    }
  }

  const askHint = (level) => ask(() => api.aiHint({ problem_id: problemId, level, language, source_code: code }));
  const explain = () => ask(() => api.aiExplain({ problem_id: problemId, language, source_code: code, error_text: lastError }));

  if (!usage && !error) {
    return (
      <Card title="Need help?">
        <p className="text-sm text-slate-500">Loading…</p>
      </Card>
    );
  }
  if (!usage) {
    return (
      <Card title="Need help?">
        <Alert>{error}</Alert>
      </Card>
    );
  }
  if (!usage.enabled) {
    return (
      <Card title="Need help?">
        <p className="text-sm text-slate-600">{usage.blocked_reason}</p>
      </Card>
    );
  }

  const canAsk = !busy && !waiting;
  return (
    <Card title="Need help?">
      <p className="mb-3 text-sm text-slate-600">
        Try the problem yourself first. The helper gives hints in three steps. It will not give you the full answer.
      </p>
      <div className="flex flex-wrap gap-2">
        {LEVELS.map(({ level, button }) => (
          <Button key={level} variant="secondary" disabled={!canAsk || !usage.available_levels.includes(level)} onClick={() => askHint(level)}>
            {button}
          </Button>
        ))}
        {lastError && (
          <Button variant="secondary" disabled={busy || usage.explains_used >= usage.explains_limit} onClick={explain}>
            Explain my error
          </Button>
        )}
      </div>
      <p className="mt-2 text-xs text-slate-500">
        Hints used today for this problem: {usage.hints_used} of {usage.hints_limit}.
        {usage.available_levels.length > 0 && usage.available_levels.length < 3 && " The next hint opens after you read this one."}
        {waiting && ` You can ask again in ${secondsLeft} second${secondsLeft === 1 ? "" : "s"}. Use the time to try it.`}
      </p>
      {usage.hints_used >= usage.hints_limit && (
        <p className="mt-2 text-sm text-amber-800">You have used all your hints for this problem today. Try again tomorrow, or ask your teacher.</p>
      )}
      {busy && <p className="mt-2 text-sm text-slate-500">Thinking…</p>}
      {error && (
        <div className="mt-3">
          <Alert>{error}</Alert>
        </div>
      )}
      {answers.length > 0 && (
        <ul className="mt-4 space-y-3">
          {answers.map((a) => (
            <li key={a.id} className="rounded border border-indigo-200 bg-indigo-50 p-3">
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-indigo-800">{titleOf(a)}</p>
              <Markdown>{a.text}</Markdown>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-xs text-slate-400">The helper is an AI and can make mistakes. Your teacher can see the hints you ask for.</p>
    </Card>
  );
}
