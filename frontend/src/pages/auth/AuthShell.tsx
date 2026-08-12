import { Link } from "react-router-dom";
import { motion } from "motion/react";
import { HeartPulse, ScanLine, ShieldCheck, Activity, Check } from "lucide-react";
import type { ReactNode } from "react";

// Split-screen auth layout: a branded panel (trust + value) beside the form.
export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-background font-body lg:grid lg:grid-cols-2">
      {/* Brand panel */}
      <div className="relative hidden overflow-hidden bg-primary-gradient p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="pointer-events-none absolute -right-20 -top-20 h-80 w-80 rounded-full bg-white/10 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-24 -left-10 h-80 w-80 rounded-full bg-white/5 blur-3xl" />

        <Link to="/" className="relative flex items-center gap-2.5">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-white/15 backdrop-blur">
            <HeartPulse size={20} />
          </span>
          <span className="font-display text-xl font-bold">
            CardioSense <span className="text-white/80">AI</span>
          </span>
        </Link>

        <div className="relative">
          <motion.h2
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
            className="font-display text-3xl font-bold leading-tight"
          >
            Cardiovascular screening,
            <br /> made accessible.
          </motion.h2>
          <div className="mt-8 space-y-4">
            {[
              { icon: <ScanLine size={18} />, t: "Scan a report, get a risk read in seconds" },
              { icon: <Activity size={18} />, t: "Explainable results — never a black box" },
              { icon: <ShieldCheck size={18} />, t: "A screening aid, honest about uncertainty" },
            ].map((f, i) => (
              <motion.div
                key={f.t}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.2 + i * 0.1, duration: 0.5 }}
                className="flex items-center gap-3 text-white/90"
              >
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-white/15">
                  {f.icon}
                </span>
                <span className="text-sm">{f.t}</span>
              </motion.div>
            ))}
          </div>
        </div>

        <p className="relative text-xs text-white/50">
          Protected access · encrypted credentials · audit-logged activity
        </p>
      </div>

      {/* Form side */}
      <div className="flex min-h-screen items-center justify-center px-6 py-12">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          className="w-full max-w-md"
        >
          {/* Mobile brand */}
          <Link to="/" className="mb-8 flex items-center justify-center gap-2 lg:hidden">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-primary-gradient text-white">
              <HeartPulse size={18} />
            </span>
            <span className="font-display text-lg font-bold">
              CardioSense <span className="text-primary">AI</span>
            </span>
          </Link>
          {children}
        </motion.div>
      </div>
    </div>
  );
}

export { Check };
