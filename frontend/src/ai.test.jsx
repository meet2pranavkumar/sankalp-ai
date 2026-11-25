import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { latestError } from "./pages/ProblemPage.jsx";
import { AI_OFF, mockBackend, renderApp, users } from "./testUtils.jsx";

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

const at = (ms) => new Date(Date.now() + ms).toISOString();
const MIN = 60_000;
const LANGS = [{ key: "c", label: "C (GCC 9.2)" }, { key: "python", label: "Python (3.8)" }];
const SIMPLE = { sankalp_simple_editor: "1" };
const PROBLEM = {
  id: 7, college_id: 1, created_by: 2, title: "Add two numbers", difficulty: "easy", tags: [], statement_md: "Print the sum.",
  time_limit_ms: 1000, memory_limit_mb: 128, is_public: false, can_edit: false,
  test_cases: [{ position: 1, input: "1 2\n", expected_output: "3\n", is_hidden: false, weight: 1 }],
};
const usage = (over = {}) => ({
  enabled: true, blocked_reason: null, hints_used: 0, hints_limit: 5, explains_used: 0, explains_limit: 10,
  available_levels: [1], retry_after_seconds: 0, recent: [], ...over,
});
const answer = (kind, level, text, u, id = 1) => ({ id, kind, level, text, usage: u });

const backend = (extra = {}, me = users.student) =>
  mockBackend({
    "GET /auth/me": () => me,
    "GET /problems/7": () => PROBLEM,
    "GET /languages": () => LANGS,
    "GET /problems/7/submissions": () => [],
    "GET /ai/usage": () => usage(),
    ...extra,
  });
const open = () => renderApp("/problems/7", { token: "t", storage: SIMPLE });
const button = (name) => screen.getByRole("button", { name });

async function typeCode(text) {
  const editor = await screen.findByLabelText("Code editor");
  await userEvent.clear(editor);
  await userEvent.click(editor);
  await userEvent.paste(text);
}

// ---------------------------------------------------------------- finding the error to explain
describe("latestError", () => {
  it("takes the compiler message or the runtime message of the latest Run", () => {
    expect(latestError({ verdict: "compile_error", compile_output: "error: boom" }, null)).toBe("error: boom");
    expect(latestError({ verdict: "runtime_error", stderr: "ZeroDivisionError" }, null)).toBe("ZeroDivisionError");
    expect(latestError({ verdict: "runtime_error", stderr: "", message: "NZEC" }, null)).toBe("NZEC");
  });
  it("uses the error of a Submit when the Run was fine, but not a hidden exam result", () => {
    expect(latestError({ verdict: "ok" }, { verdict: "compile_error", compile_output: "main.c:1: error" })).toBe("main.c:1: error");
    expect(latestError(null, { verdict: "runtime_error", results: [{ error: "" }, { error: "signal 11" }] })).toBe("signal 11");
    expect(latestError(null, { hidden: true, verdict: "compile_error", compile_output: "x" })).toBeNull();
  });
  it("has nothing to explain when the code worked", () => {
    expect(latestError({ verdict: "ok", stdout: "3" }, { verdict: "accepted" })).toBeNull();
    expect(latestError(null, null)).toBeNull();
  });
});

// ---------------------------------------------------------------- the panel
describe("AI helper panel", () => {
  it("shows the three hint buttons, and only the first is open", async () => {
    backend();
    open();
    expect(await screen.findByRole("button", { name: "Give me a nudge" })).toBeEnabled(); // (the title shows while it is still loading)
    expect(screen.getByText("Need help?")).toBeInTheDocument();
    expect(button("Explain the method")).toBeDisabled();
    expect(button("Show pseudo-code")).toBeDisabled();
    expect(screen.getByText(/Hints used today for this problem: 0 of 5/)).toBeInTheDocument();
    expect(screen.getByText(/will not give you the full answer/)).toBeInTheDocument();
    expect(screen.getByText(/can make mistakes/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Explain my error" })).not.toBeInTheDocument(); // nothing to explain yet
  });

  it("asks for a hint with the problem, language and the code written so far", async () => {
    let sent = null;
    backend({
      "POST /ai/hint": (o) => {
        sent = JSON.parse(o.body);
        return answer("hint", 1, "What must the program print for the first sample?", usage({ hints_used: 1, available_levels: [1, 2] }));
      },
    });
    open();
    await typeCode("print('my try')");
    await userEvent.click(await screen.findByRole("button", { name: "Give me a nudge" }));
    expect(await screen.findByText("What must the program print for the first sample?")).toBeInTheDocument();
    expect(screen.getByText("Hint 1: a nudge")).toBeInTheDocument();
    expect(sent).toEqual({ problem_id: 7, level: 1, language: "python", source_code: "print('my try')" });
    expect(screen.getByText(/Hints used today for this problem: 1 of 5/)).toBeInTheDocument();
    expect(button("Explain the method")).toBeEnabled(); // hint 2 opened after reading hint 1
    expect(button("Show pseudo-code")).toBeDisabled();
  });

  it("shows pseudo-code in a code block and newest answers first", async () => {
    const replies = [
      answer("hint", 2, "1. Read the numbers.\n2. Add them.", usage({ hints_used: 2, available_levels: [1, 2, 3] }), 2),
      answer("hint", 3, "```\nread two numbers\nadd them\nprint the total\n```", usage({ hints_used: 3, available_levels: [1, 2, 3] }), 3),
    ];
    backend({ "GET /ai/usage": () => usage({ hints_used: 1, available_levels: [1, 2] }), "POST /ai/hint": () => replies.shift() });
    open();
    await userEvent.click(await screen.findByRole("button", { name: "Explain the method" }));
    await screen.findByText("Hint 2: the method");
    await userEvent.click(screen.getByRole("button", { name: "Show pseudo-code" }));
    const pre = await screen.findByText(/read two numbers/);
    expect(pre.closest("pre")).not.toBeNull();
    const titles = screen.getAllByText(/^Hint \d: /).map((n) => n.textContent);
    expect(titles).toEqual(["Hint 3: pseudo-code", "Hint 2: the method"]);
  });

  it("shows the answers from the last 24 hours when the page opens", async () => {
    backend({
      "GET /ai/usage": () => usage({ hints_used: 2, available_levels: [1, 2, 3], recent: [
        { id: 9, kind: "hint", level: 2, text: "Break it into steps.", created_at: at(-MIN) },
        { id: 8, kind: "hint", level: 1, text: "Try the sample by hand.", created_at: at(-2 * MIN) },
      ] }),
    });
    open();
    expect(await screen.findByText("Break it into steps.")).toBeInTheDocument();
    expect(screen.getByText("Try the sample by hand.")).toBeInTheDocument();
  });

  it("shows the server's message and refreshes the real numbers when a request is refused", async () => {
    let usageCalls = 0;
    backend({
      "GET /ai/usage": () => { usageCalls += 1; return usage({ hints_used: usageCalls > 1 ? 3 : 0 }); },
      "POST /ai/hint": () => [429, { detail: "You have used all 5 hints for this problem today. Try again tomorrow, or ask your teacher." }],
    });
    open();
    await userEvent.click(await screen.findByRole("button", { name: "Give me a nudge" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("used all 5 hints");
    await waitFor(() => expect(screen.getByText(/Hints used today for this problem: 3 of 5/)).toBeInTheDocument());
    expect(usageCalls).toBe(2);
  });

  it("asks the student to wait between hints, then opens the buttons again", async () => {
    backend({ "GET /ai/usage": () => usage({ hints_used: 1, available_levels: [1, 2], retry_after_seconds: 1 }) });
    open();
    expect(await screen.findByText(/You can ask again in 1 second/)).toBeInTheDocument();
    expect(button("Give me a nudge")).toBeDisabled();
    expect(button("Explain the method")).toBeDisabled();
    await waitFor(() => expect(button("Explain the method")).toBeEnabled(), { timeout: 3000 });
    expect(screen.queryByText(/You can ask again in/)).not.toBeInTheDocument();
  });

  it("closes everything when all the hints for today are used", async () => {
    backend({ "GET /ai/usage": () => usage({ hints_used: 5, available_levels: [] }) });
    open();
    expect(await screen.findByText(/used all your hints for this problem today/)).toBeInTheDocument();
    for (const name of ["Give me a nudge", "Explain the method", "Show pseudo-code"]) expect(button(name)).toBeDisabled();
  });

  it("shows why the helper is closed instead of the buttons", async () => {
    backend({ "GET /ai/usage": () => usage({ enabled: false, blocked_reason: "Your teacher turned the AI helper off for this assignment.", available_levels: [] }) });
    open();
    expect(await screen.findByText("Your teacher turned the AI helper off for this assignment.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Give me a nudge" })).not.toBeInTheDocument();
  });

  it("says so when the helper is not set up", async () => {
    backend({ "GET /ai/usage": () => AI_OFF });
    open();
    expect(await screen.findByText(/not set up yet/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Give me a nudge" })).not.toBeInTheDocument();
  });

  it("shows an error if the helper cannot be reached", async () => {
    backend({ "GET /ai/usage": () => [500, { detail: "Something broke." }] });
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent("Something broke.");
  });
});

// ---------------------------------------------------------------- explaining an error
describe("explain my error", () => {
  const withRun = (verdict, extra = {}) => ({
    "POST /run": () => [202, { id: 70, status: "queued" }],
    "GET /submissions/70": () => ({ id: 70, status: "done", verdict, hidden: false, ...extra }),
  });

  it("appears after a compile error and sends that error with the code", async () => {
    let sent = null;
    backend({
      ...withRun("compile_error", { compile_output: "main.c:3: error: expected ';' before 'return'" }),
      "POST /ai/explain-error": (o) => { sent = JSON.parse(o.body); return answer("explain", null, "A semicolon is missing. Look at the line before line 3.", usage({ explains_used: 1 })); },
    });
    open();
    await typeCode("int main(){ return 0 }");
    await userEvent.click(await screen.findByRole("button", { name: "Run" }));
    await userEvent.click(await screen.findByRole("button", { name: "Explain my error" }));
    expect(await screen.findByText("Your error, explained")).toBeInTheDocument();
    expect(screen.getByText(/A semicolon is missing/)).toBeInTheDocument();
    expect(sent).toEqual({ problem_id: 7, language: "python", source_code: "int main(){ return 0 }", error_text: "main.c:3: error: expected ';' before 'return'" });
  });

  it("also appears after a runtime error", async () => {
    backend(withRun("runtime_error", { stderr: "ZeroDivisionError: division by zero" }));
    open();
    await typeCode("print(1/0)");
    await userEvent.click(await screen.findByRole("button", { name: "Run" }));
    expect(await screen.findByRole("button", { name: "Explain my error" })).toBeInTheDocument();
  });

  it("does not appear when the code ran fine", async () => {
    backend(withRun("ok", { stdout: "3\n" }));
    open();
    await typeCode("print(3)");
    await userEvent.click(await screen.findByRole("button", { name: "Run" }));
    await screen.findByText("Run result");
    expect(screen.queryByRole("button", { name: "Explain my error" })).not.toBeInTheDocument();
  });

  it("is closed when the day's explanations are used up", async () => {
    backend({ ...withRun("compile_error", { compile_output: "error" }), "GET /ai/usage": () => usage({ explains_used: 10 }) });
    open();
    await typeCode("x");
    await userEvent.click(await screen.findByRole("button", { name: "Run" }));
    expect(await screen.findByRole("button", { name: "Explain my error" })).toBeDisabled();
  });
});

// ---------------------------------------------------------------- where the helper appears
describe("where the helper appears", () => {
  const ASSESSMENT = (type, over = {}) => ({
    id: 3, title: "Midterm", type, batch_id: 1, batch_name: "CSE", starts_at: at(-5 * MIN), ends_at: at(120 * MIN), duration_min: type === "exam" ? 60 : null,
    is_published: true, results_published: false, total_marks: 10, problem_count: 1, status: type === "exam" ? "in_progress" : "open",
    my_marks: null, can_manage: false, description: "", server_now: at(0), ai_hints_allowed: true,
    attempt: type === "exam" ? { started_at: at(-5 * MIN), deadline_at: at(55 * MIN), finished_at: null } : null,
    problems: [{ problem_id: 7, title: "Add two numbers", difficulty: "easy", marks: 10, position: 1, score: null }], has_activity: false, ...over,
  });
  const inAssessment = (type, over) => {
    const spy = mockBackend({
      "GET /auth/me": () => users.student,
      "GET /assessments/3/problems/7": () => PROBLEM,
      "GET /languages": () => LANGS,
      "GET /assessments/3": () => ASSESSMENT(type, over),
      "GET /assessments/3/problems/7/submissions": () => [],
      "GET /assessments/3/problems/7/draft": () => null,
      "GET /ai/usage": () => usage(),
    });
    renderApp("/assessments/3/problems/7", { token: "t", storage: SIMPLE });
    return spy;
  };

  it("is not even asked about during an exam", async () => {
    const spy = inAssessment("exam");
    await screen.findByRole("timer");
    expect(screen.queryByText("Need help?")).not.toBeInTheDocument();
    expect(spy.mock.calls.some(([url]) => String(url).includes("/ai/"))).toBe(false);
  });

  it("is available in an assignment", async () => {
    inAssessment("assignment");
    expect(await screen.findByText("Need help?")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Give me a nudge" })).toBeInTheDocument();
  });

  it("is not shown to teachers", async () => {
    const spy = backend({}, users.teacher);
    open();
    await screen.findByRole("heading", { name: "Add two numbers" });
    expect(screen.queryByText("Need help?")).not.toBeInTheDocument();
    expect(spy.mock.calls.some(([url]) => String(url).includes("/ai/"))).toBe(false);
  });
});

// ---------------------------------------------------------------- what the teacher sees
describe("where students need help (teacher page)", () => {
  const ROWS = [
    { problem_id: 7, title: "Add two numbers", students: 12, requests: 40, hints: 31, explains: 9, level3: 6, flagged: 2, errors: 1, last_at: at(-MIN) },
    { problem_id: 8, title: "Prime check", students: 3, requests: 4, hints: 4, explains: 0, level3: 0, flagged: 0, errors: 0, last_at: at(-MIN) },
  ];
  const REQUESTS = [
    { id: 3, student_name: "Asha", student_email: "a@x.com", kind: "hint", level: 3, status: "fallback", flagged: true, text: "Write the steps in plain words.", created_at: at(-MIN) },
    { id: 2, student_name: "Ravi", student_email: "r@x.com", kind: "explain", level: null, status: "ok", flagged: false, text: "A semicolon is missing.", created_at: at(-2 * MIN) },
    { id: 1, student_name: "Asha", student_email: "a@x.com", kind: "hint", level: 1, status: "ok", flagged: true, text: "Try the sample by hand.", created_at: at(-3 * MIN) },
    { id: 0, student_name: "Sam", student_email: "s@x.com", kind: "hint", level: 2, status: "error", flagged: false, text: "The AI helper is very busy.", created_at: at(-4 * MIN) },
  ];
  const page = (rows = ROWS) =>
    mockBackend({ "GET /auth/me": () => users.teacher, "GET /ai/insights": () => rows, "GET /ai/requests": () => REQUESTS });

  it("lists the problems where help is asked for most", async () => {
    page();
    renderApp("/ai-help", { token: "t" });
    const row = (await screen.findByText("Add two numbers")).closest("tr");
    expect(within(row).getAllByRole("cell").map((c) => c.textContent).slice(0, 8)).toEqual(["Add two numbers", "12", "40", "31", "6", "9", "2", "1"]);
    expect(screen.getAllByRole("row")[2]).toHaveTextContent("Prime check"); // the order the server gave: most requests first
    expect(screen.getByText(/Where students need help/)).toBeInTheDocument();
  });

  it("shows what each student was told, with plain-words labels", async () => {
    page();
    renderApp("/ai-help", { token: "t" });
    await userEvent.click(await screen.findByRole("button", { name: "See what students were told for Add two numbers" }));
    expect(await screen.findByText("Write the steps in plain words.")).toBeInTheDocument();
    expect(screen.getByText("Hint 3 (pseudo-code)")).toBeInTheDocument();
    expect(screen.getByText("Error explained")).toBeInTheDocument();
    expect(screen.getByText("Safe text shown instead")).toBeInTheDocument(); // the AI tried to give the answer twice
    expect(screen.getByText("First AI answer refused")).toBeInTheDocument();
    expect(screen.getByText("AI service problem")).toBeInTheDocument();
    expect(screen.getAllByText("Asha")).toHaveLength(2);
    await userEvent.click(screen.getByRole("button", { name: "See what students were told for Add two numbers" }));
    expect(screen.queryByText("What students were told")).not.toBeInTheDocument(); // Hide
  });

  it("changes the time range and asks again", async () => {
    const spy = page();
    renderApp("/ai-help", { token: "t" });
    await screen.findByText("Add two numbers");
    await userEvent.selectOptions(screen.getByLabelText("Time"), "7");
    await waitFor(() => expect(spy.mock.calls.some(([url]) => String(url).includes("/ai/insights?days=7"))).toBe(true));
  });

  it("explains an empty list", async () => {
    page([]);
    renderApp("/ai-help", { token: "t" });
    expect(await screen.findByText(/No one has asked the AI helper/)).toBeInTheDocument();
  });

  it("keeps students out", async () => {
    mockBackend({ "GET /auth/me": () => users.student });
    renderApp("/ai-help", { token: "t" });
    expect(await screen.findByRole("alert")).toHaveTextContent("not allowed to open this page");
  });
});
