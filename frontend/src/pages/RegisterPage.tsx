import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Loader2, UserPlus } from "lucide-react";
import { apiError, authApi } from "@/lib/api";
import { checkPassword } from "@/lib/passwordCheck";
import { useAuthStore } from "@/store/auth";
import { ErrorNote } from "@/components/ui";
import { AuthShell } from "./auth/AuthShell";
import { MatchHint, PasswordField, StrengthMeter } from "./auth/fields";

export function RegisterPage() {
  const navigate = useNavigate();
  const { setToken, setUser } = useAuthStore();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Password strength is evaluated CLIENT-SIDE (mirrors the server policy), so
  // the meter and the submit button work regardless of network/backend state.
  // The server re-validates on registration, so this can never weaken security.
  const strength = useMemo(() => checkPassword(password, email || undefined), [password, email]);

  const passwordsMatch = password.length > 0 && password === confirm;
  const canSubmit = fullName && email && strength.ok && passwordsMatch && !busy;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setError(null);
    setBusy(true);
    try {
      await authApi.register({ email, password, full_name: fullName, role: "health_worker" });
      const token = await authApi.login({ email, password });
      setToken(token.access_token);
      setUser(await authApi.me());
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(apiError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell>
      <h1 className="font-display text-2xl font-bold text-text-primary">Create your account</h1>
      <p className="mt-1 text-sm text-text-secondary">
        Health-worker access — your workspace comes pre-loaded with sample patients.
      </p>

      <form onSubmit={submit} className="mt-7 space-y-4">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-text-primary" htmlFor="name">
            Full name
          </label>
          <input
            id="name"
            required
            className="w-full rounded-xl border border-border bg-surface px-3.5 py-2.5 text-sm transition-colors focus:border-primary hover:border-primary/40"
            placeholder="Dr. Asha Devi"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
          />
        </div>

        <div>
          <label className="mb-1.5 block text-sm font-medium text-text-primary" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            required
            className="w-full rounded-xl border border-border bg-surface px-3.5 py-2.5 text-sm transition-colors focus:border-primary hover:border-primary/40"
            placeholder="you@clinic.org"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>

        <div>
          <PasswordField
            id="password"
            label="Password"
            value={password}
            onChange={setPassword}
            autoComplete="new-password"
            placeholder="Create a strong password"
          />
          <StrengthMeter score={strength.score} errors={strength.errors} show={!!password} />
        </div>

        <div>
          <PasswordField
            id="confirm"
            label="Confirm password"
            value={confirm}
            onChange={setConfirm}
            autoComplete="new-password"
            placeholder="Re-enter your password"
          />
          <MatchHint match={passwordsMatch} show={confirm.length > 0} />
        </div>

        {error && <ErrorNote message={error} />}

        <button
          type="submit"
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-primary-hover active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed"
          disabled={!canSubmit}
        >
          {busy ? <Loader2 size={17} className="animate-spin" /> : <UserPlus size={17} />}
          {busy ? "Creating account…" : "Create account"}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-text-secondary">
        Already registered?{" "}
        <Link to="/login" className="font-semibold text-primary hover:underline">
          Sign in
        </Link>
      </p>
    </AuthShell>
  );
}
