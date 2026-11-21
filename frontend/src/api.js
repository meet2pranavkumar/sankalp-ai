// All calls to the backend go through this file.
const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const TOKEN_KEY = "sankalp_token";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

let onUnauthorized = () => {};
export const setUnauthorizedHandler = (fn) => {
  onUnauthorized = fn;
};

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (token) => {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
};

// FastAPI sends errors as {detail: "text"} or {detail: [{msg, loc}, ...]}.
export function errorMessage(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0];
    const field = Array.isArray(first.loc) ? first.loc[first.loc.length - 1] : "";
    return field ? `${field}: ${first.msg}` : first.msg;
  }
  return "Something went wrong. Please try again.";
}

async function request(path, { method = "GET", body, auth = true } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = getToken();
  if (auth && token) headers.Authorization = `Bearer ${token}`;

  let res;
  try {
    res = await fetch(`${BASE_URL}/api/v1${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("Cannot reach the server. Is the backend running?", 0);
  }

  if (res.status === 204) return null;
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* no body */
  }
  if (!res.ok) {
    if (res.status === 401 && auth) onUnauthorized();
    throw new ApiError(errorMessage(data?.detail), res.status);
  }
  return data;
}

export const api = {
  getHealth: () => request("/health", { auth: false }),
  login: (email, password) => request("/auth/login", { method: "POST", body: { email, password }, auth: false }),
  me: () => request("/auth/me"),
  changePassword: (current_password, new_password) =>
    request("/auth/change-password", { method: "POST", body: { current_password, new_password } }),

  listColleges: () => request("/colleges"),
  createCollege: (body) => request("/colleges", { method: "POST", body }),

  listUsers: (params = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v != null)).toString();
    return request(`/users${qs ? `?${qs}` : ""}`);
  },
  createUser: (body) => request("/users", { method: "POST", body }),
  bulkCreate: (body) => request("/users/bulk", { method: "POST", body }),
  updateUser: (id, body) => request(`/users/${id}`, { method: "PATCH", body }),
  resetPassword: (id) => request(`/users/${id}/reset-password`, { method: "POST" }),

  listLanguages: () => request("/languages", { auth: false }),
  listProblems: (params = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v != null)).toString();
    return request(`/problems${qs ? `?${qs}` : ""}`);
  },
  getProblem: (id) => request(`/problems/${id}`),
  createProblem: (body) => request("/problems", { method: "POST", body }),
  updateProblem: (id, body) => request(`/problems/${id}`, { method: "PUT", body }),
  run: (body) => request("/run", { method: "POST", body }),
  submit: (body) => request("/submissions", { method: "POST", body }),
  getSubmission: (id) => request(`/submissions/${id}`),
  mySubmissions: (problemId) => request(`/problems/${problemId}/submissions`),

  listCourses: () => request("/courses"),
  getCourse: (id) => request(`/courses/${id}`),
  createCourse: (body) => request("/courses", { method: "POST", body }),
  updateCourse: (id, body) => request(`/courses/${id}`, { method: "PATCH", body }),
  deleteCourse: (id) => request(`/courses/${id}`, { method: "DELETE" }),
  duplicateCourse: (id) => request(`/courses/${id}/duplicate`, { method: "POST" }),
  addUnit: (courseId, title) => request(`/courses/${courseId}/units`, { method: "POST", body: { title } }),
  renameUnit: (id, title) => request(`/units/${id}`, { method: "PATCH", body: { title } }),
  deleteUnit: (id) => request(`/units/${id}`, { method: "DELETE" }),
  reorderUnits: (courseId, ids) => request(`/courses/${courseId}/units/order`, { method: "PUT", body: { ids } }),
  addLesson: (unitId, title) => request(`/units/${unitId}/lessons`, { method: "POST", body: { title } }),
  reorderLessons: (unitId, ids) => request(`/units/${unitId}/lessons/order`, { method: "PUT", body: { ids } }),
  getLesson: (id) => request(`/lessons/${id}`),
  updateLesson: (id, body) => request(`/lessons/${id}`, { method: "PATCH", body }),
  deleteLesson: (id) => request(`/lessons/${id}`, { method: "DELETE" }),
  completeLesson: (id) => request(`/lessons/${id}/complete`, { method: "POST" }),
  uncompleteLesson: (id) => request(`/lessons/${id}/complete`, { method: "DELETE" }),

  listAssessments: () => request("/assessments"),
  getAssessment: (id) => request(`/assessments/${id}`),
  createAssessment: (body) => request("/assessments", { method: "POST", body }),
  updateAssessment: (id, body) => request(`/assessments/${id}`, { method: "PATCH", body }),
  deleteAssessment: (id) => request(`/assessments/${id}`, { method: "DELETE" }),
  startExam: (id) => request(`/assessments/${id}/start`, { method: "POST" }),
  finishExam: (id) => request(`/assessments/${id}/finish`, { method: "POST" }),
  tabSwitch: (id) => request(`/assessments/${id}/tab-switch`, { method: "POST" }),
  getAssessmentProblem: (id, problemId) => request(`/assessments/${id}/problems/${problemId}`),
  assessmentSubmissions: (id, problemId) => request(`/assessments/${id}/problems/${problemId}/submissions`),
  saveDraft: (id, problemId, body) => request(`/assessments/${id}/problems/${problemId}/draft`, { method: "PUT", body }),
  getDraft: (id, problemId) => request(`/assessments/${id}/problems/${problemId}/draft`),
  myResult: (id) => request(`/assessments/${id}/my-result`),
  assessmentResults: (id) => request(`/assessments/${id}/results`),
  setOverride: (id, userId, body) => request(`/assessments/${id}/results/${userId}`, { method: "PUT", body }),
  rejudge: (id) => request(`/assessments/${id}/rejudge`, { method: "POST" }),
  // The file needs the login token, so a plain link will not work. We fetch it and hand the browser a download.
  downloadResults: async (id) => {
    let res;
    try {
      res = await fetch(`${BASE_URL}/api/v1/assessments/${id}/export`, { headers: { Authorization: `Bearer ${getToken()}` } });
    } catch {
      throw new ApiError("Cannot reach the server. Is the backend running?", 0);
    }
    if (!res.ok) {
      let detail;
      try {
        detail = (await res.json()).detail;
      } catch {
        /* no body */
      }
      throw new ApiError(errorMessage(detail), res.status);
    }
    return res.blob();
  },

  listBatches: () => request("/batches"),
  getBatch: (id) => request(`/batches/${id}`),
  createBatch: (body) => request("/batches", { method: "POST", body }),
  listMembers: (id) => request(`/batches/${id}/members`),
  addMembers: (id, user_ids) => request(`/batches/${id}/members`, { method: "POST", body: { user_ids } }),
  removeMember: (id, userId) => request(`/batches/${id}/members/${userId}`, { method: "DELETE" }),
};
