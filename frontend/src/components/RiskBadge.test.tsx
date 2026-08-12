import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { RiskBadge } from "./RiskBadge";

// Accessibility rule: the risk band must never be conveyed by colour alone —
// each badge carries a text label AND a distinct glyph.
describe("RiskBadge", () => {
  it("shows a text label for each band", () => {
    const { rerender } = render(<RiskBadge band="low" />);
    expect(screen.getByText(/low risk/i)).toBeInTheDocument();
    rerender(<RiskBadge band="moderate" />);
    expect(screen.getByText(/moderate risk/i)).toBeInTheDocument();
    rerender(<RiskBadge band="high" />);
    expect(screen.getByText(/high risk/i)).toBeInTheDocument();
  });

  it("pairs the label with a non-colour glyph", () => {
    const { container } = render(<RiskBadge band="high" />);
    // The glyph (▲ / ◆ / ●) is present in addition to the label text.
    expect(container.textContent).toMatch(/[▲◆●]/);
  });
});
