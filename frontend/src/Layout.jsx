import { Link, NavLink, Outlet, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "./auth.jsx";
import { Button, roleLabel } from "./ui.jsx";

const NAV = [
  { to: "/", label: "Home", roles: ["student", "teacher", "admin", "super_admin"], end: true },
  { to: "/courses", label: "Courses", roles: ["student", "teacher", "admin", "super_admin"] },
  { to: "/problems", label: "Problems", roles: ["student", "teacher", "admin", "super_admin"] },
  { to: "/colleges", label: "Colleges", roles: ["super_admin"] },
  { to: "/people", label: "People", roles: ["super_admin", "admin", "teacher"] },
  { to: "/batches", label: "Batches", roles: ["student", "teacher", "admin"] },
  { to: "/account", label: "Account", roles: ["student", "teacher", "admin", "super_admin"] },
];

export function ProtectedRoute({ roles, children }) {
  const { user, loading } = useAuth();
  if (loading) return <p className="p-6 text-slate-500">Loading…</p>;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) {
    return (
      <div className="mx-auto max-w-xl p-6">
        <p role="alert" className="rounded border border-red-200 bg-red-50 p-3 text-red-800">
          You are not allowed to open this page.
        </p>
        <Link to="/" className="mt-3 inline-block text-indigo-700 underline">
          Back to home
        </Link>
      </div>
    );
  }
  return children;
}

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const links = NAV.filter((n) => n.roles.includes(user.role));

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <span className="text-lg font-bold text-indigo-700">Sankalp AI</span>
          <nav className="flex flex-wrap gap-4 text-sm">
            {links.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.end}
                className={({ isActive }) =>
                  isActive ? "font-semibold text-indigo-700" : "text-slate-600 hover:text-slate-900"
                }
              >
                {l.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm">
            <span className="text-slate-600">
              {user.name} <span className="text-slate-400">({roleLabel[user.role]})</span>
            </span>
            <Button
              variant="secondary"
              onClick={() => {
                logout();
                navigate("/login");
              }}
            >
              Log out
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
