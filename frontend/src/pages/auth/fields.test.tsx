import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MatchHint, StrengthMeter } from "./fields";

describe("StrengthMeter", () => {
  it("is hidden until there is a password", () => {
    const { container } = render(<StrengthMeter score={0} errors={[]} show={false} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("lists outstanding requirements when weak", () => {
    render(<StrengthMeter score={1} errors={["Add a symbol (e.g. ! ? @ #)."]} show />);
    expect(screen.getByText(/add a symbol/i)).toBeInTheDocument();
  });

  it("confirms when all requirements are met", () => {
    render(<StrengthMeter score={4} errors={[]} show />);
    expect(screen.getByText(/meets all requirements/i)).toBeInTheDocument();
  });
});

describe("MatchHint", () => {
  it("shows a match confirmation", () => {
    render(<MatchHint match show />);
    expect(screen.getByText(/passwords match/i)).toBeInTheDocument();
  });

  it("warns on mismatch", () => {
    render(<MatchHint match={false} show />);
    expect(screen.getByText(/don't match/i)).toBeInTheDocument();
  });
});
