// Client-side password policy — mirrors the backend (app/core/passwords.py).
// The register form uses THIS as the source of truth for the strength meter and
// the submit button, so it works even if the live server check is unreachable.
// The server still enforces the same rules on registration.

export interface PasswordResult {
  ok: boolean;
  score: number; // 0-4
  errors: string[];
}

const MIN_LENGTH = 10;
const MAX_LENGTH = 128;

const COMMON = new Set([
  "password", "password1", "password12", "password123", "passw0rd",
  "12345678", "123456789", "1234567890", "qwerty123", "letmein123",
  "welcome123", "admin123", "cardiosense", "changeme123", "iloveyou1",
]);

export function checkPassword(password: string, email?: string): PasswordResult {
  const p = password || "";
  const errors: string[] = [];

  if (p.length < MIN_LENGTH) errors.push(`Use at least ${MIN_LENGTH} characters.`);
  if (p.length > MAX_LENGTH) errors.push(`Keep it under ${MAX_LENGTH} characters.`);
  if (!/[a-z]/.test(p)) errors.push("Add a lowercase letter.");
  if (!/[A-Z]/.test(p)) errors.push("Add an uppercase letter.");
  if (!/\d/.test(p)) errors.push("Add a number.");
  if (!/[^A-Za-z0-9]/.test(p)) errors.push("Add a symbol (e.g. ! ? @ #).");
  if (COMMON.has(p.toLowerCase())) errors.push("That password is too common.");

  const localPart = email?.split("@")[0]?.toLowerCase();
  if (localPart && localPart.length >= 3 && p.toLowerCase().includes(localPart)) {
    errors.push("Don't include your email name in the password.");
  }

  return { ok: errors.length === 0, score: score(p), errors };
}

function score(p: string): number {
  if (!p) return 0;
  let s = 0;
  if (p.length >= MIN_LENGTH) s += 1;
  if (p.length >= 14) s += 1;
  const classes =
    (/[a-z]/.test(p) ? 1 : 0) +
    (/[A-Z]/.test(p) ? 1 : 0) +
    (/\d/.test(p) ? 1 : 0) +
    (/[^A-Za-z0-9]/.test(p) ? 1 : 0);
  s += Math.max(0, classes - 1);
  return Math.min(4, s);
}
