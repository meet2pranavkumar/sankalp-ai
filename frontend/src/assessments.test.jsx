import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import ExamTimer from "./ExamTimer.jsx";
import { formatCountdown, formatMinutes, fromLocalInput, toLocalInput } from "./time.js";
import { moveItem } from "./pages/AssessmentEditor.jsx";
import { mockBackend, renderApp, users } from "./testUtils.jsx";

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

const at = (ms) => new Date(Date.now() + ms).toISOString();
const MIN = 60_000;
const LANGS = [{ key: "c", label: "C (GCC 9.2)" }, { key: "python", label: "Python (3.8)" }];
const SIMPLE = { sankalp_simple_editor: "1" };

const PROBLEMS = [
  { problem_id: 7, title: "Add two numbers", difficulty: "easy", marks: 10, position: 1, score: null },
  { problem_id: 8, title: "Add again", difficulty: "medium", marks: 20, position: 2, score: null },
];
const attempt = (left = 55 * MIN) => ({ started_at: at(-5 * MIN), deadline_at: at(left), finished_at: null });

const assessment = (over = {}) => ({
  id: 3, title: "Midterm", type: "exam", batch_id: 1, batch_name: "CSE Sem 3",
  starts_at: at(-5 * MIN), ends_at: at(120 * MIN), duration_min: 60,
  is_published: true, results_published: false, total_marks: 30, problem_count: 2,
  status: "ready", my_marks: null, can_manage: false, description: "", server_now: at(0),
  attempt: null, problems: null, has_activity: false, ...over,
});
const running = (over = {}) => assessment({ status: "in_progress", attempt: attempt(), problems: PROBLEMS, ...over });

// ---------------------------------------------------------------- time helpers
describe("time helpers", () => {
  it("formats a countdown", () => {
    expect(formatCountdown(65_000)).toBe("01:05");
    expect(formatCountdown(3_725_000)).toBe("1:02:05");
    expect(formatCountdown(0)).toBe("00:00");
    expect(formatCountdown(-5000)).toBe("00:00");
  });
  it("formats minutes", () => {
    expect([formatMinutes(45), formatMinutes(60), formatMinutes(90)]).toEqual(["45 min", "1 h", "1 h 30 min"]);
  });
  it("turns local input into UTC and back without changing the moment", () => {
    const iso = "2026-12-01T09:30:00.000Z";
    expect(fromLocalInput(toLocalInput(iso))).toBe(iso);
    expect(fromLocalInput("2026-12-01T09:30")).toBe(new Date(2026, 11, 1, 9, 30).toISOString()); // typed time = the person's own time
  });
  it("moves list items and stops at the ends", () => {
    expect(moveItem(["a", "b", "c"], 1, -1)).toEqual(["b", "a", "c"]);
    expect(moveItem(["a", "b", "c"], 0, -1)).toEqual(["a", "b", "c"]);
  });
});

// ---------------------------------------------------------------- the timer
describe("exam timer", () => {
  it("counts down, and uses the server's clock, not the computer's", async () => {
    // The server says it is 10 minutes later than this computer thinks. The deadline is 3 server-minutes away.
    const serverNow = at(10 * MIN);
    render(<ExamTimer attempt={{ deadline_at: at(13 * MIN) }} serverNow={serverNow} onExpire={() => {}} />);
    expect(screen.getByRole("timer")).toHaveTextContent(/0[23]:[0-5]\d/); // about 3 minutes, not 13
  });

  it("calls onExpire once when time is up", async () => {
    const onExpire = vi.fn();
    render(<ExamTimer attempt={{ deadline_at: at(100) }} serverNow={at(0)} onExpire={onExpire} />);
    await waitFor(() => expect(onExpire).toHaveBeenCalled());
    await act(async () => new Promise((r) => setTimeout(r, 120)));
    expect(onExpire).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("timer")).toHaveTextContent("00:00");
  });

  it("turns red in the last five minutes", () => {
    render(<ExamTimer attempt={{ deadline_at: at(3 * MIN) }} serverNow={at(0)} onExpire={() => {}} />);
    expect(screen.getByRole("timer").className).toContain("red");
  });
});

// ---------------------------------------------------------------- the list
describe("assessment list", () => {
  const items = [
    { ...assessment({ status: "open", my_marks: 12 }), type: "assignment", title: "Loops homework", duration_min: null },
    { ...assessment({ status: "ready", id: 4, title: "Midterm" }) },
  ];

  it("shows each student their status and score", async () => {
    mockBackend({ "GET /auth/me": () => users.student, "GET /assessments": () => items });
    renderApp("/assessments", { token: "t" });
    expect(await screen.findByRole("link", { name: "Loops homework" })).toHaveAttribute("href", "/assessments/3");
    expect(screen.getByText("Open")).toBeInTheDocument();
    expect(screen.getByText("Ready to start")).toBeInTheDocument();
    expect(screen.getByText(/You scored 12/)).toBeInTheDocument();
    expect(screen.getByText(/1 h per student/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "New assessment" })).not.toBeInTheDocument();
  });

  it("shows teachers drafts and a New assessment button", async () => {
    mockBackend({ "GET /auth/me": () => users.teacher, "GET /assessments": () => [{ ...assessment({ is_published: false, status: null, can_manage: true }) }] });
    renderApp("/assessments", { token: "t" });
    expect(await screen.findByText("Draft")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "New assessment" })).toBeInTheDocument();
  });

  it("explains an empty list", async () => {
    mockBackend({ "GET /auth/me": () => users.student, "GET /assessments": () => [] });
    renderApp("/assessments", { token: "t" });
    expect(await screen.findByText(/Your teacher will publish/)).toBeInTheDocument();
  });

  it("keeps super admins out", async () => {
    mockBackend({ "GET /auth/me": () => users.super });
    renderApp("/assessments", { token: "t" });
    expect(await screen.findByRole("alert")).toHaveTextContent("not allowed");
  });
});

// ---------------------------------------------------------------- the assessment page
describe("assessment page, student", () => {
  const page = (a, extra = {}) =>
    mockBackend({ "GET /auth/me": () => users.student, "GET /assessments/3": () => a, ...extra });

  it("says when it opens and shows no questions", async () => {
    page(assessment({ status: "upcoming" }));
    renderApp("/assessments/3", { token: "t" });
    expect(await screen.findByText(/opens on/)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Problems" })).not.toBeInTheDocument(); // (the nav bar also has a "Problems" link)
  });

  it("explains the rules and only starts after the student confirms", async () => {
    let started = 0;
    const confirm = vi.spyOn(window, "confirm");
    page(assessment(), { "POST /assessments/3/start": () => { started += 1; return running(); } });
    renderApp("/assessments/3", { token: "t" });
    expect(await screen.findByText(/timer cannot be paused/)).toBeInTheDocument();
    expect(screen.getByText(/last saved code is submitted for you/)).toBeInTheDocument();
    confirm.mockReturnValueOnce(false);
    await userEvent.click(screen.getByRole("button", { name: "Start the exam" }));
    expect(started).toBe(0);
    confirm.mockReturnValueOnce(true);
    await userEvent.click(screen.getByRole("button", { name: "Start the exam" }));
    expect(await screen.findByRole("timer")).toBeInTheDocument();
    expect(started).toBe(1);
    expect(screen.getByRole("link", { name: "Add two numbers" })).toHaveAttribute("href", "/assessments/3/problems/7");
  });

  it("shows the timer and problems while the exam runs, then finishes it", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    let finished = false;
    mockBackend({
      "GET /auth/me": () => users.student,
      "GET /assessments/3": () => running(),
      "POST /assessments/3/finish": () => { finished = true; return assessment({ status: "finished", attempt: { ...attempt(), finished_at: at(0) }, problems: PROBLEMS }); },
      "GET /assessments/3/my-result": () => ({ visible: false, total_marks: 30, auto_marks: null, final_marks: null, comment: null, per_problem: [], pending: 0 }),
    });
    renderApp("/assessments/3", { token: "t" });
    expect(await screen.findByRole("timer")).toHaveTextContent(/5\d:\d\d|0\d:\d\d/);
    await userEvent.click(screen.getByRole("button", { name: "Finish the exam" }));
    expect(await screen.findByText("Your exam is over")).toBeInTheDocument();
    expect(screen.getByText(/marks will be shown after your teacher publishes/)).toBeInTheDocument();
    expect(finished).toBe(true);
    expect(screen.queryByRole("timer")).not.toBeInTheDocument();
  });

  it("when the timer reaches zero the page asks the server what happened", async () => {
    let calls = 0;
    mockBackend({
      "GET /auth/me": () => users.student,
      "GET /assessments/3": () => {
        calls += 1;
        return calls === 1
          ? running({ attempt: { started_at: at(-60 * MIN), deadline_at: at(150), finished_at: null } })
          : assessment({ status: "finished", attempt: { started_at: at(-60 * MIN), deadline_at: at(-100), finished_at: null }, problems: PROBLEMS });
      },
      "GET /assessments/3/my-result": () => ({ visible: false, total_marks: 30, auto_marks: null, final_marks: null, comment: null, per_problem: [], pending: 0 }),
    });
    renderApp("/assessments/3", { token: "t" });
    expect(await screen.findByRole("timer")).toBeInTheDocument();
    expect(await screen.findByText("Your exam is over")).toBeInTheDocument();
    expect(calls).toBeGreaterThanOrEqual(2);
  });

  it("shows marks and the teacher's comment after results are published", async () => {
    page(assessment({ status: "finished", results_published: true, attempt: { ...attempt(), finished_at: at(0) }, problems: PROBLEMS }), {
      "GET /assessments/3/my-result": () => ({ visible: true, total_marks: 30, auto_marks: 25, final_marks: 27, comment: "Well done", per_problem: [], pending: 0 }),
    });
    renderApp("/assessments/3", { token: "t" });
    expect(await screen.findByText("27")).toBeInTheDocument();
    expect(screen.getByText(/out of 30/)).toBeInTheDocument();
    expect(screen.getByText(/Well done/)).toBeInTheDocument();
  });

  it("warns when some answers are still being checked", async () => {
    page(assessment({ status: "finished", results_published: true, attempt: { ...attempt(), finished_at: at(0) }, problems: PROBLEMS }), {
      "GET /assessments/3/my-result": () => ({ visible: true, total_marks: 30, auto_marks: 10, final_marks: 10, comment: null, per_problem: [], pending: 2 }),
    });
    renderApp("/assessments/3", { token: "t" });
    expect(await screen.findByText(/still being checked/)).toBeInTheDocument();
  });

  it("shows live marks for each problem in an open assignment", async () => {
    const problems = [{ ...PROBLEMS[0], score: { problem_id: 7, marks: 5, possible: 10, passed: 1, total: 2, attempted: true } }, PROBLEMS[1]];
    page(assessment({ type: "assignment", status: "open", duration_min: null, problems, my_marks: 5 }));
    renderApp("/assessments/3", { token: "t" });
    expect(await screen.findByText("5 / 10 marks")).toBeInTheDocument();
    expect(screen.getByText("20 marks")).toBeInTheDocument();
    expect(screen.getByText(/open until/)).toBeInTheDocument();
  });

  it("tells the student when they missed the exam", async () => {
    page(assessment({ status: "missed" }));
    renderApp("/assessments/3", { token: "t" });
    expect(await screen.findByRole("alert")).toHaveTextContent("did not start this exam");
  });

  it("counts a tab switch during the exam, and only then", async () => {
    let switches = 0;
    mockBackend({
      "GET /auth/me": () => users.student,
      "GET /assessments/3": () => running(),
      "POST /assessments/3/tab-switch": () => { switches += 1; return [204, null]; },
    });
    renderApp("/assessments/3", { token: "t" });
    await screen.findByRole("timer");
    Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
    document.dispatchEvent(new Event("visibilitychange"));
    expect(switches).toBe(0); // coming back to the tab is not counted
    Object.defineProperty(document, "visibilityState", { value: "hidden", configurable: true });
    document.dispatchEvent(new Event("visibilitychange"));
    await waitFor(() => expect(switches).toBe(1));
    Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
  });

  it("does not count tab switches in an assignment", async () => {
    let switches = 0;
    mockBackend({
      "GET /auth/me": () => users.student,
      "GET /assessments/3": () => assessment({ type: "assignment", status: "open", duration_min: null, problems: PROBLEMS }),
      "POST /assessments/3/tab-switch": () => { switches += 1; return [204, null]; },
    });
    renderApp("/assessments/3", { token: "t" });
    await screen.findByRole("heading", { name: "Problems" });
    Object.defineProperty(document, "visibilityState", { value: "hidden", configurable: true });
    document.dispatchEvent(new Event("visibilitychange"));
    await act(async () => new Promise((r) => setTimeout(r, 50)));
    expect(switches).toBe(0);
    Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
  });

  it("shows a clear message when the assessment cannot be found", async () => {
    mockBackend({ "GET /auth/me": () => users.student, "GET /assessments/3": () => [404, { detail: "Assessment not found." }] });
    renderApp("/assessments/3", { token: "t" });
    expect(await screen.findByRole("alert")).toHaveTextContent("Assessment not found.");
  });
});

describe("assessment page, teacher", () => {
  const manage = (over = {}, extra = {}) =>
    mockBackend({ "GET /auth/me": () => users.teacher, "GET /assessments/3": () => assessment({ status: null, can_manage: true, problems: PROBLEMS, ...over }), ...extra });

  it("shows the manage tools and every problem", async () => {
    manage({ is_published: false });
    renderApp("/assessments/3", { token: "t" });
    expect(await screen.findByText("This is a draft. Students cannot see it until you publish it.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Results and marks" })).toHaveAttribute("href", "/assessments/3/results");
    expect(screen.getByRole("link", { name: "Edit" })).toHaveAttribute("href", "/assessments/3/edit");
    expect(screen.getByRole("link", { name: "Add again" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start the exam" })).not.toBeInTheDocument();
  });

  it("publishes and hides", async () => {
    let sent = null;
    manage({ is_published: false }, { "PATCH /assessments/3": (o) => { sent = JSON.parse(o.body); return assessment({ status: null, can_manage: true, problems: PROBLEMS, is_published: true }); } });
    renderApp("/assessments/3", { token: "t" });
    await userEvent.click(await screen.findByRole("button", { name: "Publish to students" }));
    expect(await screen.findByRole("button", { name: "Hide from students" })).toBeInTheDocument();
    expect(sent).toEqual({ is_published: true });
  });

  it("deletes only after asking, and not at all once students have started", async () => {
    const confirm = vi.spyOn(window, "confirm");
    let deleted = false;
    manage({}, { "DELETE /assessments/3": () => { deleted = true; return [204, null]; }, "GET /assessments": () => [] });
    renderApp("/assessments/3", { token: "t" });
    confirm.mockReturnValueOnce(false);
    await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
    expect(deleted).toBe(false);
    confirm.mockReturnValueOnce(true);
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(await screen.findByRole("heading", { name: "Assignments and exams" })).toBeInTheDocument();
    expect(deleted).toBe(true);
  });

  it("hides Delete when students have started", async () => {
    manage({ has_activity: true });
    renderApp("/assessments/3", { token: "t" });
    expect(await screen.findByText(/problems can no longer change/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------- answering inside an assessment
describe("problem page inside an assessment", () => {
  const PROBLEM = {
    id: 7, college_id: 1, created_by: 2, title: "Add two numbers", difficulty: "easy", tags: [],
    statement_md: "Print the sum.", time_limit_ms: 1000, memory_limit_mb: 128, is_public: false, can_edit: false,
    test_cases: [{ position: 1, input: "1 2\n", expected_output: "3\n", is_hidden: false, weight: 1 }],
  };
  const backend = (asg = running(), extra = {}, me = users.student) =>
    mockBackend({
      "GET /auth/me": () => me,
      "GET /assessments/3/problems/7": () => PROBLEM,
      "GET /languages": () => LANGS,
      "GET /assessments/3": () => asg,
      "GET /assessments/3/problems/7/submissions": () => [],
      "GET /assessments/3/problems/7/draft": () => null,
      "PUT /assessments/3/problems/7/draft": () => ({ language: "python", source_code: "x", updated_at: at(0) }),
      ...extra,
    });
  const open = () => renderApp("/assessments/3/problems/7", { token: "t", storage: SIMPLE });
  const typeCode = async (text) => {
    const editor = await screen.findByLabelText("Code editor");
    await userEvent.clear(editor);
    await userEvent.click(editor);
    await userEvent.paste(text);
  };

  it("loads the problem through the assessment, with a timer and a way back", async () => {
    backend();
    open();
    expect(await screen.findByRole("heading", { name: "Add two numbers" })).toBeInTheDocument();
    expect(screen.getByRole("timer")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "← Back to the assessment" })).toHaveAttribute("href", "/assessments/3");
    expect(screen.queryByRole("link", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.getByText("Midterm")).toBeInTheDocument();
  });

  it("sends the assessment id when running and submitting", async () => {
    const sent = {};
    backend(running(), {
      "POST /run": (o) => { sent.run = JSON.parse(o.body); return [202, { id: 70, status: "queued" }]; },
      "GET /submissions/70": () => ({ id: 70, status: "done", verdict: "ok", stdout: "42\n", hidden: false }),
      "POST /submissions": (o) => { sent.submit = JSON.parse(o.body); return [202, { id: 71, status: "queued" }]; },
      "GET /submissions/71": () => ({ id: 71, status: "done", hidden: true, verdict: null }),
    });
    open();
    await typeCode("print(42)");
    await userEvent.click(screen.getByRole("button", { name: "Run" }));
    expect(await screen.findByText("42")).toBeInTheDocument(); // the student can always test their code
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));
    expect(await screen.findByText("Answer received")).toBeInTheDocument();
    expect(screen.getByText(/result is hidden during the exam/)).toBeInTheDocument();
    expect(sent.run).toMatchObject({ assessment_id: 3, problem_id: 7, language: "python" });
    expect(sent.submit).toEqual({ assessment_id: 3, problem_id: 7, language: "python", source_code: "print(42)" });
    expect(screen.queryByText(/tests passed/)).not.toBeInTheDocument();
  });

  it("shows hidden exam answers in the history as received, without a verdict", async () => {
    backend(running(), {
      "GET /assessments/3/problems/7/submissions": () => [{ id: 5, language: "python", status: "done", verdict: null, passed_count: null, total_count: null, runtime_ms: null, created_at: "2026-11-10T10:00:00Z", hidden: true }],
    });
    open();
    expect(await screen.findByText("Received")).toBeInTheDocument();
    expect(screen.queryByText(/null/)).not.toBeInTheDocument();
  });

  it("saves the code on the server while typing, but never the empty starter template", async () => {
    const saved = [];
    backend(running(), { "PUT /assessments/3/problems/7/draft": (o) => { saved.push(JSON.parse(o.body)); return { language: "python", source_code: "", updated_at: at(0) }; } });
    open();
    const editor = await screen.findByLabelText("Code editor");
    await act(async () => new Promise((r) => setTimeout(r, 100)));
    expect(saved).toEqual([]); // the template alone is not an answer
    await userEvent.click(editor);
    await userEvent.clear(editor);
    await userEvent.paste("print('mine')");
    await waitFor(() => expect(saved.length).toBeGreaterThan(0));
    expect(saved.at(-1)).toEqual({ language: "python", source_code: "print('mine')" });
    expect(await screen.findByText(/Saved automatically at/)).toBeInTheDocument();
  });

  it("brings back the code saved on the server, for example on another computer", async () => {
    backend(running(), { "GET /assessments/3/problems/7/draft": () => ({ language: "python", source_code: "print('from server')", updated_at: at(-1000) }) });
    open();
    await waitFor(() => expect(screen.getByLabelText("Code editor")).toHaveValue("print('from server')"));
  });

  it("does not save drafts in an assignment", async () => {
    const saved = [];
    backend(assessment({ type: "assignment", status: "open", duration_min: null, problems: PROBLEMS }), {
      "PUT /assessments/3/problems/7/draft": (o) => { saved.push(o); return {}; },
    });
    open();
    await typeCode("print(1)");
    await act(async () => new Promise((r) => setTimeout(r, 100)));
    expect(saved).toEqual([]);
    expect(screen.queryByRole("timer")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit" })).toBeEnabled();
  });

  it("stops answers when the exam is over", async () => {
    backend(assessment({ status: "finished", attempt: { ...attempt(), finished_at: at(0) }, problems: PROBLEMS }));
    open();
    expect(await screen.findByText("Time is over. You can no longer send answers.")).toBeInTheDocument();
    await typeCode("print(1)");
    expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Run" })).toBeDisabled();
    expect(screen.queryByRole("timer")).not.toBeInTheDocument();
  });

  it("after the server refuses a late answer, shows the real state", async () => {
    let asked = 0;
    backend(running(), {
      "GET /assessments/3": () => {
        asked += 1;
        return asked === 1 ? running() : assessment({ status: "finished", attempt: { ...attempt(), finished_at: at(0) }, problems: PROBLEMS });
      },
      "POST /submissions": () => [403, { detail: "Your time is over. No more answers can be sent." }],
    });
    open();
    await typeCode("print(1)");
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));
    expect(await screen.findByText("Time is over. You can no longer send answers.")).toBeInTheDocument();
    expect(screen.getAllByText(/time is over/i).length).toBeGreaterThan(0);
  });

  it("shows an open assignment with its normal verdicts", async () => {
    backend(assessment({ type: "assignment", status: "open", duration_min: null, problems: PROBLEMS }), {
      "POST /submissions": () => [202, { id: 80, status: "queued" }],
      "GET /submissions/80": () => ({ id: 80, status: "done", verdict: "accepted", passed_count: 2, total_count: 2, hidden: false, results: [] }),
    });
    open();
    await typeCode("print(1)");
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));
    expect(await screen.findByText("2 of 2 tests passed")).toBeInTheDocument();
  });

  it("lets a teacher read the problem but not answer", async () => {
    backend(assessment({ status: null, can_manage: true, problems: PROBLEMS }), {}, users.teacher);
    open();
    expect(await screen.findByText(/Only students can send answers/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
    expect(screen.queryByText("My earlier submissions")).not.toBeInTheDocument();
  });

  it("explains why a problem cannot be opened yet", async () => {
    mockBackend({
      "GET /auth/me": () => users.student,
      "GET /assessments/3/problems/7": () => [403, { detail: "Press Start to see the questions." }],
      "GET /languages": () => LANGS,
      "GET /assessments/3": () => assessment(),
      "GET /assessments/3/problems/7/submissions": () => [403, { detail: "x" }],
    });
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent("Press Start to see the questions.");
  });
});
