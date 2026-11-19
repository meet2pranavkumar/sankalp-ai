import { lazy, Suspense, useState } from "react";

// Monaco (the VS Code editor) is big and loads from the internet, so it loads only when needed.
// On a slow connection the student can switch to a plain text box.
const Monaco = lazy(() => import("@monaco-editor/react"));
const SIMPLE_KEY = "sankalp_simple_editor";
const MONACO_LANGUAGE = { c: "c", cpp: "cpp", java: "java", python: "python" };

export default function CodeEditor({ language, value, onChange }) {
  const [simple, setSimple] = useState(() => localStorage.getItem(SIMPLE_KEY) === "1");

  const toggle = (e) => {
    setSimple(e.target.checked);
    localStorage.setItem(SIMPLE_KEY, e.target.checked ? "1" : "0");
  };

  return (
    <div>
      <label className="mb-1 flex items-center gap-2 text-xs text-slate-500">
        <input type="checkbox" checked={simple} onChange={toggle} />
        Simple editor (use this if the page is slow)
      </label>
      {simple ? (
        <textarea
          aria-label="Code editor"
          spellCheck={false}
          className="h-80 w-full rounded border border-slate-300 p-2 font-mono text-sm"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Tab") {
              e.preventDefault();
              const t = e.target;
              const next = value.slice(0, t.selectionStart) + "    " + value.slice(t.selectionEnd);
              onChange(next);
              requestAnimationFrame(() => (t.selectionStart = t.selectionEnd = t.selectionStart + 4));
            }
          }}
        />
      ) : (
        <div className="overflow-hidden rounded border border-slate-300">
          <Suspense fallback={<p className="p-4 text-sm text-slate-500">Loading editor…</p>}>
            <Monaco
              height="20rem"
              language={MONACO_LANGUAGE[language]}
              value={value}
              onChange={(v) => onChange(v ?? "")}
              options={{ minimap: { enabled: false }, fontSize: 14, scrollBeyondLastLine: false, automaticLayout: true }}
            />
          </Suspense>
        </div>
      )}
    </div>
  );
}
