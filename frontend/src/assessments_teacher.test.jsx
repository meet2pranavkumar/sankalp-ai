import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mockBackend, renderApp, users } from "./testUtils.jsx";

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

const at = (ms) => new Date(Date.now() + ms).toISOString();
const MIN = 60_000;
const BATCHES = [{ id: 1, college_id: 1, created_by: 2, name: "CSE Sem 3", year: 2026, branch: "CSE" }];
const POOL = [
  { id: 7, title: "Add two numbers", difficulty: "easy", tags: [], is_public: false, solved: false },
  { id: 8, title: "Reverse a string", difficulty: "medium", tags: [], is_public: false, solved: false },
  { id: 9, title: "Prime check", difficulty: "hard", tags: [], is_public: false, solved: false },
];
const created = (over = {}) => ({
  id: 12, title: "Midterm", type: "exam", batch_id: 1, batch_name: "CSE Sem 3", starts_at: at(60 * MIN), ends_at: at(180 * MIN),
  duration_min: 60, is_published: false, results_published: false, total_marks: 30, problem_count: 2, status: null, my_marks: null,
  can_manage: true, description: "", server_now: at(0), attempt: null, has_activity: false,
  problems: [
    { problem_id: 7, title: "Add two numbers", difficulty: "easy", marks: 10, position: 1, score: null },
    { problem_id: 8, title: "Reverse a string", difficulty: "medium", marks: 20, position: 2, score: null },
  ], ...over,
});

const setupEditor = (extra = {}) =>
  mockBackend({ "GET /auth/me": () => users.teacher, "GET /batches": () => BATCHES, "GET /problems": () => POOL, ...extra });

async function fillBasics(title = "Midterm") {
  await screen.findByRole("option", { name: "CSE Sem 3" }); // the batch list comes from the server, wait for it
  await userEvent.selectOptions(screen.getByLabelText("Batch"), "1");
  await userEvent.type(screen.getByLabelText("Title"), title);
}

// ---------------------------------------------------------------- the editor
describe("assessment editor: creating", () => {
  it("creates an exam with times converted to UTC and problems in the chosen order", async () => {
    let sent = null;
    setupEditor({
      "POST /assessments": (o) => { sent = JSON.parse(o.body); return [201, created()]; },
      "GET /assessments/12": () => created(),
    });
    renderApp("/assessments/new", { token: "t" });
    await fillBasics();
    fireEvent.change(screen.getByLabelText("Opens at"), { target: { value: "2026-12-01T09:00" } });
    fireEvent.change(screen.getByLabelText("Closes at"), { target: { value: "2026-12-01T12:30" } });
    fireEvent.change(screen.getByLabelText("Minutes for each student"), { target: { value: "90" } });
    await userEvent.click(await screen.findByLabelText("Use Reverse a string"));
    await userEvent.click(screen.getByLabelText("Use Add two numbers"));
    const marks = screen.getByLabelText("Marks for Add two numbers");
    await userEvent.clear(marks);
    await userEvent.type(marks, "25");
    expect(screen.getByText(/2\) · 35 marks in total/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Move Add two numbers up" }));
    await userEvent.click(screen.getByRole("button", { name: "Create (as a draft)" }));
    await waitFor(() => expect(sent).not.toBeNull());
    expect(sent).toEqual({
      batch_id: 1, type: "exam", title: "Midterm", description: "",
      starts_at: new Date(2026, 11, 1, 9, 0).toISOString(), // typed in the teacher's own time zone, sent as UTC
      ends_at: new Date(2026, 11, 1, 12, 30).toISOString(),
      duration_min: 90,
      problems: [{ problem_id: 7, marks: 25 }, { problem_id: 8, marks: 10 }],
    });
    expect(await screen.findByRole("heading", { name: "Midterm" })).toBeInTheDocument(); // moved on to the new exam
  });

  it("an assignment has no duration box and sends no duration", async () => {
    let sent = null;
    setupEditor({ "POST /assessments": (o) => { sent = JSON.parse(o.body); return [201, created({ type: "assignment", duration_min: null })]; }, "GET /assessments/12": () => created({ type: "assignment", duration_min: null }) });
    renderApp("/assessments/new", { token: "t" });
    await fillBasics("Homework");
    await userEvent.selectOptions(screen.getByLabelText("Type"), "assignment");
    expect(screen.queryByLabelText("Minutes for each student")).not.toBeInTheDocument();
    await userEvent.click(await screen.findByLabelText("Use Prime check"));
    await userEvent.click(screen.getByRole("button", { name: "Create (as a draft)" }));
    await waitFor(() => expect(sent).not.toBeNull());
    expect(sent).toMatchObject({ type: "assignment", duration_min: null, problems: [{ problem_id: 9, marks: 10 }] });
  });

  it("asks for at least one problem before talking to the server", async () => {
    let called = false;
    setupEditor({ "POST /assessments": () => { called = true; return [201, created()]; } });
    renderApp("/assessments/new", { token: "t" });
    await fillBasics();
    await userEvent.click(screen.getByRole("button", { name: "Create (as a draft)" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Pick at least one problem.");
    expect(called).toBe(false);
  });

  it("shows the server's message when something is wrong", async () => {
    setupEditor({ "POST /assessments": () => [422, { detail: "The exam duration cannot be longer than the time window." }] });
    renderApp("/assessments/new", { token: "t" });
    await fillBasics();
    await userEvent.click(await screen.findByLabelText("Use Prime check"));
    await userEvent.click(screen.getByRole("button", { name: "Create (as a draft)" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("longer than the time window");
  });

  it("searches problems and can remove a pick", async () => {
    setupEditor();
    renderApp("/assessments/new", { token: "t" });
    await screen.findByLabelText("Use Prime check");
    await userEvent.type(screen.getByLabelText("Search problems"), "rev");
    expect(screen.queryByLabelText("Use Prime check")).not.toBeInTheDocument();
    await userEvent.click(screen.getByLabelText("Use Reverse a string"));
    expect(screen.getByText(/Problems \(1\)/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Remove Reverse a string" }));
    expect(screen.getByText(/Problems \(0\)/)).toBeInTheDocument();
  });

  it("warns that exam problems are hidden from students until the exam is over", async () => {
    setupEditor();
    renderApp("/assessments/new", { token: "t" });
    expect(await screen.findByText(/hidden from students until the exam window is over/)).toBeInTheDocument();
  });

  it("keeps students out", async () => {
    mockBackend({ "GET /auth/me": () => users.student });
    renderApp("/assessments/new", { token: "t" });
    expect(await screen.findByRole("alert")).toHaveTextContent("not allowed to open this page");
  });
});

describe("assessment editor: changing", () => {
  it("loads an assessment and saves with the problems", async () => {
    let sent = null;
    setupEditor({ "GET /assessments/12": () => created(), "PATCH /assessments/12": (o) => { sent = JSON.parse(o.body); return created(); } });
    renderApp("/assessments/12/edit", { token: "t" });
    const title = await screen.findByLabelText("Title");
    expect(title).toHaveValue("Midterm");
    expect(screen.getByLabelText("Batch")).toBeDisabled();
    expect(screen.getByLabelText("Type")).toBeDisabled(); // an exam cannot turn into an assignment
    expect(screen.getByLabelText("Minutes for each student")).toHaveValue(60);
    await userEvent.clear(title);
    await userEvent.type(title, "Final");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(sent).not.toBeNull());
    expect(sent.title).toBe("Final");
    expect(sent.problems).toEqual([{ problem_id: 7, marks: 10 }, { problem_id: 8, marks: 20 }]);
    expect(sent).not.toHaveProperty("batch_id");
  });

  it("when students have started, the problems are locked and not sent", async () => {
    let sent = null;
    setupEditor({ "GET /assessments/12": () => created({ has_activity: true }), "PATCH /assessments/12": (o) => { sent = JSON.parse(o.body); return created(); } });
    renderApp("/assessments/12/edit", { token: "t" });
    expect(await screen.findByText(/cannot be changed/)).toBeInTheDocument();
    expect(screen.getByLabelText("Marks for Add two numbers")).toBeDisabled();
    expect(screen.queryByLabelText("Search problems")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(sent).not.toBeNull());
    expect(sent).not.toHaveProperty("problems"); // the server would refuse them anyway
  });

  it("does not open for someone who cannot manage it", async () => {
    setupEditor({ "GET /assessments/12": () => created({ can_manage: false }) });
    renderApp("/assessments/12/edit", { token: "t" });
    expect(await screen.findByRole("alert")).toHaveTextContent("not allowed to edit");
  });
});

// ---------------------------------------------------------------- the results page
const ROW = (over = {}) => ({
  user_id: 20, name: "Asha", email: "asha@x.com", status: "finished", tab_switches: 0,
  per_problem: [{ problem_id: 7, marks: 5, possible: 10, passed: 1, total: 2, attempted: true }, { problem_id: 8, marks: 20, possible: 20, passed: 2, total: 2, attempted: true }],
  auto_marks: 25, override_marks: null, final_marks: 25, comment: null, pending: 0, judge_errors: 0, ...over,
});
const RESULTS = (over = {}) => ({
  assessment_id: 3, title: "Midterm", type: "exam", results_published: false, total_marks: 30,
  problems: [{ problem_id: 7, title: "Add two numbers", difficulty: "easy", marks: 10, position: 1 }, { problem_id: 8, title: "Reverse a string", difficulty: "medium", marks: 20, position: 2 }],
  rows: [ROW(), ROW({ user_id: 21, name: "Ravi", email: "ravi@x.com", status: "not_started", per_problem: [{ problem_id: 7, marks: 0, possible: 10, passed: 0, total: 0, attempted: false }, { problem_id: 8, marks: 0, possible: 20, passed: 0, total: 0, attempted: false }], auto_marks: 0, final_marks: 0 })],
  pending_total: 0, judge_errors_total: 0, ...over,
});
const results = (data = RESULTS(), extra = {}) =>
  mockBackend({ "GET /auth/me": () => users.teacher, "GET /assessments/3/results": () => data, ...extra });

describe("results page", () => {
  it("shows every student with marks per problem, status and tab switches", async () => {
    results(RESULTS({ rows: [ROW({ tab_switches: 3 }), RESULTS().rows[1]] }));
    renderApp("/assessments/3/results", { token: "t" });
    const row = (await screen.findByText("Asha")).closest("tr");
    expect(within(row).getByText("5 / 10")).toBeInTheDocument();
    expect(within(row).getByText("20 / 20")).toBeInTheDocument();
    expect(within(row).getByText("Finished")).toBeInTheDocument();
    expect(within(row).getByText("3")).toBeInTheDocument();
    expect(within(screen.getByText("Ravi").closest("tr")).getByText("Did not start")).toBeInTheDocument();
    expect(screen.getByText("Tab switches")).toBeInTheDocument();
    expect(screen.getByText("Results are hidden from students")).toBeInTheDocument();
  });

  it("an assignment has no tab-switch column", async () => {
    results(RESULTS({ type: "assignment" }));
    renderApp("/assessments/3/results", { token: "t" });
    await screen.findByText("Asha");
    expect(screen.queryByText("Tab switches")).not.toBeInTheDocument();
  });

  it("saves a hand-given mark and comment", async () => {
    let sent = null;
    results(RESULTS(), { "PUT /assessments/3/results/20": (o) => { sent = JSON.parse(o.body); return ROW({ override_marks: 27, final_marks: 27, comment: "Nice" }); } });
    renderApp("/assessments/3/results", { token: "t" });
    const save = await screen.findByRole("button", { name: "Save marks for Asha" });
    expect(save).toBeDisabled(); // nothing changed yet
    await userEvent.type(screen.getByLabelText("Final marks for Asha"), "27");
    await userEvent.type(screen.getByLabelText("Comment for Asha"), "  Nice ");
    await userEvent.click(save);
    await waitFor(() => expect(sent).toEqual({ override_marks: 27, comment: "Nice" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Save marks for Asha" })).toBeDisabled()); // saved
  });

  it("an empty marks box means use the automatic marks", async () => {
    let sent = null;
    results(RESULTS({ rows: [ROW({ override_marks: 20, final_marks: 20 })] }), { "PUT /assessments/3/results/20": (o) => { sent = JSON.parse(o.body); return ROW(); } });
    renderApp("/assessments/3/results", { token: "t" });
    const marks = await screen.findByLabelText("Final marks for Asha");
    expect(marks).toHaveValue(20);
    await userEvent.clear(marks);
    await userEvent.click(screen.getByRole("button", { name: "Save marks for Asha" }));
    await waitFor(() => expect(sent).toEqual({ override_marks: null, comment: null }));
  });

  it("shows the server's message beside the student when the mark is not allowed", async () => {
    results(RESULTS(), { "PUT /assessments/3/results/20": () => [422, { detail: "The marks cannot be more than the total (30.0)." }] });
    renderApp("/assessments/3/results", { token: "t" });
    await userEvent.type(await screen.findByLabelText("Final marks for Asha"), "99");
    await userEvent.click(screen.getByRole("button", { name: "Save marks for Asha" }));
    const row = screen.getByText("Asha").closest("tr");
    expect(await within(row).findByRole("alert")).toHaveTextContent("cannot be more than the total");
  });

  it("keeps checking while answers are still being judged", async () => {
    let calls = 0;
    results(null, { "GET /assessments/3/results": () => { calls += 1; return calls < 3 ? RESULTS({ pending_total: 2, rows: [ROW({ pending: 2 })] }) : RESULTS(); } });
    renderApp("/assessments/3/results", { token: "t" });
    expect(await screen.findByText(/2 answers are still being checked/)).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText(/still being checked/)).not.toBeInTheDocument());
    expect(calls).toBeGreaterThanOrEqual(3);
    const stopped = calls;
    await new Promise((r) => setTimeout(r, 150));
    expect(calls).toBe(stopped); // once nothing is pending it stops asking
  });

  it("tells the teacher about answers the judge could not check, and judges them again", async () => {
    let judged = false;
    results(null, {
      "GET /assessments/3/results": () => (judged ? RESULTS() : RESULTS({ judge_errors_total: 1, rows: [ROW({ judge_errors: 1, auto_marks: 0, final_marks: 0 })] })),
      "POST /assessments/3/rejudge": () => { judged = true; return { requeued: 1 }; },
    });
    renderApp("/assessments/3/results", { token: "t" });
    expect(await screen.findByText(/1 answer was not checked because the code judge had a problem/)).toBeInTheDocument();
    expect(screen.getByText("1 not checked")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Judge again" }));
    expect(await screen.findByText("1 answer sent to be checked again.")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText(/was not checked/)).not.toBeInTheDocument());
  });

  it("publishes and hides the results for students", async () => {
    let published = false;
    let sent = null;
    results(null, {
      "GET /assessments/3/results": () => RESULTS({ results_published: published }),
      "PATCH /assessments/3": (o) => { sent = JSON.parse(o.body); published = true; return {}; },
    });
    renderApp("/assessments/3/results", { token: "t" });
    await userEvent.click(await screen.findByRole("button", { name: "Publish results to students" }));
    expect(await screen.findByText("Students can see results")).toBeInTheDocument();
    expect(sent).toEqual({ results_published: true });
    expect(screen.getByRole("button", { name: "Hide results from students" })).toBeInTheDocument();
  });

  it("downloads the CSV with the login token", async () => {
    const spy = results(RESULTS(), { "GET /assessments/3/export": () => new Blob(["Name,Email\n"], { type: "text/csv" }) });
    const makeUrl = vi.fn(() => "blob:fake");
    const revoke = vi.fn();
    globalThis.URL.createObjectURL = makeUrl;
    globalThis.URL.revokeObjectURL = revoke;
    const downloads = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function () { downloads.push(this.download); });
    renderApp("/assessments/3/results", { token: "secret-token" });
    await userEvent.click(await screen.findByRole("button", { name: "Download CSV" }));
    await waitFor(() => expect(downloads).toEqual(["assessment-3-results.csv"]));
    expect(makeUrl).toHaveBeenCalledWith(expect.any(Blob));
    expect(revoke).toHaveBeenCalledWith("blob:fake");
    const call = spy.mock.calls.find(([url]) => String(url).endsWith("/assessments/3/export"));
    expect(call[1].headers.Authorization).toBe("Bearer secret-token");
  });

  it("shows an error when the download fails", async () => {
    results(RESULTS(), { "GET /assessments/3/export": () => [404, { detail: "Assessment not found." }] });
    renderApp("/assessments/3/results", { token: "t" });
    await userEvent.click(await screen.findByRole("button", { name: "Download CSV" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Assessment not found.");
  });

  it("explains an empty batch, and keeps students out", async () => {
    results(RESULTS({ rows: [] }));
    const first = renderApp("/assessments/3/results", { token: "t" });
    expect(await screen.findByText("There are no students in this batch yet.")).toBeInTheDocument();
    first.unmount();
    vi.restoreAllMocks();
    mockBackend({ "GET /auth/me": () => users.student });
    renderApp("/assessments/3/results", { token: "t" });
    expect(await screen.findByRole("alert")).toHaveTextContent("not allowed to open this page");
  });

  it("shows a clear message when the results cannot be opened", async () => {
    mockBackend({ "GET /auth/me": () => users.teacher, "GET /assessments/3/results": () => [404, { detail: "Assessment not found." }] });
    renderApp("/assessments/3/results", { token: "t" });
    expect(await screen.findByRole("alert")).toHaveTextContent("Assessment not found.");
  });
});
