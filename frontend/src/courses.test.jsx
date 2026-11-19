import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { splitLesson } from "./lessonBlocks.js";
import { move } from "./pages/CourseEditor.jsx";
import { mockBackend, renderApp, users } from "./testUtils.jsx";

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

const COURSE = {
  id: 3, title: "C Programming Basics", description: "Learn C from zero.", language: "c",
  is_published: true, is_shared: false, can_edit: false, total_lessons: 3, completed_lessons: 1,
  units: [
    { id: 10, title: "Basics", position: 1, lessons: [
      { id: 100, title: "Hello", position: 1, completed: true },
      { id: 101, title: "Variables", position: 2, completed: false },
    ] },
    { id: 11, title: "Loops", position: 2, lessons: [{ id: 102, title: "While", position: 1, completed: false }] },
  ],
};
const summary = (c) => ({ id: c.id, title: c.title, description: c.description, language: c.language, is_published: c.is_published, is_shared: c.is_shared, can_edit: c.can_edit, total_lessons: c.total_lessons, completed_lessons: c.completed_lessons });

const LESSON = {
  id: 101, unit_id: 10, unit_title: "Basics", course_id: 3, course_title: "C Programming Basics",
  title: "Variables", content_md: "Intro text.", video_url: null, position: 2, completed: false, can_edit: false,
  prev_lesson_id: 100, next_lesson_id: 102,
};

// ---------------------------------------------------------------- the example splitter
describe("splitLesson", () => {
  it("finds runnable examples and their input, and keeps the text around them", () => {
    const md = "Before\n```c run\nint main(){}\n```\n```stdin\n5 7\n```\nAfter\n```c\nonly shown\n```\n```python run\nprint(1)\n```\n";
    const parts = splitLesson(md);
    expect(parts.map((p) => p.type)).toEqual(["markdown", "run", "markdown", "run"]);
    expect(parts[0].text).toBe("Before\n");
    expect(parts[1]).toEqual({ type: "run", language: "c", code: "int main(){}", stdin: "5 7" });
    expect(parts[2].text).toContain("only shown"); // a block without "run" stays ordinary text
    expect(parts[3]).toMatchObject({ language: "python", code: "print(1)", stdin: "" });
  });

  it("does not attach an input block that is not directly after the example", () => {
    const parts = splitLesson("```c run\nA\n```\n\nwords\n\n```stdin\n1\n```\n");
    expect(parts[0].stdin).toBe("");
    expect(parts.some((p) => p.type === "markdown" && p.text.includes("stdin"))).toBe(true);
  });

  it("leaves unknown languages and plain text alone", () => {
    expect(splitLesson("just text")).toEqual([{ type: "markdown", text: "just text" }]);
    expect(splitLesson("```cobol run\nX\n```").every((p) => p.type === "markdown")).toBe(true);
    expect(splitLesson("")).toEqual([]);
  });
});

describe("move", () => {
  it("swaps neighbours and stops at the ends", () => {
    expect(move([1, 2, 3], 1, -1)).toEqual([2, 1, 3]);
    expect(move([1, 2, 3], 1, 1)).toEqual([1, 3, 2]);
    expect(move([1, 2, 3], 0, -1)).toEqual([1, 2, 3]);
    expect(move([1, 2, 3], 2, 1)).toEqual([1, 2, 3]);
  });
});

// ---------------------------------------------------------------- course list
describe("course list", () => {
  const draft = { ...COURSE, id: 4, title: "My draft", is_published: false, can_edit: true, total_lessons: 0, completed_lessons: 0 };
  const starter = { ...COURSE, id: 5, title: "Starter", is_shared: true };

  it("shows courses with progress and badges", async () => {
    mockBackend({ "GET /auth/me": () => users.teacher, "GET /courses": () => [summary(COURSE), summary(draft), summary(starter)] });
    renderApp("/courses", { token: "t" });
    expect(await screen.findByRole("link", { name: "C Programming Basics" })).toHaveAttribute("href", "/courses/3");
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getByText("Starter course")).toBeInTheDocument();
    expect(screen.getAllByText("1 of 3 lessons done").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("progressbar")[0]).toHaveAttribute("aria-valuenow", "33");
  });

  it("gives staff a New course button but not students", async () => {
    mockBackend({ "GET /auth/me": () => users.student, "GET /courses": () => [summary(COURSE)] });
    renderApp("/courses", { token: "t" });
    await screen.findByText("C Programming Basics");
    expect(screen.queryByRole("link", { name: "New course" })).not.toBeInTheDocument();
  });

  it("explains an empty list to each kind of user", async () => {
    mockBackend({ "GET /auth/me": () => users.student, "GET /courses": () => [] });
    const first = renderApp("/courses", { token: "t" });
    expect(await screen.findByText(/Your teacher will publish courses/)).toBeInTheDocument();
    first.unmount();
    vi.restoreAllMocks();
    mockBackend({ "GET /auth/me": () => users.teacher, "GET /courses": () => [] });
    renderApp("/courses", { token: "t" });
    expect(await screen.findByText(/Create one with the button above/)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------- course page
describe("course page", () => {
  const backend = (course = COURSE, me = users.student, extra = {}) =>
    mockBackend({ "GET /auth/me": () => me, "GET /courses/3": () => course, ...extra });

  it("shows units, lessons and ticks for finished lessons", async () => {
    backend();
    renderApp("/courses/3", { token: "t" });
    expect(await screen.findByRole("heading", { name: "C Programming Basics" })).toBeInTheDocument();
    expect(screen.getByText("Basics")).toBeInTheDocument();
    expect(screen.getAllByLabelText("Done")).toHaveLength(1);
    expect(screen.getAllByLabelText("Not done")).toHaveLength(2);
    expect(screen.getByText("1 of 3 lessons done")).toBeInTheDocument();
  });

  it("Continue learning goes to the first lesson that is not done yet", async () => {
    backend();
    renderApp("/courses/3", { token: "t" });
    expect(await screen.findByRole("link", { name: "Continue learning" })).toHaveAttribute("href", "/lessons/101");
  });

  it("offers Start the course when nothing is done", async () => {
    backend({ ...COURSE, completed_lessons: 0, units: COURSE.units.map((u) => ({ ...u, lessons: u.lessons.map((l) => ({ ...l, completed: false })) })) });
    renderApp("/courses/3", { token: "t" });
    expect(await screen.findByRole("link", { name: "Start the course" })).toHaveAttribute("href", "/lessons/100");
  });

  it("students see no editing buttons", async () => {
    backend();
    renderApp("/courses/3", { token: "t" });
    await screen.findByText("Basics");
    for (const name of ["Edit course", "Publish", "Unpublish", "Make my own copy"]) {
      expect(screen.queryByRole("button", { name }) ?? screen.queryByRole("link", { name })).not.toBeInTheDocument();
    }
  });

  it("a teacher can copy the shared course and lands in the editor of the copy", async () => {
    let called = false;
    backend({ ...COURSE, is_shared: true }, users.teacher, {
      "POST /courses/3/duplicate": () => {
        called = true;
        return [201, { ...COURSE, id: 9, title: "C Programming Basics (copy)", can_edit: true, is_published: false }];
      },
      "GET /courses/9": () => ({ ...COURSE, id: 9, title: "C Programming Basics (copy)", can_edit: true, is_published: false }),
    });
    renderApp("/courses/3", { token: "t" });
    expect(await screen.findByText(/shared starter course/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Make my own copy" }));
    await waitFor(() => expect(called).toBe(true));
    expect(await screen.findByRole("heading", { name: "Edit course" })).toBeInTheDocument();
    expect(screen.getByLabelText("Title")).toHaveValue("C Programming Basics (copy)");
  });

  it("an author can publish and unpublish", async () => {
    let sent = null;
    backend({ ...COURSE, can_edit: true, is_published: false }, users.teacher, {
      "PATCH /courses/3": (opts) => {
        sent = JSON.parse(opts.body);
        return { ...COURSE, can_edit: true, is_published: true };
      },
    });
    renderApp("/courses/3", { token: "t" });
    expect(await screen.findByText("Draft")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Publish" }));
    expect(await screen.findByRole("button", { name: "Unpublish" })).toBeInTheDocument();
    expect(sent).toEqual({ is_published: true });
    expect(screen.queryByText("Draft")).not.toBeInTheDocument();
  });

  it("says clearly when the course cannot be found", async () => {
    mockBackend({ "GET /auth/me": () => users.student, "GET /courses/3": () => [404, { detail: "Course not found." }] });
    renderApp("/courses/3", { token: "t" });
    expect(await screen.findByRole("alert")).toHaveTextContent("Course not found.");
  });
});

// ---------------------------------------------------------------- lesson page
describe("lesson page", () => {
  const backend = (lesson = LESSON, extra = {}, me = users.student) =>
    mockBackend({ "GET /auth/me": () => me, "GET /lessons/101": () => lesson, ...extra });

  it("shows the lesson with a Markdown table and links to the neighbours", async () => {
    backend({ ...LESSON, content_md: "## Types\n\n| Type | Holds |\n|---|---|\n| `int` | whole numbers |\n" });
    renderApp("/lessons/101", { token: "t" });
    expect(await screen.findByRole("heading", { name: "Variables" })).toBeInTheDocument();
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Holds" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "← Previous" })).toHaveAttribute("href", "/lessons/100");
    expect(screen.getByRole("link", { name: "Next →" })).toHaveAttribute("href", "/lessons/102");
    expect(screen.getByRole("link", { name: "C Programming Basics" })).toHaveAttribute("href", "/courses/3");
  });

  it("on the last lesson the next button leads back to the course", async () => {
    backend({ ...LESSON, next_lesson_id: null });
    renderApp("/lessons/101", { token: "t" });
    expect(await screen.findByRole("link", { name: "Back to course" })).toHaveAttribute("href", "/courses/3");
  });

  it("marks a lesson as done and lets the student undo it", async () => {
    const calls = [];
    backend(LESSON, {
      "POST /lessons/101/complete": () => { calls.push("done"); return [204, null]; },
      "DELETE /lessons/101/complete": () => { calls.push("undo"); return [204, null]; },
    });
    renderApp("/lessons/101", { token: "t" });
    await userEvent.click(await screen.findByRole("button", { name: "Mark as done" }));
    expect(await screen.findByRole("button", { name: "Done ✓ (undo)" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Done ✓ (undo)" }));
    expect(await screen.findByRole("button", { name: "Mark as done" })).toBeInTheDocument();
    expect(calls).toEqual(["done", "undo"]);
  });

  it("shows a video link that opens safely in a new tab", async () => {
    backend({ ...LESSON, video_url: "https://example.com/watch" });
    renderApp("/lessons/101", { token: "t" });
    const link = await screen.findByRole("link", { name: "Watch the video" });
    expect(link).toHaveAttribute("href", "https://example.com/watch");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link.getAttribute("rel")).toContain("noopener");
  });

  it("shows an Edit link only to people who can edit", async () => {
    backend({ ...LESSON, can_edit: true }, {}, users.teacher);
    renderApp("/lessons/101", { token: "t" });
    expect(await screen.findByRole("link", { name: "Edit" })).toHaveAttribute("href", "/lessons/101/edit");
  });

  it("says so when a lesson has no text yet, and when it cannot be found", async () => {
    backend({ ...LESSON, content_md: "  " });
    const first = renderApp("/lessons/101", { token: "t" });
    expect(await screen.findByText("This lesson has no text yet.")).toBeInTheDocument();
    first.unmount();
    vi.restoreAllMocks();
    mockBackend({ "GET /auth/me": () => users.student, "GET /lessons/101": () => [404, { detail: "Lesson not found." }] });
    renderApp("/lessons/101", { token: "t" });
    expect(await screen.findByRole("alert")).toHaveTextContent("Lesson not found.");
  });

  describe("runnable examples", () => {
    const withExample = { ...LESSON, content_md: "Try it:\n```c run\nint main(){}\n```\n```stdin\n5 7\n```\n" };

    it("runs the example with its default input and shows the output", async () => {
      let sent = null;
      backend(withExample, {
        "POST /run": (opts) => { sent = JSON.parse(opts.body); return [202, { id: 70, status: "queued" }]; },
        "GET /submissions/70": () => ({ id: 70, status: "done", verdict: "ok", stdout: "Sum = 12\n", stderr: "", compile_output: "" }),
      });
      renderApp("/lessons/101", { token: "t" });
      expect(await screen.findByLabelText("Example input")).toHaveValue("5 7");
      await userEvent.click(screen.getByRole("button", { name: "Run" }));
      const result = await screen.findByLabelText("Example result");
      expect(within(result).getByText("Sum = 12")).toBeInTheDocument();
      expect(sent).toEqual({ language: "c", source_code: "int main(){}", stdin: "5 7" });
    });

    it("lets the student change the code, run it, and reset it", async () => {
      let sentCode = null;
      backend(withExample, {
        "POST /run": (opts) => { sentCode = JSON.parse(opts.body).source_code; return [202, { id: 71, status: "queued" }]; },
        "GET /submissions/71": () => ({ id: 71, status: "done", verdict: "ok", stdout: "hi\n" }),
      });
      renderApp("/lessons/101", { token: "t" });
      const code = await screen.findByLabelText("Example code");
      expect(screen.queryByRole("button", { name: "Reset" })).not.toBeInTheDocument();
      await userEvent.clear(code);
      await userEvent.click(code);
      await userEvent.paste("my own code");
      await userEvent.click(screen.getByRole("button", { name: "Run" }));
      await screen.findByLabelText("Example result");
      expect(sentCode).toBe("my own code");
      await userEvent.click(screen.getByRole("button", { name: "Reset" }));
      expect(screen.getByLabelText("Example code")).toHaveValue("int main(){}");
      expect(screen.queryByLabelText("Example result")).not.toBeInTheDocument();
    });

    it("shows compiler errors", async () => {
      backend(withExample, {
        "POST /run": () => [202, { id: 72, status: "queued" }],
        "GET /submissions/72": () => ({ id: 72, status: "done", verdict: "compile_error", compile_output: "main.c:1: error: boom" }),
      });
      renderApp("/lessons/101", { token: "t" });
      await userEvent.click(await screen.findByRole("button", { name: "Run" }));
      expect(await screen.findByText("Compilation error")).toBeInTheDocument();
      expect(screen.getByText(/error: boom/)).toBeInTheDocument();
    });

    it("shows the server's message when the student runs too fast", async () => {
      backend(withExample, { "POST /run": () => [429, { detail: "Please wait 2 more second(s) before trying again." }] });
      renderApp("/lessons/101", { token: "t" });
      await userEvent.click(await screen.findByRole("button", { name: "Run" }));
      expect(await screen.findByRole("alert")).toHaveTextContent("Please wait 2 more second(s)");
      expect(screen.getByRole("button", { name: "Run" })).toBeEnabled();
    });

    it("hides the input box until it is needed", async () => {
      backend({ ...LESSON, content_md: "```python run\nprint(1)\n```" });
      renderApp("/lessons/101", { token: "t" });
      await screen.findByLabelText("Example code");
      expect(screen.queryByLabelText("Example input")).not.toBeInTheDocument();
      await userEvent.click(screen.getByRole("button", { name: "Add input" }));
      expect(screen.getByLabelText("Example input")).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------- course editor
describe("course editor", () => {
  const EDITABLE = { ...COURSE, can_edit: true, is_published: false };

  it("creates a course and moves on to its editor", async () => {
    let sent = null;
    mockBackend({
      "GET /auth/me": () => users.teacher,
      "POST /courses": (opts) => { sent = JSON.parse(opts.body); return [201, { ...EDITABLE, id: 8, units: [] }]; },
      "GET /courses/8": () => ({ ...EDITABLE, id: 8, units: [] }),
    });
    renderApp("/courses/new", { token: "t" });
    await userEvent.type(await screen.findByLabelText("Title"), "Python Basics");
    await userEvent.selectOptions(screen.getByLabelText("Main language"), "python");
    await userEvent.click(screen.getByRole("button", { name: "Create course" }));
    await waitFor(() => expect(sent).toEqual({ title: "Python Basics", description: "", language: "python" }));
    expect(await screen.findByRole("heading", { name: "Edit course" })).toBeInTheDocument();
  });

  it("shows the server's message for an invalid course", async () => {
    mockBackend({ "GET /auth/me": () => users.teacher, "POST /courses": () => [422, { detail: [{ loc: ["body", "title"], msg: "String should have at least 1 character" }] }] });
    renderApp("/courses/new", { token: "t" });
    await userEvent.type(await screen.findByLabelText("Title"), " ");
    await userEvent.click(screen.getByRole("button", { name: "Create course" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("title:");
  });

  it("saves the details of an existing course", async () => {
    let sent = null;
    mockBackend({
      "GET /auth/me": () => users.teacher,
      "GET /courses/3": () => EDITABLE,
      "PATCH /courses/3": (opts) => { sent = JSON.parse(opts.body); return { ...EDITABLE, title: "New title" }; },
    });
    renderApp("/courses/3/edit", { token: "t" });
    const title = await screen.findByLabelText("Title");
    await userEvent.clear(title);
    await userEvent.type(title, "New title");
    await userEvent.click(screen.getByRole("button", { name: "Save details" }));
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
    expect(sent).toMatchObject({ title: "New title", language: "c" });
  });

  it("adds a unit and a lesson", async () => {
    const withUnit = { ...EDITABLE, units: [...EDITABLE.units, { id: 12, title: "Functions", position: 3, lessons: [] }] };
    const withLesson = { ...withUnit, units: withUnit.units.map((u) => (u.id === 12 ? { ...u, lessons: [{ id: 200, title: "Intro", position: 1, completed: false }] } : u)) };
    const bodies = [];
    mockBackend({
      "GET /auth/me": () => users.teacher,
      "GET /courses/3": () => EDITABLE,
      "POST /courses/3/units": (o) => { bodies.push(JSON.parse(o.body)); return [201, withUnit]; },
      "POST /units/12/lessons": (o) => { bodies.push(JSON.parse(o.body)); return [201, withLesson]; },
    });
    renderApp("/courses/3/edit", { token: "t" });
    await userEvent.type(await screen.findByLabelText("New unit title"), "Functions");
    await userEvent.click(screen.getByRole("button", { name: "Add unit" }));
    await userEvent.type(await screen.findByLabelText("New lesson in unit 3"), "Intro");
    await userEvent.click(within(screen.getByLabelText("New lesson in unit 3").closest("form")).getByRole("button", { name: "Add lesson" }));
    expect(await screen.findByRole("link", { name: "Intro" })).toHaveAttribute("href", "/lessons/200/edit");
    expect(bodies).toEqual([{ title: "Functions" }, { title: "Intro" }]);
  });

  it("renames a unit", async () => {
    let sent = null;
    mockBackend({
      "GET /auth/me": () => users.teacher,
      "GET /courses/3": () => EDITABLE,
      "PATCH /units/10": (o) => { sent = JSON.parse(o.body); return { ...EDITABLE, units: [{ ...EDITABLE.units[0], title: "Start here" }, EDITABLE.units[1]] }; },
    });
    renderApp("/courses/3/edit", { token: "t" });
    const name = await screen.findByLabelText("Name of unit 1");
    const rename = within(name.closest("div")).getByRole("button", { name: "Rename" });
    expect(rename).toBeDisabled(); // nothing changed yet
    await userEvent.clear(name);
    await userEvent.type(name, "Start here");
    await userEvent.click(rename);
    await waitFor(() => expect(sent).toEqual({ title: "Start here" }));
    expect(await screen.findByLabelText("Name of unit 1")).toHaveValue("Start here");
  });

  it("changes the order of units and lessons", async () => {
    const orders = [];
    mockBackend({
      "GET /auth/me": () => users.teacher,
      "GET /courses/3": () => EDITABLE,
      "PUT /courses/3/units/order": (o) => { orders.push(["units", JSON.parse(o.body).ids]); return EDITABLE; },
      "PUT /units/10/lessons/order": (o) => { orders.push(["lessons", JSON.parse(o.body).ids]); return EDITABLE; },
    });
    renderApp("/courses/3/edit", { token: "t" });
    await screen.findByLabelText("Name of unit 1");
    expect(screen.getByRole("button", { name: "Move unit 1 up" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Move unit 2 down" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Move unit 1 down" }));
    await userEvent.click(screen.getByRole("button", { name: "Move lesson Hello down" }));
    await waitFor(() => expect(orders).toHaveLength(2));
    expect(orders).toEqual([["units", [11, 10]], ["lessons", [101, 100]]]);
  });

  it("asks before deleting, and deletes only when the person agrees", async () => {
    const confirm = vi.spyOn(window, "confirm");
    let deleted = [];
    mockBackend({
      "GET /auth/me": () => users.teacher,
      "GET /courses/3": () => EDITABLE,
      "DELETE /lessons/100": () => { deleted.push("lesson"); return { ...EDITABLE, units: [{ ...EDITABLE.units[0], lessons: [EDITABLE.units[0].lessons[1]] }, EDITABLE.units[1]] }; },
      "DELETE /units/11": () => { deleted.push("unit"); return { ...EDITABLE, units: [EDITABLE.units[0]] }; },
    });
    renderApp("/courses/3/edit", { token: "t" });
    await screen.findByLabelText("Name of unit 1");
    confirm.mockReturnValueOnce(false);
    await userEvent.click(screen.getByRole("button", { name: "Delete lesson Hello" }));
    expect(deleted).toEqual([]);
    confirm.mockReturnValueOnce(true);
    await userEvent.click(screen.getByRole("button", { name: "Delete lesson Hello" }));
    await waitFor(() => expect(screen.queryByRole("link", { name: "Hello" })).not.toBeInTheDocument());
    confirm.mockReturnValueOnce(true);
    await userEvent.click(screen.getAllByRole("button", { name: "Delete unit" })[1]);
    await waitFor(() => expect(screen.queryByLabelText("Name of unit 2")).not.toBeInTheDocument());
    expect(deleted).toEqual(["lesson", "unit"]);
  });

  it("deletes a whole course after a warning and goes back to the list", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    let deleted = false;
    mockBackend({
      "GET /auth/me": () => users.teacher,
      "GET /courses/3": () => EDITABLE,
      "DELETE /courses/3": () => { deleted = true; return [204, null]; },
      "GET /courses": () => [],
    });
    renderApp("/courses/3/edit", { token: "t" });
    await userEvent.click(await screen.findByRole("button", { name: "Delete this course" }));
    expect(await screen.findByRole("heading", { name: "Courses" })).toBeInTheDocument();
    expect(deleted).toBe(true);
    expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining("progress"));
  });

  it("does not let someone edit a course they cannot change", async () => {
    mockBackend({ "GET /auth/me": () => users.teacher, "GET /courses/3": () => ({ ...COURSE, can_edit: false }) });
    renderApp("/courses/3/edit", { token: "t" });
    expect(await screen.findByRole("alert")).toHaveTextContent("not allowed to edit this course");
    expect(screen.queryByLabelText("New unit title")).not.toBeInTheDocument();
  });

  it("keeps students out of the editor routes", async () => {
    mockBackend({ "GET /auth/me": () => users.student });
    renderApp("/courses/new", { token: "t" });
    expect(await screen.findByRole("alert")).toHaveTextContent("not allowed to open this page");
  });
});

// ---------------------------------------------------------------- lesson editor
describe("lesson editor", () => {
  const EDITABLE_LESSON = { ...LESSON, can_edit: true, content_md: "Hello\n```python run\nprint(1)\n```", video_url: "https://example.com/v" };

  it("loads the lesson, saves changes, and removes the video when the box is emptied", async () => {
    let sent = null;
    mockBackend({
      "GET /auth/me": () => users.teacher,
      "GET /lessons/101": () => EDITABLE_LESSON,
      "PATCH /lessons/101": (o) => { sent = JSON.parse(o.body); return EDITABLE_LESSON; },
    });
    renderApp("/lessons/101/edit", { token: "t" });
    const title = await screen.findByLabelText("Lesson title");
    expect(title).toHaveValue("Variables");
    await userEvent.clear(title);
    await userEvent.type(title, "Variables v2");
    await userEvent.clear(screen.getByLabelText(/Video link/));
    await userEvent.click(screen.getByRole("button", { name: "Save lesson" }));
    await waitFor(() => expect(sent).not.toBeNull());
    expect(sent).toEqual({ title: "Variables v2", content_md: "Hello\n```python run\nprint(1)\n```", video_url: null });
    expect(await screen.findByRole("heading", { name: "Variables" })).toBeInTheDocument(); // back on the lesson page
  });

  it("shows a live preview with a working example", async () => {
    mockBackend({ "GET /auth/me": () => users.teacher, "GET /lessons/101": () => EDITABLE_LESSON });
    renderApp("/lessons/101/edit", { token: "t" });
    const preview = (await screen.findByText("Preview")).closest("section");
    expect(within(preview).getByText("Hello")).toBeInTheDocument();
    expect(within(preview).getByLabelText("Example code")).toHaveValue("print(1)");
    expect(within(preview).getByRole("button", { name: "Run" })).toBeInTheDocument();
  });

  it("shows the server's message when the video link is not allowed", async () => {
    mockBackend({
      "GET /auth/me": () => users.teacher,
      "GET /lessons/101": () => EDITABLE_LESSON,
      "PATCH /lessons/101": () => [422, { detail: [{ loc: ["body", "video_url"], msg: "Value error, The video link must start with http:// or https://" }] }],
    });
    renderApp("/lessons/101/edit", { token: "t" });
    await userEvent.click(await screen.findByRole("button", { name: "Save lesson" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("video link must start with");
  });

  it("does not open for someone who cannot edit", async () => {
    mockBackend({ "GET /auth/me": () => users.teacher, "GET /lessons/101": () => ({ ...LESSON, can_edit: false }) });
    renderApp("/lessons/101/edit", { token: "t" });
    expect(await screen.findByRole("alert")).toHaveTextContent("not allowed to edit this lesson");
  });
});
