import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Alert, Badge, Button, Card, ProgressBar } from "../ui.jsx";

export default function CoursePage() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const isStaff = ["teacher", "admin", "super_admin"].includes(user.role);
  const [course, setCourse] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .getCourse(id)
      .then(setCourse)
      .catch((e) => setError(e.message));
  }, [id]);

  async function togglePublish() {
    setError("");
    try {
      setCourse(await api.updateCourse(id, { is_published: !course.is_published }));
    } catch (err) {
      setError(err.message);
    }
  }

  async function copy() {
    setError("");
    try {
      const made = await api.duplicateCourse(id);
      navigate(`/courses/${made.id}/edit`);
    } catch (err) {
      setError(err.message);
    }
  }

  if (error && !course) {
    return (
      <div className="space-y-3">
        <Alert>{error}</Alert>
        <Link to="/courses" className="text-indigo-700 underline">
          Back to courses
        </Link>
      </div>
    );
  }
  if (!course) return <p className="text-slate-500">Loading…</p>;

  const lessons = course.units.flatMap((u) => u.lessons);
  const next = lessons.find((l) => !l.completed) ?? lessons[0];
  const started = course.completed_lessons > 0;

  return (
    <div className="space-y-4">
      <Link to="/courses" className="text-sm text-indigo-700 underline">
        ← All courses
      </Link>
      <Card>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-bold text-slate-900">{course.title}</h1>
          {!course.is_published && <Badge color="bg-amber-100 text-amber-800">Draft</Badge>}
          {course.is_shared && <Badge color="bg-indigo-100 text-indigo-800">Starter course</Badge>}
        </div>
        <p className="mt-2 text-sm text-slate-600">{course.description}</p>
        <div className="mt-4 max-w-md">
          <ProgressBar done={course.completed_lessons} total={course.total_lessons} />
        </div>
        <div className="mt-4 flex flex-wrap gap-3">
          {next && (
            <Link to={`/lessons/${next.id}`} className="rounded bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700">
              {started ? "Continue learning" : "Start the course"}
            </Link>
          )}
          {course.can_edit && (
            <>
              <Link to={`/courses/${course.id}/edit`} className="rounded border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
                Edit course
              </Link>
              <Button variant="secondary" onClick={togglePublish}>
                {course.is_published ? "Unpublish" : "Publish"}
              </Button>
            </>
          )}
          {isStaff && (
            <Button variant="secondary" onClick={copy}>
              Make my own copy
            </Button>
          )}
        </div>
        {isStaff && course.is_shared && !course.can_edit && (
          <p className="mt-3 text-xs text-slate-500">
            This is the shared starter course. To change it for your college, press &quot;Make my own copy&quot;.
          </p>
        )}
        {error && (
          <div className="mt-3">
            <Alert>{error}</Alert>
          </div>
        )}
      </Card>

      {course.units.length === 0 ? (
        <Card>
          <p className="text-sm text-slate-500">This course has no lessons yet.</p>
        </Card>
      ) : (
        course.units.map((unit) => (
          <Card key={unit.id} title={unit.title}>
            <ul className="divide-y divide-slate-100">
              {unit.lessons.map((lesson) => (
                <li key={lesson.id} className="flex items-center gap-3 py-2 text-sm">
                  <span aria-label={lesson.completed ? "Done" : "Not done"} className="w-4 text-emerald-600">
                    {lesson.completed ? "✓" : ""}
                  </span>
                  <Link to={`/lessons/${lesson.id}`} className="text-indigo-700 underline">
                    {lesson.title}
                  </Link>
                </li>
              ))}
              {unit.lessons.length === 0 && <li className="py-2 text-sm text-slate-500">No lessons in this unit yet.</li>}
            </ul>
          </Card>
        ))
      )}
    </div>
  );
}
