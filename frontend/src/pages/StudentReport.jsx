import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";
import StudentDashboard from "../StudentDashboard.jsx";
import { Alert } from "../ui.jsx";

export default function StudentReport() {
  const { id } = useParams();
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api
      .studentReport(id)
      .then(setReport)
      .catch((e) => setError(e.message));
  }, [id]);

  return (
    <div className="space-y-4">
      <Link to="/reports" className="text-sm text-indigo-700 underline">
        ← All classes
      </Link>
      {error && <Alert>{error}</Alert>}
      {!report && !error && <p className="text-slate-500">Loading…</p>}
      {report && (
        <>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">{report.name}</h1>
            <p className="text-sm text-slate-500">{report.email}</p>
          </div>
          <StudentDashboard report={report} staffView />
        </>
      )}
    </div>
  );
}
