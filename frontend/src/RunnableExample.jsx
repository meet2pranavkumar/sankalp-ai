import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import { waitForResult } from "./polling.js";
import { Alert, Button, VerdictBadge } from "./ui.jsx";

const LABELS = { c: "C", cpp: "C++", java: "Java", python: "Python" };

/** A code example inside a lesson. The student can change the code and the input, and run it. */
export default function RunnableExample({ language, code: initialCode, stdin: initialInput = "" }) {
  const [code, setCode] = useState(initialCode);
  const [stdin, setStdin] = useState(initialInput);
  const [showInput, setShowInput] = useState(initialInput !== "");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  async function run() {
    setError("");
    setBusy(true);
    try {
      const created = await api.run({ language, source_code: code, stdin });
      const done = await waitForResult(created.id, () => alive.current);
      if (done && alive.current) setResult(done);
    } catch (err) {
      if (alive.current) setError(err.message);
    } finally {
      if (alive.current) setBusy(false);
    }
  }

  const lines = Math.min(24, Math.max(3, code.split("\n").length));
  const changed = code !== initialCode || stdin !== initialInput;

  return (
    <div className="my-4 overflow-hidden rounded-lg border border-slate-300 bg-white">
      <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-3 py-1.5 text-xs">
        <span className="font-semibold uppercase tracking-wide text-slate-500">{LABELS[language]} example</span>
        <span className="flex gap-2">
          {changed && (
            <button
              type="button"
              className="text-slate-600 underline"
              onClick={() => {
                setCode(initialCode);
                setStdin(initialInput);
                setResult(null);
              }}
            >
              Reset
            </button>
          )}
          <Button className="!px-3 !py-1 text-xs" onClick={run} disabled={busy || !code.trim()}>
            {busy ? "Running…" : "Run"}
          </Button>
        </span>
      </div>
      <textarea
        aria-label="Example code"
        spellCheck={false}
        rows={lines}
        className="block w-full resize-y border-0 p-3 font-mono text-sm focus:outline-none"
        value={code}
        onChange={(e) => setCode(e.target.value)}
      />
      <div className="border-t border-slate-200 px-3 py-2">
        {showInput ? (
          <label className="block text-xs font-medium text-slate-600">
            Input
            <textarea
              aria-label="Example input"
              rows={2}
              spellCheck={false}
              className="mt-1 block w-full rounded border border-slate-300 p-2 font-mono text-sm"
              value={stdin}
              onChange={(e) => setStdin(e.target.value)}
            />
          </label>
        ) : (
          <button type="button" className="text-xs text-indigo-700 underline" onClick={() => setShowInput(true)}>
            Add input
          </button>
        )}
      </div>
      {error && (
        <div className="px-3 pb-3">
          <Alert>{error}</Alert>
        </div>
      )}
      {result && (
        <div className="border-t border-slate-200 bg-slate-50 px-3 py-2 text-sm" aria-label="Example result">
          <VerdictBadge verdict={result.verdict} />
          {result.compile_output && <pre className="mt-2 max-h-40 overflow-auto rounded bg-slate-900 p-2 text-xs text-red-200">{result.compile_output}</pre>}
          {result.stdout && <pre className="mt-2 max-h-48 overflow-auto rounded bg-slate-900 p-2 text-xs text-slate-100">{result.stdout}</pre>}
          {result.stderr && <pre className="mt-2 max-h-40 overflow-auto rounded bg-slate-900 p-2 text-xs text-amber-200">{result.stderr}</pre>}
          {result.message && <p className="mt-1 text-xs text-slate-600">{result.message}</p>}
        </div>
      )}
    </div>
  );
}
