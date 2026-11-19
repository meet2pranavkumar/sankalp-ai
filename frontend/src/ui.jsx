// Small shared pieces so every page looks the same.
export function Card({ title, children, className = "" }) {
  return (
    <section className={`rounded-lg border border-slate-200 bg-white p-4 shadow-sm ${className}`}>
      {title && <h2 className="mb-3 text-base font-semibold text-slate-900">{title}</h2>}
      {children}
    </section>
  );
}

export function Alert({ kind = "error", children }) {
  const colors =
    kind === "error"
      ? "border-red-200 bg-red-50 text-red-800"
      : "border-emerald-200 bg-emerald-50 text-emerald-800";
  return (
    <div role={kind === "error" ? "alert" : "status"} className={`rounded border px-3 py-2 text-sm ${colors}`}>
      {children}
    </div>
  );
}

export function Field({ label, children }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block font-medium text-slate-700">{label}</span>
      {children}
    </label>
  );
}

export const inputClass =
  "w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500";

export function Button({ children, variant = "primary", className = "", ...props }) {
  const styles = {
    primary: "bg-indigo-600 text-white hover:bg-indigo-700 disabled:bg-indigo-300",
    secondary: "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-50",
    danger: "border border-red-300 bg-white text-red-700 hover:bg-red-50 disabled:opacity-50",
  };
  return (
    <button
      className={`rounded px-3 py-2 text-sm font-medium ${styles[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

export const roleLabel = {
  student: "Student",
  teacher: "Teacher",
  admin: "College admin",
  super_admin: "Platform owner",
};

export const verdictInfo = {
  accepted: { label: "Accepted", color: "bg-emerald-100 text-emerald-800" },
  ok: { label: "Finished", color: "bg-emerald-100 text-emerald-800" },
  wrong_answer: { label: "Wrong answer", color: "bg-red-100 text-red-800" },
  time_limit: { label: "Time limit exceeded", color: "bg-amber-100 text-amber-800" },
  runtime_error: { label: "Runtime error", color: "bg-red-100 text-red-800" },
  compile_error: { label: "Compilation error", color: "bg-red-100 text-red-800" },
  internal_error: { label: "Judge problem (not your fault)", color: "bg-slate-200 text-slate-800" },
};

export function VerdictBadge({ verdict }) {
  const info = verdictInfo[verdict] || { label: verdict, color: "bg-slate-100 text-slate-700" };
  return <span className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${info.color}`}>{info.label}</span>;
}

export const difficultyColor = {
  easy: "text-emerald-700",
  medium: "text-amber-700",
  hard: "text-red-700",
};

export function ProgressBar({ done, total }) {
  const percent = total === 0 ? 0 : Math.round((done / total) * 100);
  return (
    <div>
      <div
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Course progress"
        className="h-2 w-full overflow-hidden rounded bg-slate-200"
      >
        <div className="h-full bg-emerald-500" style={{ width: `${percent}%` }} />
      </div>
      <p className="mt-1 text-xs text-slate-500">
        {done} of {total} lessons done
      </p>
    </div>
  );
}

export function Badge({ children, color = "bg-slate-100 text-slate-700" }) {
  return <span className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${color}`}>{children}</span>;
}
