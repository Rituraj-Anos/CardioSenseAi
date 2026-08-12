import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { FileText, ScanLine, HeartPulse, CheckCircle2 } from "lucide-react";

// The hero's living product demo: a lab report is scanned, values populate, and
// a calibrated risk read appears. It communicates the whole product in one
// glance — scan → predict → explain — and loops gently.

const FIELDS = [
  { label: "Resting BP", value: "158 mm Hg" },
  { label: "Cholesterol", value: "284 mg/dL" },
  { label: "Fasting sugar", value: "138 mg/dL" },
  { label: "Peak heart rate", value: "118 bpm" },
  { label: "ST depression", value: "2.8 mm" },
];

type Phase = "scanning" | "extracting" | "result";

export function ScanDemo() {
  const reduce = useReducedMotion();
  const [phase, setPhase] = useState<Phase>(reduce ? "result" : "scanning");

  useEffect(() => {
    if (reduce) return;
    let t1: number, t2: number, t3: number;
    const run = () => {
      setPhase("scanning");
      t1 = window.setTimeout(() => setPhase("extracting"), 1800);
      t2 = window.setTimeout(() => setPhase("result"), 4200);
      t3 = window.setTimeout(run, 8000);
    };
    run();
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    };
  }, [reduce]);

  return (
    <div className="relative mx-auto w-full max-w-md">
      {/* ambient glow */}
      <div className="pointer-events-none absolute -inset-6 -z-10 rounded-[36px] bg-primary/10 blur-3xl" />

      <div className="grid gap-4 sm:grid-cols-[1.1fr_1fr]">
        {/* Report being scanned */}
        <div className="relative overflow-hidden rounded-2xl border border-border bg-surface p-4 shadow-card">
          <div className="flex items-center gap-2 text-xs font-medium text-text-secondary">
            <FileText size={14} className="text-primary" /> Lab report
          </div>
          <div className="mt-3 space-y-2">
            {[90, 70, 82, 60, 75, 88, 66].map((w, i) => (
              <div key={i} className="flex items-center gap-2">
                <div className="h-2 rounded-full bg-text-primary/10" style={{ width: `${w}%` }} />
              </div>
            ))}
          </div>

          {/* scanning sweep */}
          {phase === "scanning" && !reduce && (
            <motion.div
              className="absolute inset-x-0 h-16 bg-gradient-to-b from-primary/0 via-primary/25 to-primary/0"
              initial={{ top: "-20%" }}
              animate={{ top: "100%" }}
              transition={{ duration: 1.6, ease: "easeInOut", repeat: Infinity }}
            >
              <div className="absolute bottom-0 h-0.5 w-full bg-primary shadow-[0_0_12px_2px_rgba(14,110,100,0.6)]" />
            </motion.div>
          )}
          <div className="mt-3 flex items-center gap-1.5 text-[11px] font-medium text-primary">
            <ScanLine size={13} />
            {phase === "scanning" ? "Scanning…" : "Read"}
          </div>
        </div>

        {/* Right: extracted fields → risk result */}
        <div className="rounded-2xl border border-border bg-surface p-4 shadow-card">
          <AnimatePresence mode="wait">
            {phase !== "result" ? (
              <motion.div
                key="fields"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="space-y-2"
              >
                <p className="text-xs font-medium text-text-secondary">Auto-filled</p>
                {FIELDS.map((f, i) => (
                  <motion.div
                    key={f.label}
                    initial={reduce ? false : { opacity: 0, x: 8 }}
                    animate={
                      phase === "extracting" || reduce
                        ? { opacity: 1, x: 0 }
                        : { opacity: 0.35, x: 0 }
                    }
                    transition={{ delay: reduce ? 0 : i * 0.18, duration: 0.3 }}
                    className="flex items-center justify-between rounded-lg bg-background px-2.5 py-1.5"
                  >
                    <span className="text-[11px] text-text-secondary">{f.label}</span>
                    <span className="font-mono text-[11px] font-semibold text-text-primary">
                      {f.value}
                    </span>
                  </motion.div>
                ))}
              </motion.div>
            ) : (
              <motion.div
                key="result"
                initial={reduce ? false : { opacity: 0, scale: 0.96 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
                className="flex h-full flex-col items-center justify-center text-center"
              >
                <div className="relative">
                  <svg width="120" height="72" viewBox="0 0 120 72">
                    <path
                      d="M 12 64 A 48 48 0 0 1 108 64"
                      fill="none"
                      stroke="#E4E7EC"
                      strokeWidth="10"
                      strokeLinecap="round"
                    />
                    <motion.path
                      d="M 12 64 A 48 48 0 0 1 108 64"
                      fill="none"
                      stroke="#B42318"
                      strokeWidth="10"
                      strokeLinecap="round"
                      strokeDasharray={151}
                      initial={reduce ? false : { strokeDashoffset: 151 }}
                      animate={{ strokeDashoffset: 151 * (1 - 0.76) }}
                      transition={{ duration: 0.9, ease: "easeOut" }}
                    />
                  </svg>
                  <div className="absolute inset-x-0 bottom-0 text-center">
                    <span className="font-mono text-2xl font-bold text-risk-high">76%</span>
                  </div>
                </div>
                <span className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-risk-high/10 px-3 py-1 text-xs font-semibold text-risk-high">
                  <HeartPulse size={13} /> High risk
                </span>
                <p className="mt-3 flex items-center gap-1.5 text-[11px] text-text-secondary">
                  <CheckCircle2 size={12} className="text-primary" /> Explained &amp; ready for review
                </p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* phase pips */}
      {!reduce && (
        <div className="mt-4 flex items-center justify-center gap-2">
          {(["scanning", "extracting", "result"] as Phase[]).map((p) => (
            <span
              key={p}
              className={`h-1.5 rounded-full transition-all duration-300 ${
                phase === p ? "w-6 bg-primary" : "w-1.5 bg-border"
              }`}
            />
          ))}
        </div>
      )}
    </div>
  );
}
