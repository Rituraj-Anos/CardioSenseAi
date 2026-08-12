import clsx from "clsx";
import type { RiskBand } from "@/lib/types";

// Accessibility rule (Blueprint Section 12): never rely on colour alone for the
// risk band. Each badge pairs its reserved colour with a text label AND a
// distinct glyph, so it is legible to colour-blind users and in greyscale print.
const CONFIG: Record<
  RiskBand,
  { label: string; glyph: string; bg: string; fg: string; ring: string }
> = {
  low: {
    label: "Low risk",
    glyph: "●",
    bg: "bg-risk-low/10",
    fg: "text-risk-low",
    ring: "ring-risk-low/30",
  },
  moderate: {
    label: "Moderate risk",
    glyph: "◆",
    bg: "bg-risk-moderate/10",
    fg: "text-risk-moderate",
    ring: "ring-risk-moderate/30",
  },
  high: {
    label: "High risk",
    glyph: "▲",
    bg: "bg-risk-high/10",
    fg: "text-risk-high",
    ring: "ring-risk-high/40",
  },
};

export function RiskBadge({ band, size = "md" }: { band: RiskBand; size?: "sm" | "md" | "lg" }) {
  const c = CONFIG[band];
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full font-semibold ring-1",
        c.bg,
        c.fg,
        c.ring,
        size === "sm" && "px-2.5 py-0.5 text-xs",
        size === "md" && "px-3 py-1 text-sm",
        size === "lg" && "px-4 py-1.5 text-base"
      )}
    >
      <span aria-hidden>{c.glyph}</span>
      {c.label}
    </span>
  );
}
