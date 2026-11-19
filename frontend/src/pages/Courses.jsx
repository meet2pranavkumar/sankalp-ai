import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Alert, Badge, Card, ProgressBar } from "../ui.jsx";

export default function Courses() {
  const { user } = useAuth();
  const canCreate = ["teacher", "admin", "super_admin"].includes(user.role);
  const [courses, setCourses] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .listCourses()
      .then(setCourses)
      .catch((e) => setError(e.message));
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-slate-900">Courses</h1>
        {canCreate && (
          <Link to="/courses/new" className="rounded bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700">
            New course
          </Link>
        )}
      </div>
      {error && <Alert>{error}</Alert>}
      {courses === null ? (
        <p className="text-slate-500">Loading…</p>
      ) : courses.length === 0 ? (
        <Card>
          <p className="text-sm text-slate-600">
            There are no courses yet.
            {canCreate ? " Create one with the button above." : " Your teacher will publish courses here."}
          </p>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {courses.map((c) => (
            <Card key={c.id}>
              <div className="flex flex-wrap items-center gap-2">
                <Link to={`/courses/${c.id}`} className="text-lg font-semibold text-indigo-700 underline">
                  {c.title}
                </Link>
                {!c.is_published && <Badge color="bg-amber-100 text-amber-800">Draft</Badge>}
                {c.is_shared && <Badge color="bg-indigo-100 text-indigo-800">Starter course</Badge>}
              </div>
              <p className="mt-1 text-sm text-slate-600">{c.description}</p>
              <div className="mt-3">
                <ProgressBar done={c.completed_lessons} total={c.total_lessons} />
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
