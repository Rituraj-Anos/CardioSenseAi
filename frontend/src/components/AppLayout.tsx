import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import {
  LayoutDashboard,
  HeartPulse,
  LogOut,
  FileHeart,
  Activity,
  TrendingUp,
  Send,
  FlaskConical,
  BookOpen,
} from "lucide-react";
import { authApi } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

export function AppLayout() {
  const { user, clear } = useAuthStore();
  const navigate = useNavigate();

  const logout = async () => {
    try {
      await authApi.logout();
    } finally {
      clear();
      navigate("/login");
    }
  };

  const initials = (user?.full_name ?? user?.email ?? "?")
    .split(" ")
    .map((s) => s[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <div className="min-h-screen bg-background lg:grid lg:grid-cols-[248px_1fr]">
      {/* Sidebar */}
      <aside className="sticky top-0 hidden h-screen flex-col border-r border-border bg-surface lg:flex">
        <Link to="/dashboard" className="flex items-center gap-2.5 px-6 py-5">
          <span className="grid h-9 w-9 place-items-center rounded-control bg-primary-gradient text-white shadow-sm">
            <HeartPulse size={19} />
          </span>
          <span className="text-lg font-bold text-text-primary">
            CardioSense <span className="text-primary">AI</span>
          </span>
        </Link>

        <nav className="mt-2 flex flex-1 flex-col gap-1 px-3">
          <div className="px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-text-tertiary">
            Clinical
          </div>
          <SideLink to="/dashboard" icon={<LayoutDashboard size={18} />} label="Dashboard" />
          <SideLink to="/insights" icon={<TrendingUp size={18} />} label="Insights" />
          <SideLink to="/referrals" icon={<Send size={18} />} label="Referrals" />

          <div className="mt-5 px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-text-tertiary">
            Knowledge
          </div>
          <SideLink to="/methodology" icon={<FlaskConical size={18} />} label="Model & methodology" />
          <SideLink to="/reference" icon={<BookOpen size={18} />} label="Clinical reference" />
        </nav>

        <div className="border-t border-border p-3">
          <div className="flex items-center gap-3 rounded-control px-3 py-2">
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-primary-soft text-sm font-semibold text-primary">
              {initials}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-text-primary">
                {user?.full_name ?? user?.email}
              </p>
              <p className="truncate text-xs text-text-tertiary capitalize">
                {user?.role?.replace("_", " ")}
              </p>
            </div>
          </div>
          <button onClick={logout} className="btn-ghost mt-1 w-full justify-start text-sm">
            <LogOut size={16} /> Sign out
          </button>
        </div>
      </aside>

      {/* Mobile top bar */}
      <div className="flex flex-col">
        <header className="flex items-center justify-between border-b border-border bg-surface px-5 py-3 lg:hidden">
          <Link to="/dashboard" className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-control bg-primary-gradient text-white">
              <HeartPulse size={16} />
            </span>
            <span className="font-bold text-text-primary">
              CardioSense <span className="text-primary">AI</span>
            </span>
          </Link>
          <button onClick={logout} className="btn-ghost py-1.5 text-xs">
            <LogOut size={14} /> Sign out
          </button>
        </header>

        <main className="mx-auto w-full max-w-6xl px-5 py-8 sm:px-8">
          <PageTransition />
        </main>

        <footer className="mx-auto w-full max-w-6xl px-5 pb-8 sm:px-8">
          <div className="flex items-center gap-2 text-xs text-text-tertiary">
            <Activity size={13} />
            CardioSense AI · screening aid, not a diagnosis · results include uncertainty
          </div>
        </footer>
      </div>
    </div>
  );
}

function PageTransition() {
  const location = useLocation();
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -6 }}
        transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
      >
        <Outlet />
      </motion.div>
    </AnimatePresence>
  );
}

function SideLink({ to, icon, label }: { to: string; icon: React.ReactNode; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex items-center gap-3 rounded-control px-3 py-2.5 text-sm font-medium transition-colors ${
          isActive
            ? "bg-primary-soft text-primary"
            : "text-text-secondary hover:bg-primary-soft/50 hover:text-text-primary"
        }`
      }
    >
      {icon}
      {label}
    </NavLink>
  );
}

// Re-export for use elsewhere without extra imports.
export { FileHeart };
