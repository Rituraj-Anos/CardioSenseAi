import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "motion/react";
import {
  HeartPulse,
  ArrowRight,
  ScanLine,
  Brain,
  ClipboardList,
  Layers,
  ShieldCheck,
  Siren,
  Activity,
  Stethoscope,
  Waves,
  Check,
} from "lucide-react";
import { useAuthStore } from "@/store/auth";
import { Counter, Eyebrow, Reveal, Stagger, StaggerItem } from "./parts";
import { ScanDemo } from "./ScanDemo";
import { EDUCATION } from "./education";

export function MarketingPage() {
  const token = useAuthStore((s) => s.accessToken);
  const enter = token ? "/dashboard" : "/login";

  return (
    <div className="min-h-screen bg-background font-body text-text-primary">
      <Nav enter={enter} />
      <Hero enter={enter} />
      <StatBar />
      <HowItWorks />
      <Features />
      <ProductPreview enter={enter} />
      <Awareness />
      <Faq />
      <Cta enter={enter} />
      <Footer />
    </div>
  );
}

/* ------------------------------- Nav ------------------------------------- */
function Nav({ enter }: { enter: string }) {
  const [solid, setSolid] = useState(false);
  useEffect(() => {
    const on = () => setSolid(window.scrollY > 24);
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);
  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 transition-all duration-300 ${
        solid ? "border-b border-border bg-surface/85 backdrop-blur-md" : "bg-transparent"
      }`}
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3.5">
        <a href="#top" className="flex items-center gap-2.5">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-primary-gradient text-white shadow-sm">
            <HeartPulse size={19} />
          </span>
          <span className="font-display text-lg font-bold">
            CardioSense <span className="text-primary">AI</span>
          </span>
        </a>
        <nav className="hidden items-center gap-7 text-sm font-medium text-text-secondary md:flex">
          <a href="#how" className="transition-colors hover:text-primary">How it works</a>
          <a href="#features" className="transition-colors hover:text-primary">Features</a>
          <a href="#why" className="transition-colors hover:text-primary">Why it matters</a>
          <a href="#faq" className="transition-colors hover:text-primary">FAQ</a>
        </nav>
        <Link
          to={enter}
          className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-white shadow-sm transition-all hover:bg-primary-hover active:scale-[0.98]"
        >
          Open app <ArrowRight size={15} />
        </Link>
      </div>
    </header>
  );
}

/* ------------------------------- Hero ------------------------------------ */
function Hero({ enter }: { enter: string }) {
  return (
    <section id="top" className="relative overflow-hidden pt-32 pb-20 sm:pt-40">
      {/* soft background wash */}
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute left-1/2 top-0 h-[520px] w-[820px] -translate-x-1/2 rounded-full bg-primary/5 blur-3xl" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_1px_1px,rgba(16,24,40,0.04)_1px,transparent_0)] [background-size:26px_26px]" />
      </div>

      <div className="mx-auto grid max-w-6xl items-center gap-12 px-6 lg:grid-cols-[1.05fr_1fr]">
        <div>
          <Reveal>
            <Eyebrow>
              <ScanLine size={13} /> Scan · Predict · Explain
            </Eyebrow>
          </Reveal>
          <Reveal delay={0.05}>
            <h1 className="mt-5 font-display text-[2.7rem] font-extrabold leading-[1.05] tracking-tight sm:text-6xl">
              Turn a report photo into a{" "}
              <span className="text-primary">heart-risk read</span> in seconds.
            </h1>
          </Reveal>
          <Reveal delay={0.1}>
            <p className="mt-5 max-w-xl text-lg leading-relaxed text-text-secondary">
              CardioSense reads a clinical report, analyses it against a validated model, and returns
              a calibrated risk score with the reasoning shown — built for the clinics and health
              workers who need it most.
            </p>
          </Reveal>
          <Reveal delay={0.15}>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link
                to={enter}
                className="inline-flex items-center gap-2 rounded-xl bg-primary px-6 py-3.5 text-base font-semibold text-white shadow-md transition-all hover:bg-primary-hover active:scale-[0.98]"
              >
                Try the screening app <ArrowRight size={18} />
              </Link>
              <a
                href="#how"
                className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface px-6 py-3.5 text-base font-semibold text-text-primary transition-all hover:border-primary/30 hover:bg-primary-soft"
              >
                See how it works
              </a>
            </div>
          </Reveal>
          <Reveal delay={0.2}>
            <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-text-secondary">
              {["Explainable, not a black box", "Works with partial data", "A screening aid, not a diagnosis"].map(
                (t) => (
                  <span key={t} className="inline-flex items-center gap-1.5">
                    <Check size={15} className="text-primary" /> {t}
                  </span>
                )
              )}
            </div>
          </Reveal>
        </div>

        <Reveal delay={0.15} y={28}>
          <ScanDemo />
        </Reveal>
      </div>
    </section>
  );
}

/* ------------------------------ Stat bar --------------------------------- */
function StatBar() {
  const stats = [
    { n: 27, suffix: "%", label: "of deaths in India are cardiovascular" },
    { n: 45, suffix: "%", label: "of deaths at ages 40–69 are cardiac" },
    { n: 13, suffix: "", label: "clinical signals in every risk read" },
    { n: 100, suffix: "%", label: "of results carry a confidence level" },
  ];
  return (
    <section className="border-y border-border bg-surface">
      <Stagger className="mx-auto grid max-w-6xl grid-cols-2 gap-6 px-6 py-10 md:grid-cols-4">
        {stats.map((s) => (
          <StaggerItem key={s.label} className="text-center">
            <div className="font-display text-4xl font-extrabold text-primary">
              <Counter to={s.n} suffix={s.suffix} />
            </div>
            <p className="mt-1.5 text-sm text-text-secondary">{s.label}</p>
          </StaggerItem>
        ))}
      </Stagger>
    </section>
  );
}

/* ---------------------------- How it works ------------------------------- */
function HowItWorks() {
  const steps = [
    {
      icon: <ScanLine size={22} />,
      step: "01",
      title: "Scan a report",
      body: "Snap a photo of a lab or clinical report. CardioSense reads the values and fills the form — no manual typing of a dozen fields.",
    },
    {
      icon: <Brain size={22} />,
      step: "02",
      title: "AI analyses the signals",
      body: "A validated model weighs 13 clinical signals — and, when available, heart-sound and ECG recordings — into one calibrated risk estimate.",
    },
    {
      icon: <ClipboardList size={22} />,
      step: "03",
      title: "Get an explained result",
      body: "See the risk band, the confidence, the exact factors that drove it, and a clear recommendation for the next step.",
    },
  ];
  return (
    <section id="how" className="py-24">
      <div className="mx-auto max-w-6xl px-6">
        <Reveal className="mx-auto max-w-2xl text-center">
          <Eyebrow>How it works</Eyebrow>
          <h2 className="mt-4 font-display text-3xl font-bold sm:text-4xl">
            From a photo to a decision, in three steps
          </h2>
          <p className="mt-4 text-lg text-text-secondary">
            The whole flow is designed for speed at the point of care.
          </p>
        </Reveal>

        <Stagger className="mt-14 grid gap-6 md:grid-cols-3" gap={0.12}>
          {steps.map((s, i) => (
            <StaggerItem key={s.step}>
              <div className="group relative h-full rounded-2xl border border-border bg-surface p-7 transition-all duration-300 hover:-translate-y-1 hover:border-primary/30 hover:shadow-card-hover">
                <div className="flex items-center justify-between">
                  <span className="grid h-12 w-12 place-items-center rounded-xl bg-primary-soft text-primary transition-colors group-hover:bg-primary group-hover:text-white">
                    {s.icon}
                  </span>
                  <span className="font-display text-3xl font-bold text-border">{s.step}</span>
                </div>
                <h3 className="mt-5 font-display text-xl font-bold">{s.title}</h3>
                <p className="mt-2 text-[15px] leading-relaxed text-text-secondary">{s.body}</p>
              </div>
              {i < steps.length - 1 && (
                <div className="pointer-events-none absolute" aria-hidden />
              )}
            </StaggerItem>
          ))}
        </Stagger>
      </div>
    </section>
  );
}

/* ------------------------------ Features --------------------------------- */
function Features() {
  const feats = [
    {
      icon: <ScanLine size={20} />,
      title: "Report auto-fill",
      body: "Reads lab reports and pre-fills the clinical form for review — no re-typing.",
      span: "md:col-span-2",
    },
    {
      icon: <Activity size={20} />,
      title: "Explainable risk",
      body: "Every score shows the factors behind it, in clinician-friendly language.",
      span: "",
    },
    {
      icon: <Layers size={20} />,
      title: "Multimodal fusion",
      body: "Clinical vitals, heart sound (PCG) and ECG combine into one honest signal.",
      span: "",
    },
    {
      icon: <Stethoscope size={20} />,
      title: "Triage dashboard",
      body: "A risk-sorted queue so the most urgent patients rise to the top.",
      span: "md:col-span-2",
    },
    {
      icon: <ShieldCheck size={20} />,
      title: "Honest by design",
      body: "Calibrated probabilities with confidence — a screening aid, never a verdict.",
      span: "",
    },
    {
      icon: <Siren size={20} />,
      title: "Emergency SOS",
      body: "Critical results can trigger a countdown, auto-dial and nearest-hospital alert.",
      span: "md:col-span-2",
    },
  ];
  return (
    <section id="features" className="bg-surface py-24">
      <div className="mx-auto max-w-6xl px-6">
        <Reveal className="max-w-2xl">
          <Eyebrow>Features</Eyebrow>
          <h2 className="mt-4 font-display text-3xl font-bold sm:text-4xl">
            Everything a screening tool should be — and honest about what it isn't
          </h2>
        </Reveal>

        <Stagger className="mt-12 grid gap-4 md:grid-cols-3" gap={0.07}>
          {feats.map((f) => (
            <StaggerItem key={f.title} className={f.span}>
              <div className="flex h-full flex-col rounded-2xl border border-border bg-background p-6 transition-all duration-300 hover:border-primary/30 hover:shadow-card">
                <span className="grid h-11 w-11 place-items-center rounded-xl bg-primary-soft text-primary">
                  {f.icon}
                </span>
                <h3 className="mt-4 font-display text-lg font-bold">{f.title}</h3>
                <p className="mt-1.5 text-[15px] leading-relaxed text-text-secondary">{f.body}</p>
              </div>
            </StaggerItem>
          ))}
        </Stagger>
      </div>
    </section>
  );
}

/* --------------------------- Product preview ----------------------------- */
function ProductPreview({ enter }: { enter: string }) {
  return (
    <section className="py-24">
      <div className="mx-auto max-w-6xl px-6">
        <div className="grid items-center gap-12 lg:grid-cols-2">
          <Reveal>
            <Eyebrow>The clinical workspace</Eyebrow>
            <h2 className="mt-4 font-display text-3xl font-bold sm:text-4xl">
              A calm, legible dashboard — reasoning in plain sight
            </h2>
            <p className="mt-4 text-lg leading-relaxed text-text-secondary">
              Health workers see a calibrated risk band, the factors that drove it, and a clear next
              step. No jargon, no black box — just a screening signal they can act on.
            </p>
            <ul className="mt-6 space-y-3">
              {[
                "Risk-sorted triage queue",
                "Per-patient explanation with factor weights",
                "Confidence and uncertainty on every result",
              ].map((t) => (
                <li key={t} className="flex items-center gap-2.5 text-[15px] text-text-primary">
                  <span className="grid h-5 w-5 place-items-center rounded-full bg-primary text-white">
                    <Check size={12} />
                  </span>
                  {t}
                </li>
              ))}
            </ul>
            <Link
              to={enter}
              className="mt-8 inline-flex items-center gap-2 rounded-xl bg-primary px-6 py-3 text-base font-semibold text-white shadow-sm transition-all hover:bg-primary-hover active:scale-[0.98]"
            >
              Explore the dashboard <ArrowRight size={18} />
            </Link>
          </Reveal>

          <Reveal delay={0.1} y={28}>
            <DashboardMock />
          </Reveal>
        </div>
      </div>
    </section>
  );
}

function DashboardMock() {
  return (
    <div className="relative">
      <div className="pointer-events-none absolute -inset-6 -z-10 rounded-[32px] bg-primary/10 blur-3xl" />
      <div className="overflow-hidden rounded-2xl border border-border bg-surface shadow-card-hover">
        <div className="flex items-center justify-between bg-primary-gradient px-4 py-3 text-white">
          <span className="flex items-center gap-2 text-sm font-semibold">
            <Activity size={15} /> Screening result
          </span>
          <span className="rounded-full bg-white/20 px-2.5 py-0.5 text-xs font-semibold">High risk</span>
        </div>
        <div className="grid gap-3 p-4 sm:grid-cols-3">
          <div className="rounded-xl border border-border bg-background p-4 sm:col-span-1">
            <p className="text-xs text-text-secondary">Estimated risk</p>
            <p className="mt-1 font-mono text-4xl font-bold text-risk-high">76%</p>
            <p className="mt-1 text-xs text-text-secondary">confidence 92%</p>
          </div>
          <div className="grid gap-3 sm:col-span-2">
            <div className="grid grid-cols-2 gap-3">
              <Mini label="Resting BP" v="158" u="mm Hg" />
              <Mini label="Peak HR" v="118" u="bpm" />
            </div>
            <div className="rounded-xl border border-border bg-background p-3">
              <p className="text-xs font-medium text-text-secondary">Top factors</p>
              <div className="mt-2 space-y-1.5">
                <Bar label="ST-segment depression" pct={92} />
                <Bar label="Major vessels" pct={70} />
                <Bar label="Peak heart rate" pct={54} down />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Mini({ label, v, u }: { label: string; v: string; u: string }) {
  return (
    <div className="rounded-xl border border-border bg-background p-3">
      <p className="text-xs text-text-secondary">{label}</p>
      <p className="mt-0.5 font-mono text-xl font-bold">
        {v} <span className="text-xs font-normal text-text-tertiary">{u}</span>
      </p>
      <svg viewBox="0 0 100 20" className="mt-1 h-5 w-full" preserveAspectRatio="none">
        <polyline
          points="0,16 16,12 32,14 48,7 64,10 80,4 100,6"
          fill="none"
          stroke="#0E6E64"
          strokeWidth="2"
          strokeLinecap="round"
        />
      </svg>
    </div>
  );
}

function Bar({ label, pct, down }: { label: string; pct: number; down?: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-36 shrink-0 text-[11px] text-text-primary">{label}</span>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-border">
        <div className={`h-full rounded-full ${down ? "bg-risk-low" : "bg-risk-high"}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

/* ------------------------------ Awareness -------------------------------- */
function Awareness() {
  return (
    <section id="why" className="bg-surface py-24">
      <div className="mx-auto max-w-6xl px-6">
        <Reveal className="max-w-2xl">
          <Eyebrow>Why it matters</Eyebrow>
          <h2 className="mt-4 font-display text-3xl font-bold sm:text-4xl">
            The heart rarely fails without warning
          </h2>
          <p className="mt-4 text-lg leading-relaxed text-text-secondary">
            The warning just goes unheard — because specialists are hours away and equipment is
            scarce. Understanding the signals is the first step to catching them early.
          </p>
        </Reveal>

        <Stagger className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3" gap={0.06}>
          {EDUCATION.map((e) => (
            <StaggerItem key={e.title}>
              <div className="h-full rounded-2xl border border-border bg-background p-5">
                <div className="flex items-center gap-2 text-primary">
                  <Waves size={16} />
                  <p className="font-display font-semibold text-text-primary">{e.title}</p>
                </div>
                <p className="mt-2 text-sm leading-relaxed text-text-secondary">{e.body}</p>
              </div>
            </StaggerItem>
          ))}
        </Stagger>
        <p className="mt-6 text-xs text-text-tertiary">
          National figures for India (WHO / national health data), indicative — not a substitute for
          local screening data.
        </p>
      </div>
    </section>
  );
}

/* --------------------------------- FAQ ----------------------------------- */
function Faq() {
  const items = [
    {
      q: "Is CardioSense a diagnosis?",
      a: "No. It's a screening aid that estimates risk and prompts the right next step. Only a qualified clinician can diagnose or rule out heart disease — and CardioSense states that on every result.",
    },
    {
      q: "What does it need to work?",
      a: "Clinical vitals are enough for a full result. Heart-sound and ECG recordings add signal when available, but the tool degrades gracefully — a missing input is never treated as a normal finding.",
    },
    {
      q: "How does the report scan work?",
      a: "You upload a photo of a lab or clinical report. CardioSense reads the printed values and pre-fills the form. You review and confirm every value before anything is analysed.",
    },
    {
      q: "Can I trust the risk score?",
      a: "The model is calibrated and every result carries a confidence level. It's tuned to prioritise catching at-risk patients, and it shows the exact factors behind each estimate.",
    },
  ];
  const [open, setOpen] = useState(0);
  return (
    <section id="faq" className="py-24">
      <div className="mx-auto max-w-3xl px-6">
        <Reveal className="text-center">
          <Eyebrow>FAQ</Eyebrow>
          <h2 className="mt-4 font-display text-3xl font-bold sm:text-4xl">Questions, answered plainly</h2>
        </Reveal>
        <div className="mt-10 space-y-3">
          {items.map((it, i) => {
            const isOpen = open === i;
            return (
              <Reveal key={it.q} delay={i * 0.05}>
                <div className="overflow-hidden rounded-2xl border border-border bg-surface">
                  <button
                    onClick={() => setOpen(isOpen ? -1 : i)}
                    className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left"
                  >
                    <span className="font-display font-semibold">{it.q}</span>
                    <motion.span animate={{ rotate: isOpen ? 45 : 0 }} className="text-primary">
                      <span className="block text-xl leading-none">+</span>
                    </motion.span>
                  </button>
                  <motion.div
                    initial={false}
                    animate={{ height: isOpen ? "auto" : 0, opacity: isOpen ? 1 : 0 }}
                    transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
                    className="overflow-hidden"
                  >
                    <p className="px-5 pb-5 text-[15px] leading-relaxed text-text-secondary">{it.a}</p>
                  </motion.div>
                </div>
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}

/* --------------------------------- CTA ----------------------------------- */
function Cta({ enter }: { enter: string }) {
  return (
    <section className="px-6 py-20">
      <Reveal>
        <div className="relative mx-auto max-w-5xl overflow-hidden rounded-3xl bg-primary-gradient px-8 py-16 text-center text-white shadow-card-hover">
          <div className="pointer-events-none absolute -left-16 top-0 h-64 w-64 rounded-full bg-white/10 blur-3xl" />
          <div className="pointer-events-none absolute -right-10 bottom-0 h-64 w-64 rounded-full bg-white/5 blur-3xl" />
          <ShieldCheck size={40} className="relative mx-auto opacity-90" />
          <h2 className="relative mt-5 font-display text-3xl font-bold sm:text-5xl">
            Screening that speaks plainly
          </h2>
          <p className="relative mx-auto mt-4 max-w-xl text-lg text-white/85">
            Scan a report, get an explained risk read, and route the right patients onward — built
            for where care is hardest to reach.
          </p>
          <Link
            to={enter}
            className="relative mt-8 inline-flex items-center gap-2 rounded-xl bg-white px-7 py-3.5 text-base font-semibold text-primary shadow-lg transition-all hover:bg-white/90 active:scale-[0.98]"
          >
            Open CardioSense AI <ArrowRight size={18} />
          </Link>
          <p className="relative mt-5 text-xs text-white/60">A screening aid, not a diagnosis.</p>
        </div>
      </Reveal>
    </section>
  );
}

/* ------------------------------- Footer ---------------------------------- */
function Footer() {
  return (
    <footer className="border-t border-border bg-surface py-12">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-3 px-6 text-center">
        <div className="flex items-center gap-2">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary-gradient text-white">
            <HeartPulse size={16} />
          </span>
          <span className="font-display font-bold">
            CardioSense <span className="text-primary">AI</span>
          </span>
        </div>
        <p className="text-sm text-text-secondary">
          A cardiovascular screening companion for low-resource settings.
        </p>
        <p className="text-xs text-text-tertiary">
          Screening aid, not a diagnosis · every result includes explicit uncertainty
        </p>
      </div>
    </footer>
  );
}
