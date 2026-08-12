import { useState } from "react";
import { BookOpen, ChevronDown, HeartPulse } from "lucide-react";
import { Card, FadeIn, Stagger, StaggerItem } from "@/components/ui";
import { CVD_FACTS, FEATURE_REFERENCE } from "@/lib/clinicalReference";

export function ReferencePage() {
  const [open, setOpen] = useState<string | null>(FEATURE_REFERENCE[0].field);

  return (
    <div className="space-y-8">
      <FadeIn>
        <div className="flex items-center gap-2">
          <BookOpen size={20} className="text-primary" />
          <h1 className="text-2xl font-bold text-text-primary">Clinical reference</h1>
        </div>
        <p className="mt-1 max-w-2xl text-sm text-text-secondary">
          What each screening input means and why it matters. Educational context for health workers
          — not medical advice, and separate from any model output.
        </p>
      </FadeIn>

      {/* CVD facts band */}
      <Stagger className="grid gap-3 sm:grid-cols-3">
        {CVD_FACTS.map((f) => (
          <StaggerItem key={f.label}>
            <div className="card h-full bg-primary-gradient text-white">
              <HeartPulse size={18} className="opacity-80" />
              <div className="mono mt-3 text-3xl font-bold">{f.stat}</div>
              <p className="mt-1 text-sm leading-snug text-white/90">{f.label}</p>
              <p className="mt-2 text-xs text-white/60">Source: {f.source}</p>
            </div>
          </StaggerItem>
        ))}
      </Stagger>

      {/* Feature accordion */}
      <FadeIn delay={0.1}>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-text-secondary">
          The 13 screening inputs
        </h2>
        <div className="space-y-2">
          {FEATURE_REFERENCE.map((f) => {
            const isOpen = open === f.field;
            return (
              <Card key={f.field} className="!p-0 overflow-hidden">
                <button
                  onClick={() => setOpen(isOpen ? null : f.field)}
                  className="flex w-full items-center justify-between px-5 py-4 text-left transition-colors hover:bg-primary-soft/30"
                >
                  <span className="font-semibold text-text-primary">{f.name}</span>
                  <ChevronDown
                    size={18}
                    className={`text-text-tertiary transition-transform ${isOpen ? "rotate-180" : ""}`}
                  />
                </button>
                {isOpen && (
                  <div className="grid gap-4 border-t border-border px-5 py-4 sm:grid-cols-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-text-tertiary">
                        What it is
                      </p>
                      <p className="mt-1 text-sm text-text-secondary">{f.what}</p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-text-tertiary">
                        Why it matters
                      </p>
                      <p className="mt-1 text-sm text-text-secondary">{f.whyItMatters}</p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-text-tertiary">
                        Typical values
                      </p>
                      <p className="mt-1 text-sm text-text-secondary">{f.typical}</p>
                    </div>
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      </FadeIn>

      <FadeIn delay={0.15}>
        <p className="rounded-control border border-primary/15 bg-primary-soft/70 px-4 py-3 text-xs leading-relaxed text-text-secondary">
          <span className="font-semibold text-primary">Note: </span>
          This reference is for orientation only. CardioSense is a screening aid, not a diagnostic
          authority — clinical decisions must be made by a qualified clinician.
        </p>
      </FadeIn>
    </div>
  );
}
