import { Link } from "react-router-dom";
import { useAuth } from "../auth.jsx";
import { Card, roleLabel } from "../ui.jsx";

const TIPS = {
  super_admin: [
    ["/courses", "Manage the shared courses"],
    ["/colleges", "Add a college"],
    ["/people", "Create a college admin"],
    ["/problems", "Add problems to the shared bank"],
  ],
  admin: [
    ["/assessments", "See assignments and exams"],
    ["/courses", "See and publish courses"],
    ["/people", "Add teachers and students"],
    ["/batches", "See all batches"],
    ["/problems", "Create coding problems"],
  ],
  teacher: [
    ["/assessments", "Create an assignment or exam"],
    ["/courses", "Make a course from the starter course"],
    ["/batches", "Create a batch"],
    ["/people", "Add students"],
    ["/problems", "Create coding problems"],
  ],
  student: [
    ["/assessments", "See your assignments and exams"],
    ["/courses", "Start learning: C Programming Basics"],
    ["/problems", "Solve a coding problem"],
    ["/batches", "See my batches"],
  ],
};

export default function Home() {
  const { user } = useAuth();
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-slate-900">Welcome, {user.name}</h1>
      <p className="text-slate-600">
        {roleLabel[user.role]}
        {user.college_name ? ` at ${user.college_name}` : ""}
      </p>
      <Card title="Get started">
        <ul className="list-inside list-disc space-y-1 text-indigo-700">
          {TIPS[user.role].map(([to, label]) => (
            <li key={to + label}>
              <Link className="underline" to={to}>
                {label}
              </Link>
            </li>
          ))}
        </ul>
      </Card>
      <p className="text-sm text-slate-500">The AI helper is coming in a later phase.</p>
    </div>
  );
}
