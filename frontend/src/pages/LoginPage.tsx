import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Loader2, LogIn } from "lucide-react";
import { apiError, authApi } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { ErrorNote } from "@/components/ui";
import { AuthShell } from "./auth/AuthShell";
import { PasswordField } from "./auth/fields";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation() as { state?: { from?: { pathname: string } } };
  const { setToken, setUser } = useAuthStore();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const token = await authApi.login({ email, password });
      setToken(token.access_token);
      setUser(await authApi.me());
      navigate(location.state?.from?.pathname ?? "/dashboard", { replace: true });
    } catch (err) {
      setError(apiError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell>
      <h1 className="font-display text-2xl font-bold text-text-primary">Welcome back</h1>
      <p className="mt-1 text-sm text-text-secondary">Sign in to your screening workspace.</p>

      <form onSubmit={submit} className="mt-7 space-y-4">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-text-primary" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            required
            className="w-full rounded-xl border border-border bg-surface px-3.5 py-2.5 text-sm transition-colors placeholder:text-text-tertiary focus:border-primary hover:border-primary/40"
            placeholder="you@clinic.org"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>

        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <span className="text-sm font-medium text-text-primary">Password</span>
            <button
              type="button"
              className="text-xs font-medium text-primary hover:underline"
              onClick={() => setError("Password reset isn't wired in this build — use the demo account or register a new one.")}
            >
              Forgot password?
            </button>
          </div>
          <PasswordField
            id="password"
            label=""
            value={password}
            onChange={setPassword}
            autoComplete="current-password"
            placeholder="••••••••••"
          />
        </div>

        {error && <ErrorNote message={error} />}

        <button
          type="submit"
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-primary-hover active:scale-[0.99] disabled:opacity-60"
          disabled={busy || !email || !password}
        >
          {busy ? <Loader2 size={17} className="animate-spin" /> : <LogIn size={17} />}
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>

      <div className="mt-6 rounded-xl border border-border bg-surface px-4 py-3 text-xs text-text-secondary">
        <span className="font-semibold text-text-primary">Demo account</span> ·
        asha@cardiosense.demo / demo-pass-2026
      </div>

      <p className="mt-6 text-center text-sm text-text-secondary">
        No account?{" "}
        <Link to="/register" className="font-semibold text-primary hover:underline">
          Create one
        </Link>
      </p>
    </AuthShell>
  );
}
