import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import ActivityChart from "./ActivityChart.jsx";
import { mockBackend, renderApp, users } from "./testUtils.jsx";

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

const iso = (daysAgo = 0) => new Date(Date.now() - daysAgo * 86_400_000).toISOString();
const dayString = (daysAgo) => new Date(Date.now() - daysAgo * 86_400_000).toISOString().slice(0, 10);

function activity(overrides = {}) {
  return Array.from({ length: 30 }, (_, i) => ({ date: dayString(29 - i), submissions: 0, accepted: 0, lessons: 0, ...(overrides[i] || {}) }));
}

const REPORT = (over = {}) => ({
  student_id: 5, name: "Asha Kumari", email: "asha@x.com",
  courses: [{ course_id: 3, title: "C Programming Basics", completed_lessons: 1, total_lessons: 4, percent: 25 }],
  problems: [{ difficulty: "easy", solved: 2, total: 5 }, { difficulty: "medium", solved: 1, total: 3 }, { difficulty: "hard", solved: 0, total: 0 }],
  streak_days: 3, active_days_30: 9, total_submissions: 12, accepted_submissions: 5, last_active_at: iso(0),
  activity: activity({ 29: { submissions: 4, accepted: 2, lessons: 1 }, 20: { submissions: 2, accepted: 0, lessons: 0 } }),
  recent: [
    { id: 1, problem_id: 7, title: "Add two numbers", language: "python", verdict: "accepted", passed_count: 2, total_count: 2, created_at: iso(0), hidden: false },
    { id: 2, problem_id: 8, title: "Prime check", language: "c", verdict: "wrong_answer", passed_count: 1, total_count: 3, created_at: iso(1), hidden: false },
  ],
  ai_requests_30d: null, ...over,
});

// ---------------------------------------------------------------- the chart
describe("activity chart", () => {
  it("draws a group for each day and says in words what it shows", () => {
    render(<ActivityChart days={activity({ 29: { submissions: 4, accepted: 2, lessons: 1 }, 5: { submissions: 3, accepted: 3, lessons: 2 } })} />);
    expect(screen.getAllByTestId("day")).toHaveLength(30);
    expect(screen.getByRole("img")).toHaveAccessibleName("Activity in the last 30 days: 7 answers and runs, 5 accepted, 3 lessons finished");
  });

  it("draws bars only for days with activity and has a tooltip for each day", () => {
    const { container } = render(<ActivityChart days={activity({ 29: { submissions: 4, accepted: 2, lessons: 1 } })} />);
    expect(container.querySelectorAll("rect")).toHaveLength(2); // the light bar and the green bar of one day
    expect(container.querySelectorAll("circle")).toHaveLength(1); // one lesson
    expect(container.querySelector("title").textContent).toMatch(/: 0 answers and runs, 0 accepted, 0 lessons$/);
    expect(screen.getByText(new RegExp(`${dayString(0)}: 4 answers and runs, 2 accepted, 1 lessons`), { selector: "title" })).toBeInTheDocument();
  });

  it("shows the first and last date and copes with no days", () => {
    const { container } = render(<ActivityChart days={activity()} />);
    const labels = [...container.querySelectorAll("text")].map((t) => t.textContent);
    expect(labels).toEqual([dayString(29), dayString(0)]);
    const empty = render(<ActivityChart days={[]} />);
    expect(within(empty.container).getByRole("img")).toHaveAccessibleName(/Activity in the last 0 days/);
  });
});

// ---------------------------------------------------------------- the student's own page
describe("my progress", () => {
  const open = (report = REPORT(), me = users.student) => {
    mockBackend({ "GET /auth/me": () => me, "GET /reports/me": () => report });
    renderApp("/progress", { token: "t" });
  };

  it("shows the numbers a student cares about", async () => {
    open();
    expect(await screen.findByText("3 days")).toBeInTheDocument(); // (the heading shows first, the numbers a moment later)
    expect(screen.getByText("Days in a row with some practice")).toBeInTheDocument();
    expect(screen.getByText("9")).toBeInTheDocument();
    expect(screen.getByText("3 of 8")).toBeInTheDocument(); // 2 + 1 + 0 solved of 5 + 3 + 0
    expect(screen.getByText("of 12 sent")).toBeInTheDocument();
    expect(screen.queryByText("AI helper requests")).not.toBeInTheDocument();
  });

  it("shows each course with a link and its progress", async () => {
    open();
    expect(await screen.findByRole("link", { name: "C Programming Basics" })).toHaveAttribute("href", "/courses/3");
    expect(screen.getByText("1 of 4 lessons done")).toBeInTheDocument();
  });

  it("shows problems solved for each level", async () => {
    open();
    const easy = await screen.findByRole("progressbar", { name: "Easy problems solved" });
    expect(easy).toHaveAttribute("aria-valuenow", "40");
    expect(screen.getByRole("progressbar", { name: "Medium problems solved" })).toHaveAttribute("aria-valuenow", "33");
    expect(screen.getByRole("progressbar", { name: "Hard problems solved" })).toHaveAttribute("aria-valuenow", "0"); // no hard problems: no dividing by zero
  });

  it("lists recent answers with their verdicts, linked to the problem", async () => {
    open();
    const row = (await screen.findByRole("link", { name: "Prime check" })).closest("li");
    expect(row).toHaveTextContent("Wrong answer");
    expect(row).toHaveTextContent("1/3 tests · c");
    expect(screen.getByRole("link", { name: "Add two numbers" })).toHaveAttribute("href", "/problems/7");
  });

  it("never shows an exam result before it is published", async () => {
    open(REPORT({ recent: [{ id: 9, problem_id: null, title: "Exam answer (result hidden)", language: "python", verdict: null, passed_count: null, total_count: null, created_at: iso(0), hidden: true }] }));
    const row = (await screen.findByText("Exam answer (result hidden)")).closest("li");
    expect(within(row).getByText("Result not published yet")).toBeInTheDocument();
    expect(within(row).queryByRole("link")).not.toBeInTheDocument();
    expect(row).not.toHaveTextContent("null");
  });

  it("is friendly to a student who has not started", async () => {
    open(REPORT({
      courses: [], streak_days: 0, active_days_30: 0, total_submissions: 0, accepted_submissions: 0, last_active_at: null, recent: [],
      problems: [{ difficulty: "easy", solved: 0, total: 0 }, { difficulty: "medium", solved: 0, total: 0 }, { difficulty: "hard", solved: 0, total: 0 }],
      activity: activity(),
    }));
    expect(await screen.findByText("Practise today to start a streak")).toBeInTheDocument();
    expect(screen.getByText("Never")).toBeInTheDocument();
    expect(screen.getByText("There are no published courses yet.")).toBeInTheDocument();
    expect(screen.getByText("No answers sent yet.")).toBeInTheDocument();
    expect(screen.getByText("0 days")).toBeInTheDocument();
  });

  it("says '1 day' for a one day streak", async () => {
    open(REPORT({ streak_days: 1 }));
    expect(await screen.findByText("1 day")).toBeInTheDocument();
  });

  it("shows an error when the report cannot be loaded", async () => {
    mockBackend({ "GET /auth/me": () => users.student, "GET /reports/me": () => [500, { detail: "Something broke." }] });
    renderApp("/progress", { token: "t" });
    expect(await screen.findByRole("alert")).toHaveTextContent("Something broke.");
  });

  it("is only for students", async () => {
    open(REPORT(), users.teacher);
    expect(await screen.findByRole("alert")).toHaveTextContent("not allowed to open this page");
  });
});

// ---------------------------------------------------------------- the menu
describe("menu", () => {
  it("students get My progress, teachers get Reports", async () => {
    mockBackend({ "GET /auth/me": () => users.student, "GET /reports/me": () => REPORT() });
    const first = renderApp("/", { token: "t" });
    const nav = await screen.findByRole("navigation");
    expect(within(nav).getByRole("link", { name: "My progress" })).toBeInTheDocument();
    expect(within(nav).queryByRole("link", { name: "Reports" })).not.toBeInTheDocument();
    first.unmount();
    vi.restoreAllMocks();
    mockBackend({ "GET /auth/me": () => users.teacher });
    renderApp("/", { token: "t" });
    const nav2 = await screen.findByRole("navigation");
    expect(within(nav2).getByRole("link", { name: "Reports" })).toBeInTheDocument();
    expect(within(nav2).queryByRole("link", { name: "My progress" })).not.toBeInTheDocument();
  });

  it("the home page shows no development notes", async () => {
    mockBackend({ "GET /auth/me": () => users.student });
    renderApp("/", { token: "t" });
    await screen.findByText(/Welcome, Sam Student/);
    expect(screen.queryByText(/next phase|coming in a later phase|come next/i)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------- the class list
const SUMMARY = (over = {}) => ({
  batch_id: 3, name: "CSE Sem 3", year: 2026, branch: "CSE", student_count: 40, total_lessons: 14,
  avg_completion_percent: 52.5, avg_problems_solved: 3.4, inactive_count: 6, last_active_at: iso(0), ...over,
});

describe("class list", () => {
  it("shows each batch with its numbers and a link to the full report", async () => {
    mockBackend({ "GET /auth/me": () => users.teacher, "GET /reports/batches": () => [SUMMARY(), SUMMARY({ batch_id: 4, name: "ECE Sem 1", total_lessons: 0, inactive_count: 0, last_active_at: null, branch: null })] });
    renderApp("/reports", { token: "t" });
    const row = (await screen.findByRole("link", { name: "CSE Sem 3" })).closest("tr");
    expect(screen.getByRole("link", { name: "CSE Sem 3" })).toHaveAttribute("href", "/reports/batches/3");
    expect(row).toHaveTextContent("40");
    expect(row).toHaveTextContent("52.5%");
    expect(row).toHaveTextContent("3.4");
    expect(within(row).getByText("6").className).toContain("amber"); // students needing attention stand out
    const other = screen.getByRole("link", { name: "ECE Sem 1" }).closest("tr");
    expect(other).toHaveTextContent("No courses yet");
    expect(other).toHaveTextContent("Never");
  });

  it("asks again when the inactive limit is changed", async () => {
    const spy = mockBackend({ "GET /auth/me": () => users.teacher, "GET /reports/batches": () => [SUMMARY()] });
    renderApp("/reports", { token: "t" });
    await screen.findByRole("link", { name: "CSE Sem 3" });
    await userEvent.selectOptions(screen.getByLabelText("Inactive after"), "14");
    await waitFor(() => expect(spy.mock.calls.some(([url]) => String(url).includes("/reports/batches?inactive_days=14"))).toBe(true));
    expect(screen.getByText(/no activity \(an answer, a Run, a lesson or an exam\) for 14 days/)).toBeInTheDocument();
  });

  it("explains an empty list, and keeps students out", async () => {
    mockBackend({ "GET /auth/me": () => users.teacher, "GET /reports/batches": () => [] });
    const first = renderApp("/reports", { token: "t" });
    expect(await screen.findByText(/You have no batches yet/)).toBeInTheDocument();
    first.unmount();
    vi.restoreAllMocks();
    mockBackend({ "GET /auth/me": () => users.student });
    renderApp("/reports", { token: "t" });
    expect(await screen.findByRole("alert")).toHaveTextContent("not allowed to open this page");
  });
});

// ---------------------------------------------------------------- one class
const ROW = (over = {}) => ({
  user_id: 20, name: "Asha Kumari", email: "asha@x.com", lessons_completed: 7, lessons_total: 14, completion_percent: 50, problems_solved: 4,
  submissions_30d: 22, ai_requests_30d: 3, last_active_at: iso(0), days_inactive: 0, status: "active", ...over,
});
const BATCH = (over = {}) => ({
  summary: SUMMARY({ student_count: 3, inactive_count: 2 }), inactive_days: 7,
  students: [
    ROW(),
    ROW({ user_id: 21, name: "Ravi Singh", email: "ravi@x.com", completion_percent: 10, lessons_completed: 1, last_active_at: iso(12), days_inactive: 12, status: "inactive", ai_requests_30d: 0 }),
    ROW({ user_id: 22, name: "Sam Roy", email: "sam@x.com", completion_percent: 0, lessons_completed: 0, problems_solved: 0, submissions_30d: 0, ai_requests_30d: 0, last_active_at: null, days_inactive: null, status: "never_active" }),
  ],
  weak_topics: [{ topic: "arrays", students: 3, pairs_attempted: 6, pairs_solved: 4, solve_rate_percent: 66.7, wrong_submissions: 5, hint_requests: 4 }],
  weak_problems: [{ problem_id: 9, title: "Reverse an Array", difficulty: "medium", students_attempted: 3, students_solved: 1, solve_rate_percent: 33.3, wrong_submissions: 6, hint_requests: 2 }],
  courses: [{ course_id: 3, title: "C Programming Basics", total_lessons: 14, avg_percent: 20 }],
  assessments: [
    { assessment_id: 12, title: "Midterm", type: "exam", results_published: true, students: 3, participants: 2, avg_percent: 66.7 },
    { assessment_id: 13, title: "Homework 1", type: "assignment", results_published: false, students: 3, participants: 0, avg_percent: null },
  ],
  ...over,
});
const openBatch = (data = BATCH(), me = users.teacher, extra = {}) => {
  const spy = mockBackend({ "GET /auth/me": () => me, "GET /reports/batches/3": () => data, ...extra });
  renderApp("/reports/batches/3", { token: "secret-token" });
  return spy;
};

describe("class report", () => {
  it("shows the summary of the class", async () => {
    openBatch();
    expect(await screen.findByRole("heading", { name: "CSE Sem 3" })).toBeInTheDocument();
    expect(screen.getByText("CSE · 2026")).toBeInTheDocument();
    expect(screen.getByText("52.5%")).toBeInTheDocument();
    expect(screen.getByText("no activity for 7 days, or never")).toBeInTheDocument();
  });

  it("lists the students who need attention, in plain words", async () => {
    openBatch();
    const card = (await screen.findByText("Students who need attention")).closest("section");
    expect(within(card).getByText("No activity for 12 days")).toBeInTheDocument();
    expect(within(card).getByText("Has never been active")).toBeInTheDocument();
    expect(within(card).queryByText("Asha Kumari")).not.toBeInTheDocument(); // she is active
    expect(within(card).getByRole("link", { name: "Ravi Singh" })).toHaveAttribute("href", "/reports/students/21");
  });

  it("tells the teacher when everyone is active", async () => {
    openBatch(BATCH({ students: [ROW()], summary: SUMMARY({ inactive_count: 0 }) }));
    expect(await screen.findByText("Everyone has been active in the last 7 days.")).toBeInTheDocument();
  });

  it("has a row for every student with progress, last activity and a status", async () => {
    openBatch();
    const table = (await screen.findByText("All students")).closest("section");
    const asha = within(table).getByText("Asha Kumari").closest("tr");
    expect(asha).toHaveTextContent("7/14");
    expect(asha).toHaveTextContent("22");
    expect(within(asha).getByRole("progressbar", { name: "Course completion of Asha Kumari" })).toHaveAttribute("aria-valuenow", "50");
    expect(within(asha).getByText("Active")).toBeInTheDocument();
    expect(within(within(table).getByText("Ravi Singh").closest("tr")).getByText("Inactive")).toBeInTheDocument();
    const sam = within(table).getByText("Sam Roy").closest("tr");
    expect(within(sam).getByText("Never active")).toBeInTheDocument();
    expect(within(sam).getByText("Never")).toBeInTheDocument(); // last active
    expect(within(table).getByRole("link", { name: "Asha Kumari" })).toHaveAttribute("href", "/reports/students/20");
  });

  it("shows weak topics and the hardest problems", async () => {
    openBatch();
    const topics = (await screen.findByText("Weak topics")).closest("section");
    expect(within(topics).getByText("arrays")).toBeInTheDocument();
    expect(within(topics).getByText("66.7%")).toBeInTheDocument();
    expect(within(topics).getByText("(4 of 6 tries)")).toBeInTheDocument();
    const hard = screen.getByText("Hardest problems").closest("section");
    expect(within(hard).getByRole("link", { name: "Reverse an Array" })).toHaveAttribute("href", "/problems/9");
    expect(within(hard).getByText("1 of 3 students")).toBeInTheDocument();
  });

  it("shows course averages and assignment and exam averages with links to the marks", async () => {
    openBatch();
    const courses = (await screen.findByRole("heading", { name: "Courses" })).closest("section");
    expect(within(courses).getByRole("progressbar", { name: "Average completion of C Programming Basics" })).toHaveAttribute("aria-valuenow", "20");
    const tests = screen.getByText("Assignments and exams").closest("section");
    expect(within(tests).getByRole("link", { name: "Midterm" })).toHaveAttribute("href", "/assessments/12/results");
    expect(within(tests).getByText("2 of 3 took part")).toBeInTheDocument();
    expect(within(tests).getByText("Average 66.7%")).toBeInTheDocument();
    expect(within(tests).getByText("No marks yet")).toBeInTheDocument();
  });

  it("explains each empty section instead of showing an empty box", async () => {
    openBatch(BATCH({ weak_topics: [], weak_problems: [], courses: [], assessments: [], students: [], summary: SUMMARY({ student_count: 0, inactive_count: 0, total_lessons: 0 }) }));
    expect(await screen.findByText(/No weak topics found/)).toBeInTheDocument();
    expect(screen.getByText("No problem stands out yet.")).toBeInTheDocument();
    expect(screen.getByText("No published courses yet.")).toBeInTheDocument();
    expect(screen.getByText(/No published assignment or exam/)).toBeInTheDocument();
    expect(screen.getByText("There are no students in this batch yet.")).toBeInTheDocument();
    expect(screen.getByText("No courses")).toBeInTheDocument();
  });

  it("changes the inactive limit and asks again", async () => {
    const spy = openBatch();
    await screen.findByRole("heading", { name: "CSE Sem 3" });
    await userEvent.selectOptions(screen.getByLabelText("Inactive after"), "30");
    await waitFor(() => expect(spy.mock.calls.some(([url]) => String(url).includes("/reports/batches/3?inactive_days=30"))).toBe(true));
  });

  it("downloads the CSV with the login token and the chosen limit", async () => {
    const spy = openBatch(BATCH(), users.teacher, { "GET /reports/batches/3/export": () => new Blob(["Name\n"], { type: "text/csv" }) });
    const makeUrl = vi.fn(() => "blob:fake");
    globalThis.URL.createObjectURL = makeUrl;
    globalThis.URL.revokeObjectURL = vi.fn();
    const names = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function () { names.push(this.download); });
    await userEvent.click(await screen.findByRole("button", { name: "Download CSV" }));
    await waitFor(() => expect(names).toEqual(["batch-3-progress.csv"]));
    expect(makeUrl).toHaveBeenCalledWith(expect.any(Blob));
    const call = spy.mock.calls.find(([url]) => String(url).includes("/export"));
    expect(String(call[0])).toContain("inactive_days=7");
    expect(call[1].headers.Authorization).toBe("Bearer secret-token");
  });

  it("shows an error if the download fails", async () => {
    openBatch(BATCH(), users.teacher, { "GET /reports/batches/3/export": () => [404, { detail: "Batch not found." }] });
    await userEvent.click(await screen.findByRole("button", { name: "Download CSV" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Batch not found.");
  });

  it("an admin can open it too, and an unknown batch gives a clear message", async () => {
    openBatch(BATCH(), users.admin);
    expect(await screen.findByRole("heading", { name: "CSE Sem 3" })).toBeInTheDocument();
  });

  it("shows a clear message when the batch cannot be found", async () => {
    mockBackend({ "GET /auth/me": () => users.teacher, "GET /reports/batches/3": () => [404, { detail: "Batch not found." }] });
    renderApp("/reports/batches/3", { token: "t" });
    expect(await screen.findByRole("alert")).toHaveTextContent("Batch not found.");
    expect(screen.getByRole("link", { name: "Back to the class list" })).toHaveAttribute("href", "/reports");
  });
});

// ---------------------------------------------------------------- one student, as the teacher sees them
describe("student report for teachers", () => {
  const openStudent = (report = REPORT({ ai_requests_30d: 7 })) => {
    mockBackend({ "GET /auth/me": () => users.teacher, "GET /reports/students/5": () => report });
    renderApp("/reports/students/5", { token: "t" });
  };

  it("shows the student's name, their dashboard and how much they used the AI helper", async () => {
    openStudent();
    expect(await screen.findByRole("heading", { name: "Asha Kumari" })).toBeInTheDocument();
    expect(screen.getByText("asha@x.com")).toBeInTheDocument();
    expect(screen.getByText("AI helper requests")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "← All classes" })).toHaveAttribute("href", "/reports");
  });

  it("does not send the teacher into the student's own course and problem pages", async () => {
    openStudent();
    await screen.findByRole("heading", { name: "Asha Kumari" });
    expect(screen.queryByRole("link", { name: "C Programming Basics" })).not.toBeInTheDocument();
    expect(screen.getByText("Prime check")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Prime check" })).not.toBeInTheDocument();
  });

  it("shows a clear message for a student the teacher may not see", async () => {
    mockBackend({ "GET /auth/me": () => users.teacher, "GET /reports/students/5": () => [404, { detail: "Student not found." }] });
    renderApp("/reports/students/5", { token: "t" });
    expect(await screen.findByRole("alert")).toHaveTextContent("Student not found.");
  });
});
