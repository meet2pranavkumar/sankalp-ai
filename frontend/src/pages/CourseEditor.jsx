import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import { Alert, Button, Card, Field, inputClass } from "../ui.jsx";

const LANGUAGES = [
  ["c", "C"],
  ["cpp", "C++"],
  ["java", "Java"],
  ["python", "Python"],
];

// Returns a new id list with the item at `index` moved up (-1) or down (+1).
export function move(ids, index, direction) {
  const target = index + direction;
  if (target < 0 || target >= ids.length) return ids;
  const copy = [...ids];
  [copy[index], copy[target]] = [copy[target], copy[index]];
  return copy;
}

function ArrowButtons({ index, count, onMove, label }) {
  return (
    <span className="flex gap-1">
      <button type="button" aria-label={`Move ${label} up`} disabled={index === 0} onClick={() => onMove(-1)} className="rounded border border-slate-300 px-2 text-xs disabled:opacity-30">
        ↑
      </button>
      <button type="button" aria-label={`Move ${label} down`} disabled={index === count - 1} onClick={() => onMove(1)} className="rounded border border-slate-300 px-2 text-xs disabled:opacity-30">
        ↓
      </button>
    </span>
  );
}

function UnitBlock({ unit, index, unitIds, courseId, run }) {
  const count = unitIds.length;
  const [title, setTitle] = useState(unit.title);
  const [newLesson, setNewLesson] = useState("");
  useEffect(() => setTitle(unit.title), [unit.title]);

  const lessonIds = unit.lessons.map((l) => l.id);
  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <input aria-label={`Name of unit ${index + 1}`} className={`${inputClass} !w-64`} value={title} onChange={(e) => setTitle(e.target.value)} />
        <Button variant="secondary" disabled={!title.trim() || title === unit.title} onClick={() => run(() => api.renameUnit(unit.id, title))}>
          Rename
        </Button>
        <ArrowButtons index={index} count={count} label={`unit ${index + 1}`} onMove={(d) => run(() => api.reorderUnits(courseId, move(unitIds, index, d)))} />
        <Button
          variant="danger"
          className="ml-auto"
          onClick={() => window.confirm(`Delete "${unit.title}" and all its lessons?`) && run(() => api.deleteUnit(unit.id))}
        >
          Delete unit
        </Button>
      </div>

      <ul className="mt-3 divide-y divide-slate-100 text-sm">
        {unit.lessons.map((lesson, i) => (
          <li key={lesson.id} className="flex items-center gap-2 py-2">
            <Link to={`/lessons/${lesson.id}/edit`} className="text-indigo-700 underline">
              {lesson.title}
            </Link>
            <span className="ml-auto flex items-center gap-2">
              <ArrowButtons index={i} count={unit.lessons.length} label={`lesson ${lesson.title}`} onMove={(d) => run(() => api.reorderLessons(unit.id, move(lessonIds, i, d)))} />
              <button
                type="button"
                className="text-red-700 underline"
                aria-label={`Delete lesson ${lesson.title}`}
                onClick={() => window.confirm(`Delete the lesson "${lesson.title}"?`) && run(() => api.deleteLesson(lesson.id))}
              >
                Delete
              </button>
            </span>
          </li>
        ))}
        {unit.lessons.length === 0 && <li className="py-2 text-slate-500">No lessons yet.</li>}
      </ul>

      <form
        className="mt-3 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          run(() => api.addLesson(unit.id, newLesson)).then(() => setNewLesson(""));
        }}
      >
        <input aria-label={`New lesson in unit ${index + 1}`} placeholder="New lesson title" className={`${inputClass} !w-64`} value={newLesson} onChange={(e) => setNewLesson(e.target.value)} />
        <Button type="submit" variant="secondary" disabled={!newLesson.trim()}>
          Add lesson
        </Button>
      </form>
    </Card>
  );
}

export default function CourseEditor() {
  const { id } = useParams(); // no id = a new course
  const navigate = useNavigate();
  const [course, setCourse] = useState(null);
  const [form, setForm] = useState({ title: "", description: "", language: "c" });
  const [newUnit, setNewUnit] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (!id) return;
    api
      .getCourse(id)
      .then((c) => {
        if (!c.can_edit) {
          setError("You are not allowed to edit this course. Use \"Make my own copy\" on the course page.");
          return;
        }
        setCourse(c);
        setForm({ title: c.title, description: c.description, language: c.language });
      })
      .catch((e) => setError(e.message));
  }, [id]);

  // Runs one change, then shows the new state of the course.
  const run = async (action) => {
    setError("");
    setNotice("");
    try {
      const updated = await action();
      if (updated && updated.units) setCourse(updated);
      return updated;
    } catch (err) {
      setError(err.message);
      return null;
    }
  };

  const setF = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  async function saveDetails(e) {
    e.preventDefault();
    if (!id) {
      const created = await run(() => api.createCourse(form));
      if (created) navigate(`/courses/${created.id}/edit`);
      return;
    }
    const saved = await run(() => api.updateCourse(id, form));
    if (saved) setNotice("Saved.");
  }

  async function removeCourse() {
    if (!window.confirm(`Delete the course "${course.title}"? All lessons and student progress in it will be lost.`)) return;
    try {
      await api.deleteCourse(id);
      navigate("/courses");
    } catch (err) {
      setError(err.message);
    }
  }

  if (id && !course) {
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
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-slate-900">{id ? "Edit course" : "New course"}</h1>
      {error && <Alert>{error}</Alert>}
      {notice && <Alert kind="ok">{notice}</Alert>}

      <Card title="Course details">
        <form onSubmit={saveDetails} className="space-y-3">
          <Field label="Title">
            <input required className={inputClass} value={form.title} onChange={setF("title")} />
          </Field>
          <Field label="Description">
            <textarea rows={3} className={inputClass} value={form.description} onChange={setF("description")} />
          </Field>
          <Field label="Main language">
            <select className={`${inputClass} !w-auto`} value={form.language} onChange={setF("language")}>
              {LANGUAGES.map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit">{id ? "Save details" : "Create course"}</Button>
            {course && (
              <>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => run(() => api.updateCourse(id, { is_published: !course.is_published }))}
                >
                  {course.is_published ? "Unpublish" : "Publish"}
                </Button>
                <span className="text-sm text-slate-500">{course.is_published ? "Students can see this course." : "Draft: only you and admins can see it."}</span>
                <Link to={`/courses/${id}`} className="text-sm text-indigo-700 underline">
                  View course
                </Link>
              </>
            )}
          </div>
        </form>
      </Card>

      {course && (
        <>
          {course.units.map((unit, i) => (
            <UnitBlock key={unit.id} unit={unit} index={i} unitIds={course.units.map((u) => u.id)} courseId={course.id} run={run} />
          ))}
          <Card title="Add a unit">
            <form
              className="flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                run(() => api.addUnit(id, newUnit)).then(() => setNewUnit(""));
              }}
            >
              <input aria-label="New unit title" placeholder="Unit title, for example: Loops" className={`${inputClass} !w-72`} value={newUnit} onChange={(e) => setNewUnit(e.target.value)} />
              <Button type="submit" variant="secondary" disabled={!newUnit.trim()}>
                Add unit
              </Button>
            </form>
          </Card>
          <div>
            <Button variant="danger" onClick={removeCourse}>
              Delete this course
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
