import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mockBackend, renderApp, users } from "./testUtils.jsx";

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("login", () => {
  it("sends a visitor without a token to the login page", async () => {
    mockBackend({});
    renderApp("/people");
    expect(await screen.findByRole("button", { name: "Log in" })).toBeInTheDocument();
  });

  it("logs in, saves the token and shows the home page", async () => {
    mockBackend({ "POST /auth/login": () => ({ access_token: "tok123", token_type: "bearer", user: users.teacher }) });
    renderApp("/login");
    await userEvent.type(screen.getByLabelText("Email"), "t@x.com");
    await userEvent.type(screen.getByLabelText("Password"), "password123");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByText("Welcome, Teena Teacher")).toBeInTheDocument();
    expect(localStorage.getItem("sankalp_token")).toBe("tok123");
  });

  it("shows the server's message when the password is wrong", async () => {
    mockBackend({ "POST /auth/login": () => [401, { detail: "Wrong email or password." }] });
    renderApp("/login");
    await userEvent.type(screen.getByLabelText("Email"), "t@x.com");
    await userEvent.type(screen.getByLabelText("Password"), "wrong-password");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Wrong email or password.");
    expect(localStorage.getItem("sankalp_token")).toBeNull();
  });

  it("tells the user when the backend is not running", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    renderApp("/login");
    await userEvent.type(screen.getByLabelText("Email"), "t@x.com");
    await userEvent.type(screen.getByLabelText("Password"), "password123");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server");
  });

  it("drops a saved token that the server no longer accepts", async () => {
    mockBackend({ "GET /auth/me": () => [401, { detail: "Please log in again." }] });
    renderApp("/", { token: "old-token" });
    expect(await screen.findByRole("button", { name: "Log in" })).toBeInTheDocument();
    expect(localStorage.getItem("sankalp_token")).toBeNull();
  });
});

describe("role based screens", () => {
  it("shows a student only the links a student may use", async () => {
    mockBackend({ "GET /auth/me": () => users.student });
    renderApp("/", { token: "t" });
    const nav = await screen.findByRole("navigation");
    expect(within(nav).getByText("Batches")).toBeInTheDocument();
    expect(within(nav).queryByText("People")).not.toBeInTheDocument();
    expect(within(nav).queryByText("Colleges")).not.toBeInTheDocument();
  });

  it("blocks a student from opening the People page", async () => {
    mockBackend({ "GET /auth/me": () => users.student });
    renderApp("/people", { token: "t" });
    expect(await screen.findByRole("alert")).toHaveTextContent("not allowed");
  });

  it("blocks a teacher from the Colleges page", async () => {
    mockBackend({ "GET /auth/me": () => users.teacher });
    renderApp("/colleges", { token: "t" });
    expect(await screen.findByRole("alert")).toHaveTextContent("not allowed");
  });

  it("lets a teacher add only students", async () => {
    mockBackend({
      "GET /auth/me": () => users.teacher,
      "GET /users": () => [users.student],
      "GET /batches": () => [],
    });
    renderApp("/people", { token: "t" });
    const roleSelect = await screen.findByLabelText("Role");
    expect(within(roleSelect).getAllByRole("option").map((o) => o.textContent)).toEqual(["Student"]);
    expect(await screen.findByText("Sam Student")).toBeInTheDocument();
  });

  it("lets the platform owner pick a college and create a college admin", async () => {
    let sent = null;
    mockBackend({
      "GET /auth/me": () => users.super,
      "GET /users": () => [],
      "GET /colleges": () => [{ id: 7, name: "Govt Polytechnic", code: "GP", city: null, state: null }],
      "POST /users": (opts) => {
        sent = JSON.parse(opts.body);
        return [201, { ...users.teacher, role: "admin", name: "New Admin" }];
      },
    });
    renderApp("/people", { token: "t" });
    const roleSelect = await screen.findByLabelText("Role");
    expect(within(roleSelect).getAllByRole("option").map((o) => o.textContent)).toContain("College admin");
    await userEvent.type(screen.getByLabelText("Full name"), "New Admin");
    await userEvent.type(screen.getByLabelText("Email"), "admin@gp.edu");
    await userEvent.type(screen.getByLabelText(/^Password/), "password123");
    await userEvent.selectOptions(roleSelect, "admin");
    const collegeSelects = await screen.findAllByLabelText("College"); // [0] = add-one form, [1] = bulk form
    await userEvent.selectOptions(collegeSelects[0], "7");
    await userEvent.click(screen.getByRole("button", { name: "Add person" }));
    await waitFor(() => expect(sent).not.toBeNull());
    expect(sent).toMatchObject({ role: "admin", college_id: 7, email: "admin@gp.edu" });
  });

  it("shows temporary passwords after a bulk upload", async () => {
    mockBackend({
      "GET /auth/me": () => users.teacher,
      "GET /users": () => [],
      "GET /batches": () => [],
      "POST /users/bulk": () => [
        [201, [
          { name: "Ravi", email: "ravi@x.com", temp_password: "Abc12345xy", error: null },
          { name: "Old", email: "old@x.com", temp_password: null, error: "Email already registered." },
        ]],
      ][0],
    });
    renderApp("/people", { token: "t" });
    await userEvent.type(await screen.findByLabelText(/One student per line/), "Ravi, ravi@x.com{enter}Old, old@x.com");
    await userEvent.click(screen.getByRole("button", { name: "Add students" }));
    expect(await screen.findByLabelText("New student passwords")).toHaveValue("Ravi, ravi@x.com, Abc12345xy");
    expect(screen.getByText(/old@x.com: Email already registered/)).toBeInTheDocument();
  });
});
