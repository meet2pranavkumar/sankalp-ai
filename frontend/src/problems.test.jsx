import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { parseTags } from "./pages/ProblemEditor.jsx";
import { AI_OFF, mockBackend, renderApp, users } from "./testUtils.jsx";

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

const LANGS = [
  { key: "c", label: "C (GCC 9.2)" },
  { key: "python", label: "Python (3.8)" },
];

const PROBLEM = {
  id: 7, college_id: 1, created_by: 2, title: "Add two numbers", difficulty: "easy", tags: ["math"],
  statement_md: "Read two integers and **print** their sum.", time_limit_ms: 1000, memory_limit_mb: 128,
  is_public: false, can_edit: false,
  test_cases: [{ position: 1, input: "1 2\n", expected_output: "3\n", is_hidden: false, weight: 1 }],
};

const SIMPLE = { sankalp_simple_editor: "1" }; // a plain textarea, so tests do not need the Monaco editor

function problemPageBackend(extra = {}, me = users.student) {
  return mockBackend({
    "GET /auth/me": () => me,
    "GET /problems/7": () => PROBLEM,
    "GET /languages": () => LANGS,
    "GET /problems/7/submissions": () => [],
    "GET /ai/usage": () => AI_OFF,
    ...extra,
  });
}

async function typeCode(text) {
  const editor = await screen.findByLabelText("Code editor");
  await userEvent.clear(editor);
  await userEvent.click(editor);
  await userEvent.paste(text);
}

describe("problem list", () => {
  const list = [
    { id: 7, title: "Add two numbers", difficulty: "easy", tags: ["math"], is_public: false, solved: true },
    { id: 8, title: "Reverse a string", difficulty: "medium", tags: ["strings"], is_public: false, solved: false },
  ];

  it("shows problems, levels, topics and a tick for solved ones", async () => {
    mockBackend({ "GET /auth/me": () => users.student, "GET /problems": () => list });
    renderApp("/problems", { token: "t" });
    expect(await screen.findByText("Add two numbers")).toBeInTheDocument();
    expect(screen.getByText("Reverse a string")).toBeInTheDocument();
    expect(screen.getAllByLabelText("Solved")).toHaveLength(1);
    expect(screen.getByText("math")).toBeInTheDocument();
  });

  it("gives teachers a New problem button but not students", async () => {
    mockBackend({ "GET /auth/me": () => users.teacher, "GET /problems": () => list });
    const { unmount } = renderApp("/problems", { token: "t" });
    expect(await screen.findByRole("link", { name: "New problem" })).toBeInTheDocument();
    unmount();
    vi.restoreAllMocks();
    mockBackend({ "GET /auth/me": () => users.student, "GET /problems": () => list });
    renderApp("/problems", { token: "t" });
    await screen.findByText("Add two numbers");
    expect(screen.queryByRole("link", { name: "New problem" })).not.toBeInTheDocument();
  });

  it("sends the search words to the server", async () => {
    const spy = mockBackend({ "GET /auth/me": () => users.student, "GET /problems": () => list });
    renderApp("/problems", { token: "t" });
    await screen.findByText("Add two numbers");
    await userEvent.selectOptions(screen.getByLabelText("Filter by difficulty"), "medium");
    await waitFor(() => expect(spy.mock.calls.some(([url]) => String(url).includes("difficulty=medium"))).toBe(true));
  });
});

describe("problem page", () => {
  it("shows the statement and only the sample tests", async () => {
    problemPageBackend();
    renderApp("/problems/7", { token: "t", storage: SIMPLE });
    expect(await screen.findByRole("heading", { name: "Add two numbers" })).toBeInTheDocument();
    expect(screen.getByText("print").tagName).toBe("STRONG"); // Markdown is shown properly
    expect(screen.getByText(/Time limit 1000 ms/)).toBeInTheDocument();
    expect(screen.getByText("Sample 1")).toBeInTheDocument();
    expect(screen.queryByText("Edit")).not.toBeInTheDocument();
  });

  it("lets the author jump to the editor", async () => {
    problemPageBackend({ "GET /problems/7": () => ({ ...PROBLEM, can_edit: true }) }, users.teacher);
    renderApp("/problems/7", { token: "t", storage: SIMPLE });
    expect(await screen.findByRole("link", { name: "Edit" })).toHaveAttribute("href", "/problems/7/edit");
  });

  it("submits code, waits while the judge works, then shows Accepted", async () => {
    let polls = 0;
    let sent = null;
    problemPageBackend({
      "POST /submissions": (opts) => {
        sent = JSON.parse(opts.body);
        return [202, { id: 55, status: "queued" }];
      },
      "GET /submissions/55": () => {
        polls += 1;
        if (polls < 3) return { id: 55, status: polls === 1 ? "queued" : "running" };
        return { id: 55, status: "done", verdict: "accepted", passed_count: 2, total_count: 2, runtime_ms: 12, results: [
          { position: 1, verdict: "accepted", hidden: false }, { position: 2, verdict: "accepted", hidden: true },
        ] };
      },
    });
    renderApp("/problems/7", { token: "t", storage: SIMPLE });
    await typeCode("print(sum(map(int, input().split())))");
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));
    expect(screen.getByRole("button", { name: "Judging…" })).toBeDisabled();
    const card = (await screen.findByText("Submission result")).closest("section");
    expect(within(card).getAllByText("Accepted")).toHaveLength(3); // overall + one per test
    expect(within(card).getByText("2 of 2 tests passed")).toBeInTheDocument();
    expect(within(card).getByText("Hidden test 2")).toBeInTheDocument();
    expect(polls).toBe(3);
    expect(sent).toEqual({ problem_id: 7, language: "python", source_code: "print(sum(map(int, input().split())))" });
    expect(screen.getByRole("button", { name: "Submit" })).toBeEnabled();
  });

  it("explains a wrong answer on sample tests but shows nothing about hidden tests", async () => {
    problemPageBackend({
      "POST /submissions": () => [202, { id: 56, status: "queued" }],
      "GET /submissions/56": () => ({
        id: 56, status: "done", verdict: "wrong_answer", passed_count: 0, total_count: 2, runtime_ms: 5,
        results: [
          { position: 1, verdict: "wrong_answer", hidden: false, input: "1 2\n", expected: "3\n", actual: "999\n", error: "" },
          { position: 2, verdict: "wrong_answer", hidden: true },
        ],
      }),
    });
    renderApp("/problems/7", { token: "t", storage: SIMPLE });
    await typeCode("print(999)");
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));
    expect(await screen.findByText("0 of 2 tests passed")).toBeInTheDocument();
    expect(screen.getByText("Your output")).toBeInTheDocument();
    expect(screen.getByText("999")).toBeInTheDocument();
    const hidden = screen.getByText("Hidden test 2").closest("li");
    expect(within(hidden).queryByText("Expected")).not.toBeInTheDocument();
  });

  it("shows the compiler message for a compile error", async () => {
    problemPageBackend({
      "POST /submissions": () => [202, { id: 57, status: "queued" }],
      "GET /submissions/57": () => ({ id: 57, status: "done", verdict: "compile_error", compile_output: "main.c:1: error: expected ';'", passed_count: 0, total_count: 2, results: [] }),
    });
    renderApp("/problems/7", { token: "t", storage: { ...SIMPLE, sankalp_lang_7: "c" } });
    await typeCode("int main(");
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));
    expect(await screen.findByText("Compilation error")).toBeInTheDocument();
    expect(screen.getByText(/expected ';'/)).toBeInTheDocument();
    expect(screen.queryByText(/tests passed/)).not.toBeInTheDocument();
  });

  it("runs the code with the student's own input", async () => {
    let sent = null;
    problemPageBackend({
      "POST /run": (opts) => {
        sent = JSON.parse(opts.body);
        return [202, { id: 60, status: "queued" }];
      },
      "GET /submissions/60": () => ({ id: 60, status: "done", verdict: "ok", stdout: "42\n", stderr: "", compile_output: "", runtime_ms: 4 }),
    });
    renderApp("/problems/7", { token: "t", storage: SIMPLE });
    await typeCode("print(42)");
    const input = screen.getByLabelText("Test with your own input");
    await userEvent.clear(input);
    await userEvent.type(input, "20 22");
    await userEvent.click(screen.getByRole("button", { name: "Run" }));
    expect(await screen.findByText("Run result")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(sent).toMatchObject({ language: "python", stdin: "20 22", problem_id: 7 });
  });

  it("shows the server's message when the student is too fast", async () => {
    problemPageBackend({ "POST /submissions": () => [429, { detail: "Please wait 4 more second(s) before trying again." }] });
    renderApp("/problems/7", { token: "t", storage: SIMPLE });
    await typeCode("print(1)");
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Please wait 4 more second(s)");
    expect(screen.getByRole("button", { name: "Submit" })).toBeEnabled();
  });

  it("explains judge problems without blaming the student", async () => {
    problemPageBackend({
      "POST /submissions": () => [202, { id: 61, status: "queued" }],
      "GET /submissions/61": () => ({ id: 61, status: "error", verdict: "internal_error", message: "The code judge is not reachable right now.", results: null }),
    });
    renderApp("/problems/7", { token: "t", storage: SIMPLE });
    await typeCode("print(1)");
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));
    expect(await screen.findByText("Judge problem (not your fault)")).toBeInTheDocument();
    expect(screen.getByText(/not reachable/)).toBeInTheDocument();
  });

  it("keeps the code in the browser so a refresh loses nothing", async () => {
    problemPageBackend();
    const first = renderApp("/problems/7", { token: "t", storage: SIMPLE });
    await typeCode("print('saved')");
    first.unmount();
    problemPageBackend();
    // render again WITHOUT clearing storage
    const { render } = await import("@testing-library/react");
    const { MemoryRouter } = await import("react-router-dom");
    const { AuthProvider } = await import("./auth.jsx");
    const { AppRoutes } = await import("./App.jsx");
    render(<MemoryRouter initialEntries={["/problems/7"]}><AuthProvider><AppRoutes /></AuthProvider></MemoryRouter>);
    expect(await screen.findByLabelText("Code editor")).toHaveValue("print('saved')");
  });

  it("starts with a template for the chosen language", async () => {
    problemPageBackend();
    renderApp("/problems/7", { token: "t", storage: { ...SIMPLE, sankalp_lang_7: "c" } });
    const editor = await screen.findByLabelText("Code editor");
    expect(editor.value).toContain("int main(void)");
  });

  it("lets the student load an earlier submission", async () => {
    problemPageBackend({
      "GET /problems/7/submissions": () => [{ id: 3, language: "c", status: "done", verdict: "wrong_answer", passed_count: 1, total_count: 2, runtime_ms: 4, created_at: "2026-11-10T10:00:00Z" }],
      "GET /submissions/3": () => ({ id: 3, language: "c", source_code: "int main(){return 0;}", status: "done" }),
    });
    renderApp("/problems/7", { token: "t", storage: SIMPLE });
    await userEvent.click(await screen.findByRole("button", { name: "Use this code" }));
    await waitFor(() => expect(screen.getByLabelText("Code editor")).toHaveValue("int main(){return 0;}"));
  });

  it("shows a clear message for a problem the student cannot see", async () => {
    mockBackend({
      "GET /auth/me": () => users.student,
      "GET /problems/9": () => [404, { detail: "Problem not found." }],
      "GET /languages": () => LANGS,
      "GET /problems/9/submissions": () => [404, { detail: "Problem not found." }],
    });
    renderApp("/problems/9", { token: "t" });
    expect(await screen.findByRole("alert")).toHaveTextContent("Problem not found.");
  });
});

describe("problem editor", () => {
  it("lets a teacher create a problem with sample and hidden tests", async () => {
    let sent = null;
    mockBackend({
      "GET /auth/me": () => users.teacher,
      "POST /problems": (opts) => {
        sent = JSON.parse(opts.body);
        return [201, { ...PROBLEM, id: 12 }];
      },
      "GET /problems/12": () => PROBLEM,
      "GET /languages": () => LANGS,
      "GET /problems/12/submissions": () => [],
    });
    renderApp("/problems/new", { token: "t", storage: SIMPLE });
    await userEvent.type(await screen.findByLabelText("Title"), "Sum of two");
    await userEvent.type(screen.getByLabelText("Topics (comma separated)"), "math, Basics ,");
    await userEvent.type(screen.getByLabelText("Input for test 1"), "1 2");
    await userEvent.type(screen.getByLabelText("Expected output for test 1"), "3");
    await userEvent.type(screen.getByLabelText("Input for test 2"), "10 20");
    await userEvent.type(screen.getByLabelText("Expected output for test 2"), "30");
    await userEvent.click(screen.getByRole("button", { name: "Save problem" }));
    await waitFor(() => expect(sent).not.toBeNull());
    expect(sent).toMatchObject({
      title: "Sum of two", difficulty: "easy", tags: ["math", "Basics"], time_limit_ms: 1000, memory_limit_mb: 256, is_public: false,
      test_cases: [
        { input: "1 2", expected_output: "3", is_hidden: false },
        { input: "10 20", expected_output: "30", is_hidden: true },
      ],
    });
    expect(await screen.findByRole("heading", { name: "Add two numbers" })).toBeInTheDocument(); // moved to the new problem
  });

  it("can add and remove test cases", async () => {
    mockBackend({ "GET /auth/me": () => users.teacher });
    renderApp("/problems/new", { token: "t" });
    expect(await screen.findByText("Test cases (2)")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Add hidden test" }));
    expect(screen.getByText("Test cases (3)")).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: "Remove" })[0]);
    expect(screen.getByText("Test cases (2)")).toBeInTheDocument();
  });

  it("shows the server's error when the problem is not valid", async () => {
    mockBackend({
      "GET /auth/me": () => users.teacher,
      "POST /problems": () => [422, { detail: [{ loc: ["body", "test_cases"], msg: "Add at least one sample test case that students can see." }] }],
    });
    renderApp("/problems/new", { token: "t" });
    await userEvent.type(await screen.findByLabelText("Title"), "X");
    await userEvent.type(screen.getByLabelText("Expected output for test 1"), "1");
    await userEvent.type(screen.getByLabelText("Expected output for test 2"), "1");
    await userEvent.click(screen.getByRole("button", { name: "Save problem" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("at least one sample");
  });

  it("loads an existing problem for editing and saves with PUT", async () => {
    let sent = null;
    mockBackend({
      "GET /auth/me": () => users.teacher,
      "GET /problems/7": () => ({ ...PROBLEM, can_edit: true, test_cases: [
        { position: 1, input: "1 2\n", expected_output: "3\n", is_hidden: false, weight: 1 },
        { position: 2, input: "5 5\n", expected_output: "10\n", is_hidden: true, weight: 1 },
      ] }),
      "PUT /problems/7": (opts) => {
        sent = JSON.parse(opts.body);
        return PROBLEM;
      },
      "GET /languages": () => LANGS,
      "GET /problems/7/submissions": () => [],
    });
    renderApp("/problems/7/edit", { token: "t", storage: SIMPLE });
    const title = await screen.findByLabelText("Title");
    expect(title).toHaveValue("Add two numbers");
    expect(screen.getByLabelText("Topics (comma separated)")).toHaveValue("math");
    await userEvent.clear(title);
    await userEvent.type(title, "Add two numbers v2");
    await userEvent.click(screen.getByRole("button", { name: "Save problem" }));
    await waitFor(() => expect(sent).not.toBeNull());
    expect(sent.title).toBe("Add two numbers v2");
    expect(sent.test_cases).toHaveLength(2);
    expect(sent.test_cases[1].is_hidden).toBe(true);
  });

  it("does not let someone without edit rights use the editor", async () => {
    mockBackend({ "GET /auth/me": () => users.teacher, "GET /problems/7": () => PROBLEM /* can_edit false */ });
    renderApp("/problems/7/edit", { token: "t" });
    expect(await screen.findByRole("alert")).toHaveTextContent("not allowed to edit");
  });

  it("keeps students out of the editor page", async () => {
    mockBackend({ "GET /auth/me": () => users.student });
    renderApp("/problems/new", { token: "t" });
    expect(await screen.findByRole("alert")).toHaveTextContent("not allowed to open this page");
  });

  it("only the platform owner sees the sharing note", async () => {
    mockBackend({ "GET /auth/me": () => users.super });
    renderApp("/problems/new", { token: "t" });
    expect(await screen.findByText(/shared with every college/)).toBeInTheDocument();
  });
});

describe("parseTags", () => {
  it("splits, trims and drops empty pieces", () => {
    expect(parseTags(" a, b ,, c ,")).toEqual(["a", "b", "c"]);
    expect(parseTags("")).toEqual([]);
  });
});
