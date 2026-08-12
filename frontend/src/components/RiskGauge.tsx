import { motion } from "motion/react";
import type { RiskBand } from "@/lib/types";

const COLORS: Record<RiskBand, string> = {
  low: "#12866F",
  moderate: "#B54708",
  high: "#B42318",
};

const LABELS: Record<RiskBand, string> = {
  low: "Low risk",
  moderate: "Moderate risk",
  high: "High risk",
};

/** Radial risk gauge. The arc + the numeric readout + the text label all encode
 *  the result, so it never depends on colour alone (Blueprint §12 a11y rule). */
export function RiskGauge({ score, band }: { score: number; band: RiskBand }) {
  const pct = Math.round(score * 100);
  const radius = 80;
  const stroke = 14;
  const circumference = Math.PI * radius; // half circle
  const color = COLORS[band];

  return (
    <div className="flex flex-col items-center">
      <svg width="200" height="118" viewBox="0 0 200 118" className="overflow-visible">
        {/* track */}
        <path
          d="M 20 108 A 80 80 0 0 1 180 108"
          fill="none"
          stroke="#E4E7EC"
          strokeWidth={stroke}
          strokeLinecap="round"
        />
        {/* value arc */}
        <motion.path
          d="M 20 108 A 80 80 0 0 1 180 108"
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: circumference * (1 - score) }}
          transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
        />
      </svg>
      <div className="-mt-14 flex flex-col items-center">
        <motion.span
          className="mono text-4xl font-bold"
          style={{ color }}
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.4 }}
        >
          {pct}%
        </motion.span>
        <span className="text-xs font-semibold uppercase tracking-wide" style={{ color }}>
          {LABELS[band]}
        </span>
      </div>
    </div>
  );
}
