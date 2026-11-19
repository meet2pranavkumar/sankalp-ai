import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Alert, Card, difficultyColor, inputClass } from "../ui.jsx";

export default function Problems() {
  const { user } = useAuth();
  const canCreate = ["teacher", "admin", "super_admin"].includes(user.role);
  const [problems, setProblems] = useState(null);
  const [difficulty, setDifficulty] = useState("");
  const [q, setQ] = useState("");
  const [tag, setTag] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => {
      api
        .listProblems({ difficulty, q, tag })
        .then(setProblems)
        .catch((e) => setError(e.message));
    }, 250); // wait a moment while the person is typing
    return () => clearTimeout(timer);
  }, [difficulty, q, tag]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-slate-900">Problems</h1>
        {canCreate && (
          <Link to="/problems/new" className="rounded bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700">
            New problem
          </Link>
        )}
      </div>
      {error && <Alert>{error}</Alert>}
      <Card>
        <div className="mb-3 flex flex-wrap gap-3">
          <input aria-label="Search by title" placeholder="Search by title" className={`${inputClass} !w-56`} value={q} onChange={(e) => setQ(e.target.value)} />
          <select aria-label="Filter by difficulty" className={`${inputClass} !w-auto`} value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
            <option value="">All levels</option>
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </select>
          <input aria-label="Filter by topic" placeholder="Topic (example: arrays)" className={`${inputClass} !w-48`} value={tag} onChange={(e) => setTag(e.target.value)} />
        </div>
        {problems === null ? (
          <p className="text-sm text-slate-500">Loading…</p>
        ) : problems.length === 0 ? (
          <p className="text-sm text-slate-500">No problems found.</p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {problems.map((p) => (
              <li key={p.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 text-sm">
                <span aria-label={p.solved ? "Solved" : "Not solved yet"} className="w-4 text-emerald-600">
                  {p.solved ? "✓" : ""}
                </span>
                <Link to={`/problems/${p.id}`} className="font-medium text-indigo-700 underline">
                  {p.title}
                </Link>
                <span className={`text-xs font-semibold uppercase ${difficultyColor[p.difficulty]}`}>{p.difficulty}</span>
                {p.tags.map((t) => (
                  <span key={t} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">
                    {t}
                  </span>
                ))}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
