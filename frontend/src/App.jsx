import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth.jsx";
import Layout, { ProtectedRoute } from "./Layout.jsx";
import Account from "./pages/Account.jsx";
import AssessmentEditor from "./pages/AssessmentEditor.jsx";
import AssessmentPage from "./pages/AssessmentPage.jsx";
import AssessmentResults from "./pages/AssessmentResults.jsx";
import Assessments from "./pages/Assessments.jsx";
import { BatchDetail, BatchList } from "./pages/Batches.jsx";
import Colleges from "./pages/Colleges.jsx";
import CourseEditor from "./pages/CourseEditor.jsx";
import CoursePage from "./pages/CoursePage.jsx";
import Courses from "./pages/Courses.jsx";
import Home from "./pages/Home.jsx";
import LessonEditor from "./pages/LessonEditor.jsx";
import LessonPage from "./pages/LessonPage.jsx";
import Login from "./pages/Login.jsx";
import People from "./pages/People.jsx";
import ProblemEditor from "./pages/ProblemEditor.jsx";
import ProblemPage from "./pages/ProblemPage.jsx";
import Problems from "./pages/Problems.jsx";

const STAFF = ["super_admin", "admin", "teacher"];

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Home />} />
        <Route path="account" element={<Account />} />
        <Route path="assessments" element={<ProtectedRoute roles={["student", "teacher", "admin"]}><Assessments /></ProtectedRoute>} />
        <Route path="assessments/new" element={<ProtectedRoute roles={["teacher", "admin"]}><AssessmentEditor /></ProtectedRoute>} />
        <Route path="assessments/:id" element={<ProtectedRoute roles={["student", "teacher", "admin"]}><AssessmentPage /></ProtectedRoute>} />
        <Route path="assessments/:id/edit" element={<ProtectedRoute roles={["teacher", "admin"]}><AssessmentEditor /></ProtectedRoute>} />
        <Route path="assessments/:id/results" element={<ProtectedRoute roles={["teacher", "admin"]}><AssessmentResults /></ProtectedRoute>} />
        <Route path="assessments/:aid/problems/:id" element={<ProtectedRoute roles={["student", "teacher", "admin"]}><ProblemPage /></ProtectedRoute>} />
        <Route path="courses" element={<Courses />} />
        <Route path="courses/new" element={<ProtectedRoute roles={STAFF}><CourseEditor /></ProtectedRoute>} />
        <Route path="courses/:id" element={<CoursePage />} />
        <Route path="courses/:id/edit" element={<ProtectedRoute roles={STAFF}><CourseEditor /></ProtectedRoute>} />
        <Route path="lessons/:id" element={<LessonPage />} />
        <Route path="lessons/:id/edit" element={<ProtectedRoute roles={STAFF}><LessonEditor /></ProtectedRoute>} />
        <Route path="problems" element={<Problems />} />
        <Route path="problems/new" element={<ProtectedRoute roles={STAFF}><ProblemEditor /></ProtectedRoute>} />
        <Route path="problems/:id" element={<ProblemPage />} />
        <Route path="problems/:id/edit" element={<ProtectedRoute roles={STAFF}><ProblemEditor /></ProtectedRoute>} />
        <Route path="colleges" element={<ProtectedRoute roles={["super_admin"]}><Colleges /></ProtectedRoute>} />
        <Route path="people" element={<ProtectedRoute roles={STAFF}><People /></ProtectedRoute>} />
        <Route path="batches" element={<ProtectedRoute roles={["student", "teacher", "admin"]}><BatchList /></ProtectedRoute>} />
        <Route path="batches/:id" element={<ProtectedRoute roles={["teacher", "admin"]}><BatchDetail /></ProtectedRoute>} />
        <Route path="*" element={<ProtectedRoute><Home /></ProtectedRoute>} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
