import clsx from "clsx";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { motion, useInView } from "motion/react";

/** One-time entrance. No looping/ambient motion on clinical data (Blueprint §10). */
export function FadeIn({
  children,
  delay = 0,
  className,
  y = 10,
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
  y?: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay, ease: [0.16, 1, 0.3, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/** Staggered container: children animate in sequence on scroll into view. */
export function Stagger({ children, className }: { children: ReactNode; className?: string }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  return (
    <motion.div
      ref={ref}
      initial="hidden"
      animate={inView ? "show" : "hidden"}
      variants={{ show: { transition: { staggerChildren: 0.06 } } }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div
      variants={{
        hidden: { opacity: 0, y: 12 },
        show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.16, 1, 0.3, 1] } },
      }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={clsx("card", className)}>{children}</div>;
}

/** Counts up to the target once, on mount. Used for headline stats only. */
export function AnimatedNumber({
  value,
  duration = 900,
  suffix = "",
  decimals = 0,
}: {
  value: number;
  duration?: number;
  suffix?: string;
  decimals?: number;
}) {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay(value * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration]);
  return (
    <span className="mono tabular-nums">
      {display.toFixed(decimals)}
      {suffix}
    </span>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 text-text-secondary" role="status">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      {label && <span className="text-sm">{label}</span>}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("skeleton", className)} />;
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="rounded-control border border-risk-high/30 bg-risk-high/5 px-3 py-2 text-sm text-risk-high"
    >
      {message}
    </div>
  );
}

export function EmptyState({
  title,
  hint,
  icon,
  action,
}: {
  title: string;
  hint?: string;
  icon?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center rounded-card border border-dashed border-border bg-surface/60 px-6 py-14 text-center">
      {icon && <div className="mb-3 text-text-tertiary">{icon}</div>}
      <p className="font-medium text-text-primary">{title}</p>
      {hint && <p className="mt-1 max-w-sm text-sm text-text-secondary">{hint}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/** The "screening, not a diagnosis" line — reused everywhere a result shows. */
export function Disclaimer({ text }: { text: string }) {
  return (
    <p className="rounded-control border border-primary/15 bg-primary-soft/70 px-3 py-2 text-xs leading-relaxed text-text-secondary">
      <span className="font-semibold text-primary">Important: </span>
      {text}
    </p>
  );
}

export function ConfidenceMeter({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const descriptor = pct >= 70 ? "high" : pct >= 40 ? "moderate" : "low";
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="text-sm text-text-secondary">Model confidence</span>
        <span className="mono text-sm font-semibold text-text-primary">
          {pct}% ({descriptor})
        </span>
      </div>
      <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-border">
        <motion.div
          className="h-full rounded-full bg-primary-gradient"
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        />
      </div>
    </div>
  );
}
