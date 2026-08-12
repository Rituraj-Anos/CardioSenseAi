import { Link } from "react-router-dom";
import { motion } from "motion/react";
import {
  HeartPulse,
  ScanText,
  ShieldCheck,
  Activity,
  ArrowRight,
  Layers,
} from "lucide-react";
import { FadeIn } from "@/components/ui";
import { useAuthStore } from "@/store/auth";

export function LandingPage() {
  const token = useAuthStore((s) => s.accessToken);

  return (
    <div className="min-h-screen bg-background">
      {/* Top bar */}
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <div className="flex items-center gap-2.5">
          <span className="grid h-9 w-9 place-items-center rounded-control bg-primary-gradient text-white shadow-sm">
            <HeartPulse size={19} />
          </span>
          <span className="text-lg font-bold text-text-primary">
            CardioSense <span className="text-primary">AI</span>
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/login" className="btn-ghost">
            Sign in
          </Link>
          <Link to="/register" className="btn-primary">
            Get started
          </Link>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="mx-auto grid max-w-6xl items-center gap-10 px-6 py-16 lg:grid-cols-2 lg:py-24">
          <div>
            <FadeIn>
              <span className="chip border border-primary/20 bg-primary-soft text-primary">
                <ShieldCheck size={13} /> Screening companion · not a diagnostic authority
              </span>
            </FadeIn>
            <FadeIn delay={0.05}>
              <h1 className="mt-6 text-4xl font-bold leading-[1.1] text-text-primary sm:text-5xl">
                Cardiovascular screening for{" "}
                <span className="bg-primary-gradient bg-clip-text text-transparent">
                  low-resource settings
                </span>
              </h1>
            </FadeIn>
            <FadeIn delay={0.1}>
              <p className="mt-5 max-w-xl text-lg leading-relaxed text-text-secondary">
                Estimate cardiovascular risk from the data a health worker actually has — clinical
                vitals always, heart-sound and ECG when available. Snap a report photo to auto-fill.
                Every result explains itself and states its confidence.
              </p>
            </FadeIn>
            <FadeIn delay={0.15} className="mt-8 flex flex-wrap gap-3">
              <Link to={token ? "/dashboard" : "/register"} className="btn-primary px-6 py-3">
                {token ? "Open dashboard" : "Create an account"} <ArrowRight size={18} />
              </Link>
              {!token && (
                <Link to="/login" className="btn-secondary px-6 py-3">
                  Sign in
                </Link>
              )}
            </FadeIn>
          </div>

          {/* Hero visual: a stylised result card */}
          <FadeIn delay={0.2}>
            <HeroCard />
          </FadeIn>
        </div>
      </section>

      {/* Features */}
      <section className="mx-auto max-w-6xl px-6 pb-24">
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {[
            {
              icon: <ScanText size={20} />,
              title: "Snap to auto-fill",
              body: "Photograph a report and the clinical values are read and pre-filled — no manual typing of 13 fields.",
            },
            {
              icon: <Layers size={20} />,
              title: "Works with partial data",
              body: "A clinical-only screening is a full, valid result. Missing modalities are excluded, never assumed normal.",
            },
            {
              icon: <Activity size={20} />,
              title: "Explains itself",
              body: "Each estimate shows which factors drove it, in clinician-friendly language, with direction and weight.",
            },
            {
              icon: <ShieldCheck size={20} />,
              title: "Honest about uncertainty",
              body: "Calibrated probabilities and a confidence figure on every result. It flags what it doesn't know.",
            },
          ].map((f, i) => (
            <FadeIn key={f.title} delay={0.05 * i}>
              <div className="card-interactive h-full">
                <span className="inline-grid h-10 w-10 place-items-center rounded-control bg-primary-soft text-primary">
                  {f.icon}
                </span>
                <h3 className="mt-4 font-semibold text-text-primary">{f.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-text-secondary">{f.body}</p>
              </div>
            </FadeIn>
          ))}
        </div>
      </section>
    </div>
  );
}

function HeroCard() {
  return (
    <div className="relative">
      <div className="absolute -inset-4 rounded-[28px] bg-hero-mesh opacity-20 blur-2xl" />
      <div className="relative rounded-card border border-border bg-surface p-6 shadow-card-hover">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-text-tertiary">Screening result</p>
            <p className="text-sm font-semibold text-text-primary">Rajesh Kumar · 61</p>
          </div>
          <span className="chip bg-risk-moderate/10 text-risk-moderate">◆ Moderate risk</span>
        </div>

        {/* animated gauge-ish arc */}
        <div className="mt-6 flex items-end justify-center">
          <svg width="200" height="112" viewBox="0 0 200 112">
            <path d="M 20 104 A 80 80 0 0 1 180 104" fill="none" stroke="#E4E7EC" strokeWidth="14" strokeLinecap="round" />
            <motion.path
              d="M 20 104 A 80 80 0 0 1 180 104"
              fill="none"
              stroke="#B54708"
              strokeWidth="14"
              strokeLinecap="round"
              strokeDasharray={251}
              initial={{ strokeDashoffset: 251 }}
              animate={{ strokeDashoffset: 251 * (1 - 0.47) }}
              transition={{ duration: 1.2, delay: 0.4, ease: "easeOut" }}
            />
          </svg>
        </div>
        <div className="-mt-10 text-center">
          <span className="mono text-3xl font-bold text-risk-moderate">47%</span>
        </div>

        <div className="mt-6 space-y-2">
          {[
            { label: "ST-segment depression", up: true, w: 90 },
            { label: "Peak heart rate reached", up: false, w: 62 },
            { label: "Major vessels on fluoroscopy", up: true, w: 48 },
          ].map((f, i) => (
            <div key={f.label} className="flex items-center gap-2">
              <span className="w-40 shrink-0 text-xs text-text-secondary">{f.label}</span>
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-border">
                <motion.div
                  className={`h-full rounded-full ${f.up ? "bg-risk-high" : "bg-risk-low"}`}
                  initial={{ width: 0 }}
                  animate={{ width: `${f.w}%` }}
                  transition={{ duration: 0.7, delay: 0.6 + i * 0.12 }}
                />
              </div>
            </div>
          ))}
        </div>

        <p className="mt-5 rounded-control bg-primary-soft/70 px-3 py-2 text-xs text-text-secondary">
          <span className="font-semibold text-primary">Important: </span>
          A screening aid, not a diagnosis. Only a clinician can diagnose heart disease.
        </p>
      </div>
    </div>
  );
}
