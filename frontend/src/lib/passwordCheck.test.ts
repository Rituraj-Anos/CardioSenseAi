import { describe, expect, it } from "vitest";
import { checkPassword } from "./passwordCheck";

describe("checkPassword (client policy mirrors server)", () => {
  it("rejects short passwords", () => {
    const r = checkPassword("Ab1!");
    expect(r.ok).toBe(false);
    expect(r.errors.join(" ")).toMatch(/at least 10/i);
  });

  it("requires upper, lower, digit and symbol", () => {
    expect(checkPassword("alllowercase1!").errors).toContain("Add an uppercase letter.");
    expect(checkPassword("ALLUPPER123!").errors).toContain("Add a lowercase letter.");
    expect(checkPassword("NoDigitsHere!!").errors).toContain("Add a number.");
    expect(checkPassword("NoSymbol12345").errors).toContain("Add a symbol (e.g. ! ? @ #).");
  });

  it("accepts a strong password with a top score", () => {
    const r = checkPassword("Str0ng-Pass!word");
    expect(r.ok).toBe(true);
    expect(r.errors).toHaveLength(0);
    expect(r.score).toBe(4);
  });

  it("rejects common passwords", () => {
    expect(checkPassword("password123").ok).toBe(false);
  });

  it("rejects passwords containing the email name", () => {
    const r = checkPassword("Rituraj-9xY!", "rituraj@example.org");
    expect(r.errors.join(" ")).toMatch(/email name/i);
  });
});
