import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";
import LessonContent from "../LessonContent.jsx";
import { Alert, Button, Card } from "../ui.jsx";

export default function LessonPage() {
  const { id } = useParams();
  const [lesson, setLesson] = useState(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setLesson(null);
    setError("");
    window.scrollTo?.(0, 0);
    api
      .getLesson(id)
      .then(setLesson)
      .catch((e) => setError(e.message));
  }, [id]);

  async function toggleDone() {
    setError("");
    setSaving(true);
    try {
      if (lesson.completed) await api.uncompleteLesson(id);
      else await api.completeLesson(id);
      setLesson({ ...lesson, completed: !lesson.completed });
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  if (error && !lesson) {
    return (
      <div className="space-y-3">
        <Alert>{error}</Alert>
        <Link to="/courses" className="text-indigo-700 underline">
          Back to courses
        </Link>
      </div>
    );
  }
  if (!lesson) return <p className="text-slate-500">Loading…</p>;

  const nav = "rounded border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50";

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <p className="text-sm text-slate-500">
        <Link to={`/courses/${lesson.course_id}`} className="text-indigo-700 underline">
          {lesson.course_title}
        </Link>{" "}
        › {lesson.unit_title}
      </p>
      <Card>
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold text-slate-900">{lesson.title}</h1>
          {lesson.can_edit && (
            <Link to={`/lessons/${lesson.id}/edit`} className="text-sm text-indigo-700 underline">
              Edit
            </Link>
          )}
        </div>
        {lesson.video_url && (
          <p className="mb-3">
            <a href={lesson.video_url} target="_blank" rel="noopener noreferrer" className="inline-block rounded bg-slate-800 px-3 py-1.5 text-sm text-white hover:bg-slate-700">
              Watch the video
            </a>
          </p>
        )}
        {lesson.content_md.trim() ? (
          <LessonContent markdown={lesson.content_md} />
        ) : (
          <p className="text-sm text-slate-500">This lesson has no text yet.</p>
        )}
      </Card>

      {error && <Alert>{error}</Alert>}
      <div className="flex flex-wrap items-center justify-between gap-3">
        {lesson.prev_lesson_id ? (
          <Link to={`/lessons/${lesson.prev_lesson_id}`} className={nav}>
            ← Previous
          </Link>
        ) : (
          <span />
        )}
        <Button variant={lesson.completed ? "secondary" : "primary"} disabled={saving} onClick={toggleDone}>
          {lesson.completed ? "Done ✓ (undo)" : "Mark as done"}
        </Button>
        {lesson.next_lesson_id ? (
          <Link to={`/lessons/${lesson.next_lesson_id}`} className={nav}>
            Next →
          </Link>
        ) : (
          <Link to={`/courses/${lesson.course_id}`} className={nav}>
            Back to course
          </Link>
        )}
      </div>
    </div>
  );
}
