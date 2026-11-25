import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import CodeEditor from "../CodeEditor.jsx";
import AIHelper from "../AIHelper.jsx";
import ExamTimer from "../ExamTimer.jsx";
import Markdown from "../Markdown.jsx";
import { waitForResult } from "../polling.js";
import { Alert, Badge, Button, Card, VerdictBadge, difficultyColor, inputClass } from "../ui.jsx";

export const STARTERS = {
  c: "#include <stdio.h>\n\nint main(void) {\n    \n    return 0;\n}\n",
  cpp: "#include <iostream>\nusing namespace std;\n\nint main() {\n    \n    return 0;\n}\n",
  java: "import java.util.Scanner;\n\n// The class must be named Main.\npublic class Main {\n    public static void main(String[] args) {\n        Scanner in = new Scanner(System.in);\n        \n    }\n}\n",
  python: "# Read input with input(), print the answer with print()\n\n",
};

// How long after the last key press the code is saved on the server during an exam.
const DRAFT_MS = import.meta.env.MODE === "test" ? 30 : 2000;
// Code written inside an assessment is kept apart from practice code for the same problem.
const keyFor = (aid, id) => (aid ? `a${aid}-${id}` : String(id));
const codeKey = (ns, lang) => `sankalp_code_${ns}_${lang}`;
const langKey = (ns) => `sankalp_lang_${ns}`;

function Output({ title, text }) {
  if (!text) return null;
  return (
    <div className="mt-2">
      <p className="text-xs font-semibold uppercase text-slate-500">{title}</p>
      <pre className="max-h-48 overflow-auto rounded bg-slate-900 p-2 text-xs text-slate-100">{text}</pre>
    </div>
  );
}

function RunResult({ result }) {
  return (
    <div>
      <div className="flex items-center gap-2 text-sm">
        <VerdictBadge verdict={result.verdict} />
        {result.runtime_ms != null && <span className="text-slate-500">{result.runtime_ms} ms</span>}
      </div>
      <Output title="Compiler message" text={result.compile_output} />
      <Output title="Output" text={result.stdout} />
      <Output title="Error output" text={result.stderr} />
      {result.message && <p className="mt-2 text-sm text-slate-600">{result.message}</p>}
    </div>
  );
}

function SubmitResult({ result }) {
  if (result.hidden) {
    return (
      <p className="text-sm text-slate-800">
        <Badge color="bg-indigo-100 text-indigo-800">Answer received</Badge>{" "}
        Your result is hidden during the exam. Your teacher will publish the results later. Use <strong>Run</strong> to test your code.
      </p>
    );
  }
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <VerdictBadge verdict={result.verdict} />
        {result.verdict !== "compile_error" && result.verdict !== "internal_error" && (
          <span className="text-slate-700">
            {result.passed_count} of {result.total_count} tests passed
          </span>
        )}
        {result.runtime_ms != null && result.verdict !== "compile_error" && <span className="text-slate-500">{result.runtime_ms} ms</span>}
      </div>
      <Output title="Compiler message" text={result.compile_output} />
      {result.message && <p className="mt-2 text-sm text-slate-600">{result.message}</p>}
      {result.results?.length > 0 && (
        <ul className="mt-3 space-y-2 text-sm">
          {result.results.map((t) => (
            <li key={t.position} className="rounded border border-slate-200 p-2">
              <div className="flex items-center gap-2">
                <span className="font-medium">{t.hidden ? `Hidden test ${t.position}` : `Sample test ${t.position}`}</span>
                <VerdictBadge verdict={t.verdict} />
              </div>
              {!t.hidden && t.verdict !== "accepted" && (
                <div className="mt-1 grid gap-2 md:grid-cols-3">
                  <Output title="Input" text={t.input} />
                  <Output title="Expected" text={t.expected} />
                  <Output title="Your output" text={t.actual || t.error} />
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** The latest compiler or runtime message from the student's own Run or Submit, for the "Explain my error" button. */
export function latestError(run, submit) {
  if (run?.verdict === "compile_error" && run.compile_output) return run.compile_output;
  if (run?.verdict === "runtime_error" && (run.stderr || run.message)) return run.stderr || run.message;
  if (submit && !submit.hidden) {
    if (submit.verdict === "compile_error" && submit.compile_output) return submit.compile_output;
    if (submit.verdict === "runtime_error") return submit.results?.find((t) => t.error)?.error || submit.message || null;
  }
  return null;
}

export default function ProblemPage() {
  const { id, aid } = useParams();
  const { user } = useAuth();
  const inAssessment = Boolean(aid);
  const ns = keyFor(aid, id);
  const isStudent = user.role === "student";
  const readOnly = inAssessment && !isStudent; // teachers can read the problem, only students answer

  const [problem, setProblem] = useState(null);
  const [assessment, setAssessment] = useState(null);
  const [languages, setLanguages] = useState([]);
  const [language, setLanguage] = useState(() => localStorage.getItem(langKey(ns)) || "python");
  const [code, setCode] = useState("");
  const [stdin, setStdin] = useState("");
  const [history, setHistory] = useState([]);
  const [busy, setBusy] = useState(null); // "run" | "submit" | null
  const [runResult, setRunResult] = useState(null);
  const [submitResult, setSubmitResult] = useState(null);
  const [error, setError] = useState("");
  const [savedAt, setSavedAt] = useState(null);
  const [draftError, setDraftError] = useState("");
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const loadHistory = useCallback(() => {
    if (inAssessment) return isStudent ? api.assessmentSubmissions(aid, id).then(setHistory).catch(() => {}) : Promise.resolve();
    return api.mySubmissions(id).then(setHistory).catch(() => {});
  }, [id, aid, inAssessment, isStudent]);

  const refreshAssessment = useCallback(() => {
    if (!aid) return Promise.resolve();
    return api.getAssessment(aid).then(setAssessment).catch(() => {});
  }, [aid]);

  useEffect(() => {
    const requests = inAssessment
      ? [api.getAssessmentProblem(aid, id), api.listLanguages(), api.getAssessment(aid)]
      : [api.getProblem(id), api.listLanguages()];
    Promise.all(requests)
      .then(([p, l, assessmentInfo]) => {
        setProblem(p);
        setLanguages(l);
        if (assessmentInfo) setAssessment(assessmentInfo);
        setStdin(p.test_cases.find((t) => !t.is_hidden)?.input ?? "");
      })
      .catch((e) => setError(e.message));
    loadHistory();
  }, [id, aid, inAssessment, loadHistory]);

  // The code is saved in this browser for every problem and language, so nothing is lost on a refresh.
  useEffect(() => {
    setCode(localStorage.getItem(codeKey(ns, language)) ?? STARTERS[language] ?? "");
  }, [ns, language]);

  const changeCode = (value) => {
    setCode(value);
    try {
      localStorage.setItem(codeKey(ns, language), value);
    } catch {
      /* storage full or blocked: not a problem, the code is still in the editor */
    }
  };

  const changeLanguage = (value) => {
    setLanguage(value);
    localStorage.setItem(langKey(ns), value);
  };

  // ---------- exam: the server keeps the clock, a copy of the code, and counts tab changes ----------
  const status = assessment?.status;
  const examActive = inAssessment && assessment?.type === "exam" && status === "in_progress";
  const canAnswer = !readOnly && (!inAssessment || status === "in_progress" || status === "open");

  useEffect(() => {
    if (!examActive) return;
    api
      .getDraft(aid, id)
      .then((draft) => {
        if (!draft) return;
        localStorage.setItem(langKey(ns), draft.language);
        localStorage.setItem(codeKey(ns, draft.language), draft.source_code);
        setLanguage(draft.language);
        setCode(draft.source_code);
      })
      .catch(() => {});
  }, [examActive, aid, id, ns]);

  useEffect(() => {
    if (!examActive || !code.trim() || code === STARTERS[language]) return undefined;
    const timer = setTimeout(() => {
      api
        .saveDraft(aid, id, { language, source_code: code })
        .then(() => {
          setSavedAt(new Date());
          setDraftError("");
        })
        .catch((e) => setDraftError(e.message));
    }, DRAFT_MS);
    return () => clearTimeout(timer);
  }, [code, language, examActive, aid, id]);

  useEffect(() => {
    if (!examActive) return undefined;
    const onChange = () => {
      if (document.visibilityState === "hidden") api.tabSwitch(aid).catch(() => {});
    };
    document.addEventListener("visibilitychange", onChange);
    return () => document.removeEventListener("visibilitychange", onChange);
  }, [examActive, aid]);

  async function start(kind) {
    setError("");
    setBusy(kind);
    try {
      const base = { language, source_code: code, problem_id: Number(id) };
      if (inAssessment) base.assessment_id = Number(aid);
      const created = kind === "run" ? await api.run({ ...base, stdin }) : await api.submit(base);
      const result = await waitForResult(created.id, () => alive.current);
      if (!result) return;
      if (kind === "run") setRunResult(result);
      else {
        setSubmitResult(result);
        loadHistory();
      }
    } catch (err) {
      setError(err.message);
      if (inAssessment) refreshAssessment(); // maybe the time is over: show the real state
    } finally {
      if (alive.current) setBusy(null);
    }
  }

  async function useOldCode(submissionId) {
    try {
      const old = await api.getSubmission(submissionId);
      setLanguage(old.language);
      localStorage.setItem(langKey(ns), old.language);
      localStorage.setItem(codeKey(ns, old.language), old.source_code);
      setCode(old.source_code);
    } catch (err) {
      setError(err.message);
    }
  }

  const backTo = inAssessment ? `/assessments/${aid}` : "/problems";
  const backLabel = inAssessment ? "← Back to the assessment" : "← All problems";

  if (error && !problem) {
    return (
      <div className="space-y-3">
        <Alert>{error}</Alert>
        <Link to={backTo} className="text-indigo-700 underline">
          Go back
        </Link>
      </div>
    );
  }
  if (!problem) return <p className="text-slate-500">Loading…</p>;

  const samples = problem.test_cases.filter((t) => !t.is_hidden);
  // Never in an exam. In a normal problem or an assignment the helper decides by itself whether it is open.
  const showAI = isStudent && (!inAssessment || assessment?.type === "assignment");
  const closedText =
    inAssessment && !readOnly && assessment && !canAnswer
      ? assessment.type === "exam"
        ? "Time is over. You can no longer send answers."
        : status === "upcoming"
          ? "This assignment has not started yet."
          : "This assignment is closed. You can still read the problem."
      : "";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link to={backTo} className="text-sm text-indigo-700 underline">
          {backLabel}
        </Link>
        {examActive && assessment.attempt && (
          <ExamTimer attempt={assessment.attempt} serverNow={assessment.server_now} onExpire={refreshAssessment} />
        )}
      </div>
      {inAssessment && assessment && <p className="text-sm text-slate-500">{assessment.title}</p>}

      <div className="grid gap-4 lg:grid-cols-2">
        {/* left: the question */}
        <div className="space-y-4">
          <Card>
            <div className="mb-2 flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-bold text-slate-900">{problem.title}</h1>
              <span className={`text-xs font-semibold uppercase ${difficultyColor[problem.difficulty]}`}>{problem.difficulty}</span>
              {problem.can_edit && !inAssessment && (
                <Link to={`/problems/${problem.id}/edit`} className="text-sm text-indigo-700 underline">
                  Edit
                </Link>
              )}
            </div>
            <p className="mb-3 text-xs text-slate-500">
              Time limit {problem.time_limit_ms} ms · Memory limit {problem.memory_limit_mb} MB
            </p>
            <Markdown>{problem.statement_md}</Markdown>
          </Card>
          {samples.map((t, i) => (
            <Card key={t.position} title={`Sample ${i + 1}`}>
              <div className="grid gap-2 md:grid-cols-2">
                <Output title="Input" text={t.input || "(empty)"} />
                <Output title="Output" text={t.expected_output} />
              </div>
            </Card>
          ))}
        </div>

        {/* right: the answer */}
        <div className="space-y-4">
          <Card>
            {readOnly && <p className="mb-2 text-sm text-slate-600">You are viewing this as a teacher. Only students can send answers.</p>}
            {closedText && <p className="mb-2 text-sm font-medium text-red-700">{closedText}</p>}
            <div className="mb-2 flex items-center gap-3">
              <label className="text-sm font-medium text-slate-700" htmlFor="language">
                Language
              </label>
              <select id="language" className={`${inputClass} !w-auto`} value={language} onChange={(e) => changeLanguage(e.target.value)}>
                {languages.map((l) => (
                  <option key={l.key} value={l.key}>
                    {l.label}
                  </option>
                ))}
              </select>
            </div>
            <CodeEditor language={language} value={code} onChange={changeCode} />
            {examActive && (
              <p className="mt-1 text-xs text-slate-500">
                {draftError ? `Could not save: ${draftError}` : savedAt ? `Saved automatically at ${savedAt.toLocaleTimeString()}` : "Your code is saved automatically while you type."}
              </p>
            )}
            <label className="mt-3 block text-sm font-medium text-slate-700" htmlFor="stdin">
              Test with your own input
            </label>
            <textarea id="stdin" rows={3} className={`${inputClass} font-mono`} value={stdin} onChange={(e) => setStdin(e.target.value)} />
            <div className="mt-3 flex flex-wrap gap-3">
              <Button variant="secondary" disabled={busy !== null || !code.trim() || !canAnswer} onClick={() => start("run")}>
                {busy === "run" ? "Running…" : "Run"}
              </Button>
              <Button disabled={busy !== null || !code.trim() || !canAnswer} onClick={() => start("submit")}>
                {busy === "submit" ? "Judging…" : "Submit"}
              </Button>
            </div>
            {error && (
              <div className="mt-3">
                <Alert>{error}</Alert>
              </div>
            )}
          </Card>

          {runResult && (
            <Card title="Run result">
              <RunResult result={runResult} />
            </Card>
          )}
          {submitResult && (
            <Card title="Submission result">
              <SubmitResult result={submitResult} />
            </Card>
          )}

          {showAI && (
            <AIHelper problemId={Number(id)} language={language} code={code} lastError={latestError(runResult, submitResult)} />
          )}

          {!readOnly && (
            <Card title="My earlier submissions">
              {history.length === 0 ? (
                <p className="text-sm text-slate-500">You have not submitted yet.</p>
              ) : (
                <ul className="divide-y divide-slate-100 text-sm">
                  {history.map((h) => (
                    <li key={h.id} className="flex flex-wrap items-center gap-2 py-2">
                      {h.hidden ? (
                        <Badge color="bg-indigo-100 text-indigo-800">Received</Badge>
                      ) : (
                        <>
                          <VerdictBadge verdict={h.verdict} />
                          <span className="text-slate-600">
                            {h.passed_count}/{h.total_count} · {h.language}
                          </span>
                        </>
                      )}
                      {h.hidden && <span className="text-slate-600">{h.language}</span>}
                      <span className="text-slate-400">{new Date(h.created_at).toLocaleString()}</span>
                      <button className="ml-auto text-indigo-700 underline" onClick={() => useOldCode(h.id)}>
                        Use this code
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
