import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import { AppRoutes } from "./App.jsx";
import { AuthProvider } from "./auth.jsx";

export const users = {
  teacher: { id: 2, name: "Teena Teacher", email: "t@x.com", role: "teacher", college_id: 1, college_name: "Govt Polytechnic", is_active: true },
  student: { id: 3, name: "Sam Student", email: "s@x.com", role: "student", college_id: 1, college_name: "Govt Polytechnic", is_active: true },
  admin: { id: 4, name: "Adam Admin", email: "a@x.com", role: "admin", college_id: 1, college_name: "Govt Polytechnic", is_active: true },
  super: { id: 1, name: "Olive Owner", email: "o@x.com", role: "super_admin", college_id: null, college_name: null, is_active: true },
};

// Fake backend: handlers is { "GET /users": () => body | [status, body] }
export function mockBackend(handlers) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (url, options = {}) => {
    const path = new URL(url).pathname.replace("/api/v1", "");
    const key = `${options.method || "GET"} ${path}`;
    const handler = handlers[key];
    if (!handler) return { ok: false, status: 404, json: async () => ({ detail: `no mock for ${key}` }) };
    const result = handler(options);
    const [status, body] = Array.isArray(result) && typeof result[0] === "number" ? result : [200, result];
    return { ok: status < 400, status, json: async () => body, blob: async () => body };
  });
}

export function renderApp(path = "/", { token, storage = {} } = {}) {
  localStorage.clear();
  if (token) localStorage.setItem("sankalp_token", token);
  for (const [key, value] of Object.entries(storage)) localStorage.setItem(key, value);
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </MemoryRouter>
  );
}
