import { useEffect, useState } from "react";
import { api } from "../api.js";
import StudentDashboard from "../StudentDashboard.jsx";
import { Alert } from "../ui.jsx";

export default function Progress() {
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api
      .myReport()
      .then(setReport)
      .catch((e) => setError(e.message));
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-slate-900">My progress</h1>
      {error && <Alert>{error}</Alert>}
      {!report && !error && <p className="text-slate-500">Loading…</p>}
      {report && <StudentDashboard report={report} />}
    </div>
  );
}
