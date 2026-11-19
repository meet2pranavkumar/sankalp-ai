import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import LessonContent from "../LessonContent.jsx";
import { Alert, Button, Card, Field, inputClass } from "../ui.jsx";

const HELP = "```c run\n#include <stdio.h>\nint main(void) {\n    printf(\"Hi\\n\");\n    return 0;\n}\n```\n```stdin\n(optional input for the example)\n```";

export default function LessonEditor() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [lesson, setLesson] = useState(null);
  const [title, setTitle] = useState("");
  const [video, setVideo] = useState("");
  const [content, setContent] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api
      .getLesson(id)
      .then((l) => {
        if (!l.can_edit) {
          setError("You are not allowed to edit this lesson.");
          return;
        }
        setLesson(l);
        setTitle(l.title);
        setVideo(l.video_url ?? "");
        setContent(l.content_md);
      })
      .catch((e) => setError(e.message));
  }, [id]);

  async function save(e) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      await api.updateLesson(id, { title, content_md: content, video_url: video.trim() || null });
      navigate(`/lessons/${id}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  if (!lesson) {
    return error ? (
      <div className="space-y-3">
        <Alert>{error}</Alert>
        <Link to="/courses" className="text-indigo-700 underline">
          Back to courses
        </Link>
      </div>
    ) : (
      <p className="text-slate-500">Loading…</p>
    );
  }

  return (
    <form onSubmit={save} className="space-y-4">
      <p className="text-sm text-slate-500">
        <Link to={`/courses/${lesson.course_id}/edit`} className="text-indigo-700 underline">
          {lesson.course_title}
        </Link>{" "}
        › {lesson.unit_title}
      </p>
      <h1 className="text-2xl font-bold text-slate-900">Edit lesson</h1>

      <Card>
        <div className="space-y-3">
          <Field label="Lesson title">
            <input required className={inputClass} value={title} onChange={(e) => setTitle(e.target.value)} />
          </Field>
          <Field label="Video link (optional, must start with https://)">
            <input className={inputClass} placeholder="https://..." value={video} onChange={(e) => setVideo(e.target.value)} />
          </Field>
          <Field label="Lesson text (Markdown)">
            <textarea rows={18} className={`${inputClass} font-mono`} value={content} onChange={(e) => setContent(e.target.value)} />
          </Field>
          <details className="text-sm text-slate-600">
            <summary className="cursor-pointer text-indigo-700">How do I add a code example with a Run button?</summary>
            <p className="mt-2">
              Write <code>run</code> after the language name on the first line of a code block. Students can change the code and run it.
              You can add a <code>stdin</code> block right after it to give the default input.
            </p>
            <pre className="mt-2 overflow-auto rounded bg-slate-100 p-2 text-xs">{HELP}</pre>
            <p className="mt-2">Languages that can run: c, cpp, java, python. A block without <code>run</code> is only shown, not run.</p>
          </details>
        </div>
      </Card>

      {error && <Alert>{error}</Alert>}
      <div className="flex gap-3">
        <Button type="submit" disabled={saving}>
          {saving ? "Saving…" : "Save lesson"}
        </Button>
        <Link to={`/lessons/${id}`} className="rounded border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
          Cancel
        </Link>
      </div>

      <Card title="Preview">
        {content.trim() ? <LessonContent markdown={content} /> : <p className="text-sm text-slate-500">Nothing to preview yet.</p>}
      </Card>
    </form>
  );
}
