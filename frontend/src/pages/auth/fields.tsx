import { useState } from "react";
import { Eye, EyeOff, Check, X } from "lucide-react";

/** Password input with a show/hide toggle. */
export function PasswordField({
  id,
  label,
  value,
  onChange,
  autoComplete = "current-password",
  placeholder,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  autoComplete?: string;
  placeholder?: string;
}) {
  const [show, setShow] = useState(false);
  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-text-primary" htmlFor={id}>
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          type={show ? "text" : "password"}
          autoComplete={autoComplete}
          placeholder={placeholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full rounded-xl border border-border bg-surface px-3.5 py-2.5 pr-11 text-sm text-text-primary transition-colors placeholder:text-text-tertiary focus:border-primary hover:border-primary/40"
        />
        <button
          type="button"
          onClick={() => setShow((s) => !s)}
          aria-label={show ? "Hide password" : "Show password"}
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg p-1.5 text-text-tertiary transition-colors hover:bg-primary-soft hover:text-primary"
          tabIndex={-1}
        >
          {show ? <EyeOff size={17} /> : <Eye size={17} />}
        </button>
      </div>
    </div>
  );
}

const STRENGTH = [
  { label: "Very weak", color: "#B42318", w: "20%" },
  { label: "Weak", color: "#B54708", w: "40%" },
  { label: "Fair", color: "#B54708", w: "60%" },
  { label: "Good", color: "#12866F", w: "80%" },
  { label: "Strong", color: "#12866F", w: "100%" },
];

/** Strength meter + live requirement checklist. */
export function StrengthMeter({
  score,
  errors,
  show,
}: {
  score: number;
  errors: string[];
  show: boolean;
}) {
  if (!show) return null;
  const s = STRENGTH[Math.min(4, Math.max(0, score))];
  return (
    <div className="mt-2">
      <div className="flex items-center gap-2">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-border">
          <div
            className="h-full rounded-full transition-all duration-300"
            style={{ width: s.w, background: s.color }}
          />
        </div>
        <span className="text-xs font-medium" style={{ color: s.color }}>
          {s.label}
        </span>
      </div>
      {errors.length > 0 && (
        <ul className="mt-2 space-y-1">
          {errors.slice(0, 4).map((e) => (
            <li key={e} className="flex items-center gap-1.5 text-xs text-text-secondary">
              <X size={13} className="text-risk-high" /> {e}
            </li>
          ))}
        </ul>
      )}
      {errors.length === 0 && (
        <p className="mt-2 flex items-center gap-1.5 text-xs text-risk-low">
          <Check size={13} /> Meets all requirements
        </p>
      )}
    </div>
  );
}

export function MatchHint({ match, show }: { match: boolean; show: boolean }) {
  if (!show) return null;
  return match ? (
    <p className="mt-1.5 flex items-center gap-1.5 text-xs text-risk-low">
      <Check size={13} /> Passwords match
    </p>
  ) : (
    <p className="mt-1.5 flex items-center gap-1.5 text-xs text-risk-high">
      <X size={13} /> Passwords don't match
    </p>
  );
}
