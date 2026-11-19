import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";
import CodeEditor from "../CodeEditor.jsx";
import Markdown from "../Markdown.jsx";
import { waitForResult } from "../polling.js";
import { Alert, Button, Card, VerdictBadge, difficultyColor, inputClass } from "../ui.jsx";

export const STARTERS = {
  c: "#include <stdio.h>\n\nint main(void) {\n    \n    return 0;\n}\n",
  cpp: "#include <iostream>\nusing namespace std;\n\nint main() {\n    \n    return 0;\n}\n",
  java: "import java.util.Scanner;\n\n// The class must be named Main.\npublic class Main {\n    public static void main(String[] args) {\n        Scanner in = new Scanner(System.in);\n        \n    }\n}\n",
  python: "# Read input with input(), print the answer with print()\n\n",
};

const codeKey = (id, lang) => `sankalp_code_${id}_${lang}`;
const langKey = (id) => `sankalp_lang_${id}`;

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

export default function ProblemPage() {
  const { id } = useParams();
  const [problem, setProblem] = useState(null);
  const [languages, setLanguages] = useState([]);
  const [language, setLanguage] = useState(() => localStorage.getItem(langKey(id)) || "python");
  const [code, setCode] = useState("");
  const [stdin, setStdin] = useState("");
  const [history, setHistory] = useState([]);
  const [busy, setBusy] = useState(null); // "run" | "submit" | null
  const [runResult, setRunResult] = useState(null);
  const [submitResult, setSubmitResult] = useState(null);
  const [error, setError] = useState("");
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const loadHistory = useCallback(() => api.mySubmissions(id).then(setHistory).catch(() => {}), [id]);

  useEffect(() => {
    Promise.all([api.getProblem(id), api.listLanguages()])
      .then(([p, l]) => {
        setProblem(p);
        setLanguages(l);
        setStdin(p.test_cases.find((t) => !t.is_hidden)?.input ?? "");
      })
      .catch((e) => setError(e.message));
    loadHistory();
  }, [id, loadHistory]);

  // The code is saved in this browser for every problem and language, so nothing is lost on a refresh.
  useEffect(() => {
    setCode(localStorage.getItem(codeKey(id, language)) ?? STARTERS[language] ?? "");
  }, [id, language]);

  const changeCode = (value) => {
    setCode(value);
    try {
      localStorage.setItem(codeKey(id, language), value);
    } catch {
      /* storage full or blocked: not a problem, the code is still in the editor */
    }
  };

  const changeLanguage = (value) => {
    setLanguage(value);
    localStorage.setItem(langKey(id), value);
  };

  async function start(kind) {
    setError("");
    setBusy(kind);
    try {
      const body = { language, source_code: code };
      let created;
      if (kind === "run") {
        created = await api.run({ ...body, stdin, problem_id: Number(id) });
      } else {
        created = await api.submit({ ...body, problem_id: Number(id) });
      }
      const result = await waitForResult(created.id, () => alive.current);
      if (!result) return;
      if (kind === "run") setRunResult(result);
      else {
        setSubmitResult(result);
        loadHistory();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      if (alive.current) setBusy(null);
    }
  }

  async function useOldCode(submissionId) {
    try {
      const old = await api.getSubmission(submissionId);
      setLanguage(old.language);
      localStorage.setItem(langKey(id), old.language);
      localStorage.setItem(codeKey(id, old.language), old.source_code);
      setCode(old.source_code);
    } catch (err) {
      setError(err.message);
    }
  }

  if (error && !problem) {
    return (
      <div className="space-y-3">
        <Alert>{error}</Alert>
        <Link to="/problems" className="text-indigo-700 underline">
          Back to problems
        </Link>
      </div>
    );
  }
  if (!problem) return <p className="text-slate-500">Loading…</p>;

  const samples = problem.test_cases.filter((t) => !t.is_hidden);

  return (
    <div className="space-y-4">
      <Link to="/problems" className="text-sm text-indigo-700 underline">
        ← All problems
      </Link>
      <div className="grid gap-4 lg:grid-cols-2">
        {/* left: the question */}
        <div className="space-y-4">
          <Card>
            <div className="mb-2 flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-bold text-slate-900">{problem.title}</h1>
              <span className={`text-xs font-semibold uppercase ${difficultyColor[problem.difficulty]}`}>{problem.difficulty}</span>
              {problem.can_edit && (
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
            <label className="mt-3 block text-sm font-medium text-slate-700" htmlFor="stdin">
              Test with your own input
            </label>
            <textarea id="stdin" rows={3} className={`${inputClass} font-mono`} value={stdin} onChange={(e) => setStdin(e.target.value)} />
            <div className="mt-3 flex flex-wrap gap-3">
              <Button variant="secondary" disabled={busy !== null || !code.trim()} onClick={() => start("run")}>
                {busy === "run" ? "Running…" : "Run"}
              </Button>
              <Button disabled={busy !== null || !code.trim()} onClick={() => start("submit")}>
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

          <Card title="My earlier submissions">
            {history.length === 0 ? (
              <p className="text-sm text-slate-500">You have not submitted yet.</p>
            ) : (
              <ul className="divide-y divide-slate-100 text-sm">
                {history.map((h) => (
                  <li key={h.id} className="flex flex-wrap items-center gap-2 py-2">
                    <VerdictBadge verdict={h.verdict} />
                    <span className="text-slate-600">
                      {h.passed_count}/{h.total_count} · {h.language}
                    </span>
                    <span className="text-slate-400">{new Date(h.created_at).toLocaleString()}</span>
                    <button className="ml-auto text-indigo-700 underline" onClick={() => useOldCode(h.id)}>
                      Use this code
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
