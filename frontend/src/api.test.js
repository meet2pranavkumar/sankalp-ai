import { describe, expect, it } from "vitest";
import { errorMessage } from "./api.js";
import { parseStudentLines } from "./pages/People.jsx";

describe("errorMessage", () => {
  it("passes plain text through", () => {
    expect(errorMessage("Wrong email or password.")).toBe("Wrong email or password.");
  });
  it("makes FastAPI validation errors readable", () => {
    expect(errorMessage([{ loc: ["body", "password"], msg: "String should have at least 8 characters" }])).toBe(
      "password: String should have at least 8 characters"
    );
  });
  it("has a safe fallback", () => {
    expect(errorMessage(undefined)).toMatch(/Something went wrong/);
  });
});

describe("parseStudentLines", () => {
  it("reads 'name, email' lines and ignores blank lines", () => {
    expect(parseStudentLines("Ravi Kumar, ravi@x.com\n\n  Anita Singh ,anita@x.com  \n")).toEqual([
      { name: "Ravi Kumar", email: "ravi@x.com" },
      { name: "Anita Singh", email: "anita@x.com" },
    ]);
  });
  it("leaves the email empty when a line has only a name", () => {
    expect(parseStudentLines("Just A Name")).toEqual([{ name: "Just A Name", email: "" }]);
  });
});
