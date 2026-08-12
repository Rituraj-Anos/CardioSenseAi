import { useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import {
  ScanText,
  UploadCloud,
  Sparkles,
  CheckCircle2,
  Stethoscope,
  Waves,
  Activity,
  ArrowRight,
  ArrowLeft,
  Loader2,
} from "lucide-react";
import { apiError, dashboardApi, screeningApi } from "@/lib/api";
import { Card, Disclaimer, ErrorNote, FadeIn } from "@/components/ui";
import { CLINICAL_FIELDS, DEMO_CONCERNING, DEMO_NORMAL } from "@/lib/clinicalFields";
import type { ClinicalInput, ReportExtraction } from "@/lib/types";

type Step = "clinical" | "pcg" | "ecg";

export function NewScreeningPage() {
  useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const screeningId = params.get("screening");

  const [step, setStep] = useState<Step>("clinical");
  const [values, setValues] = useState<Record<string, number | "">>(() =>
    Object.fromEntries(
      CLINICAL_FIELDS.map((f) => [f.name, f.kind === "select" ? f.options[0].value : ""])
    )
  );
  const [autoFilled, setAutoFilled] = useState<Record<string, string>>({}); // field -> source snippet
  const [error, setError] = useState<string | null>(null);
  const [clinicalSaved, setClinicalSaved] = useState(false);
  const [uploads, setUploads] = useState<{ pcg?: string; ecg?: string }>({});

  const { data: models } = useQuery({ queryKey: ["models"], queryFn: dashboardApi.systemModels });

  const extract = useMutation({
    mutationFn: (file: File) => screeningApi.extractReport(screeningId!, file),
    onSuccess: (res: ReportExtraction) => {
      const next = { ...values };
      const filled: Record<string, string> = {};
      for (const [name, info] of Object.entries(res.extracted)) {
        next[name] = info.value;
        filled[name] = info.source_text;
      }
      setValues(next);
      setAutoFilled(filled);
      setClinicalSaved(false);
      setError(null);
    },
    onError: (e) => setError(apiError(e)),
  });

  const saveClinical = useMutation({
    mutationFn: () => {
      const payload = {} as ClinicalInput;
      for (const f of CLINICAL_FIELDS) {
        const v = values[f.name];
        (payload as any)[f.name] = v === "" ? NaN : Number(v);
      }
      return screeningApi.submitClinical(screeningId!, payload);
    },
    onSuccess: () => {
      setClinicalSaved(true);
      setError(null);
    },
    onError: (e) => setError(apiError(e)),
  });

  const analyze = useMutation({
    mutationFn: () => screeningApi.analyze(screeningId!),
    onSuccess: () => navigate(`/screening/${screeningId}/result`),
    onError: (e) => setError(apiError(e)),
  });

  const pcgUpload = useMutation({
    mutationFn: (file: File) => screeningApi.uploadPcg(screeningId!, file),
    onSuccess: (r) => setUploads((u) => ({ ...u, pcg: r.quality_note })),
    onError: (e) => setError(apiError(e)),
  });
  const ecgUpload = useMutation({
    mutationFn: (file: File) => screeningApi.uploadEcg(screeningId!, file, 250),
    onSuccess: (r) => setUploads((u) => ({ ...u, ecg: r.quality_note })),
    onError: (e) => setError(apiError(e)),
  });

  const missingRequired = useMemo(
    () => CLINICAL_FIELDS.some((f) => values[f.name] === "" || values[f.name] === undefined),
    [values]
  );

  if (!screeningId) {
    return <ErrorNote message="No screening in progress. Start one from the dashboard." />;
  }

  const setValue = (name: string, v: number | "") => {
    setValues((prev) => ({ ...prev, [name]: v }));
    setAutoFilled((prev) => {
      // Once a user edits an auto-filled field, drop the "auto" marker.
      if (!(name in prev)) return prev;
      const next = { ...prev };
      delete next[name];
      return next;
    });
    setClinicalSaved(false);
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <FadeIn>
        <Stepper current={step} />
      </FadeIn>

      <AnimatePresence mode="wait">
        {step === "clinical" && (
          <StepShell key="clinical">
            <ReportUpload
              busy={extract.isPending}
              engineNote={extract.data && !extract.data.engine_available ? extract.data.engine_note : null}
              result={extract.data?.engine_available ? extract.data : null}
              onFile={(f) => extract.mutate(f)}
            />

            <Card>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h1 className="text-xl font-semibold text-text-primary">Clinical measurements</h1>
                  <p className="mt-1 text-sm text-text-secondary">
                    {Object.keys(autoFilled).length > 0
                      ? "Review the auto-filled values and complete any remaining fields."
                      : "Enter values, or auto-fill from a report photo above."}
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    className="btn-secondary py-1.5 text-xs"
                    onClick={() => {
                      setValues({ ...DEMO_NORMAL });
                      setAutoFilled({});
                    }}
                    type="button"
                  >
                    Demo: low-risk
                  </button>
                  <button
                    className="btn-secondary py-1.5 text-xs"
                    onClick={() => {
                      setValues({ ...DEMO_CONCERNING });
                      setAutoFilled({});
                    }}
                    type="button"
                  >
                    Demo: concerning
                  </button>
                </div>
              </div>

              <div className="mt-6 grid gap-4 sm:grid-cols-2">
                {CLINICAL_FIELDS.map((f) => {
                  const isAuto = f.name in autoFilled;
                  return (
                    <div key={f.name}>
                      <label className="label flex items-center gap-2" htmlFor={f.name}>
                        {f.label}
                        {f.kind === "number" && f.unit && (
                          <span className="font-normal text-text-secondary">({f.unit})</span>
                        )}
                        {isAuto && (
                          <span
                            className="chip bg-primary-soft text-primary"
                            title={`From report: "${autoFilled[f.name]}"`}
                          >
                            <Sparkles size={11} /> auto
                          </span>
                        )}
                      </label>
                      {f.kind === "select" ? (
                        <select
                          id={f.name}
                          className={`input ${isAuto ? "border-primary/50 bg-primary-soft/30" : ""}`}
                          value={values[f.name]}
                          onChange={(e) => setValue(f.name, Number(e.target.value))}
                        >
                          {f.options.map((o) => (
                            <option key={o.value} value={o.value}>
                              {o.label}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <input
                          id={f.name}
                          type="number"
                          step={f.step ?? 1}
                          min={f.min}
                          max={f.max}
                          className={`input mono ${isAuto ? "border-primary/50 bg-primary-soft/30" : ""}`}
                          value={values[f.name]}
                          onChange={(e) =>
                            setValue(f.name, e.target.value === "" ? "" : Number(e.target.value))
                          }
                        />
                      )}
                      {f.hint && <p className="mt-1 text-xs text-text-tertiary">{f.hint}</p>}
                    </div>
                  );
                })}
              </div>

              {error && (
                <div className="mt-4">
                  <ErrorNote message={error} />
                </div>
              )}

              <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
                <button
                  className="btn-secondary"
                  onClick={() => saveClinical.mutate()}
                  disabled={missingRequired || saveClinical.isPending}
                >
                  {saveClinical.isPending ? (
                    <>
                      <Loader2 size={16} className="animate-spin" /> Saving…
                    </>
                  ) : clinicalSaved ? (
                    <>
                      <CheckCircle2 size={16} /> Saved
                    </>
                  ) : (
                    "Save clinical data"
                  )}
                </button>
                <div className="flex gap-2">
                  <button className="btn-secondary" onClick={() => setStep("pcg")} disabled={!clinicalSaved}>
                    Add recordings <ArrowRight size={16} />
                  </button>
                  <button
                    className="btn-primary"
                    onClick={() => analyze.mutate()}
                    disabled={!clinicalSaved || analyze.isPending}
                  >
                    {analyze.isPending ? (
                      <>
                        <Loader2 size={16} className="animate-spin" /> Analysing…
                      </>
                    ) : (
                      <>Analyse now</>
                    )}
                  </button>
                </div>
              </div>
            </Card>
          </StepShell>
        )}

        {step === "pcg" && (
          <StepShell key="pcg">
            <UploadStep
              title="Heart sound (PCG)"
              icon={<Waves size={20} />}
              available={models?.modalities.pcg.available ?? false}
              unavailableReason={models?.modalities.pcg.reason ?? undefined}
              accept=".wav,.flac,.ogg"
              result={uploads.pcg}
              uploading={pcgUpload.isPending}
              onUpload={(f) => pcgUpload.mutate(f)}
              onBack={() => setStep("clinical")}
              onNext={() => setStep("ecg")}
            />
          </StepShell>
        )}

        {step === "ecg" && (
          <StepShell key="ecg">
            <UploadStep
              title="ECG waveform"
              icon={<Activity size={20} />}
              available={models?.modalities.ecg.available ?? false}
              unavailableReason={models?.modalities.ecg.reason ?? undefined}
              accept=".csv,.txt,.json,.dat"
              result={uploads.ecg}
              uploading={ecgUpload.isPending}
              onUpload={(f) => ecgUpload.mutate(f)}
              onBack={() => setStep("pcg")}
              onNext={() => analyze.mutate()}
              nextLabel={analyze.isPending ? "Analysing…" : "Finish & analyse"}
              nextBusy={analyze.isPending}
            />
          </StepShell>
        )}
      </AnimatePresence>

      {models && <Disclaimer text={models.disclaimer} />}
    </div>
  );
}

function StepShell({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: 16 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -16 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="space-y-6"
    >
      {children}
    </motion.div>
  );
}

function ReportUpload({
  busy,
  result,
  engineNote,
  onFile,
}: {
  busy: boolean;
  result: ReportExtraction | null;
  engineNote: string | null;
  onFile: (f: File) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  return (
    <div className="overflow-hidden rounded-card border border-primary/25 bg-primary-soft/40">
      <div className="flex items-start gap-3 border-b border-primary/15 bg-primary-soft/60 px-5 py-3">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-control bg-primary-gradient text-white">
          <ScanText size={18} />
        </span>
        <div>
          <h2 className="text-sm font-semibold text-text-primary">Auto-fill from a report photo</h2>
          <p className="text-xs text-text-secondary">
            Upload a photo of a clinical/lab report — we read it and pre-fill the fields. You review
            before submitting.
          </p>
        </div>
      </div>

      <div className="p-5">
        <div
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            if (e.dataTransfer.files?.[0]) onFile(e.dataTransfer.files[0]);
          }}
          className={`flex cursor-pointer flex-col items-center justify-center rounded-control border-2 border-dashed px-6 py-8 text-center transition-colors ${
            dragging ? "border-primary bg-primary-soft" : "border-primary/30 bg-surface hover:border-primary"
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
          />
          {busy ? (
            <div className="flex items-center gap-2 text-primary">
              <Loader2 size={18} className="animate-spin" />
              <span className="text-sm font-medium">Reading report…</span>
            </div>
          ) : (
            <>
              <UploadCloud size={26} className="text-primary" />
              <span className="mt-2 text-sm font-medium text-text-primary">
                Drop a report image, or click to choose
              </span>
              <span className="mt-0.5 text-xs text-text-tertiary">JPG, PNG, WEBP · a clear photo works best</span>
            </>
          )}
        </div>

        {engineNote && (
          <div className="mt-3 rounded-control border border-risk-moderate/30 bg-risk-moderate/5 px-3 py-2 text-xs text-risk-moderate">
            {engineNote}
          </div>
        )}

        {result && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-3 rounded-control border border-primary/20 bg-surface px-4 py-3"
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-sm font-medium text-primary">
                <CheckCircle2 size={16} />
                Read {result.found_count} of 13 fields from the report
              </div>
              <span className="chip bg-primary-soft text-primary">
                read in {(result.elapsed_ms / 1000).toFixed(1)}s
              </span>
            </div>
            {result.missing_fields.length > 0 && (
              <p className="mt-1 text-xs text-text-secondary">
                Still need manual entry: {result.missing_fields.join(", ")}
              </p>
            )}
            <p className="mt-1 text-xs text-text-tertiary">
              Values are pre-filled below for you to verify — nothing is submitted automatically.
            </p>
          </motion.div>
        )}
      </div>
    </div>
  );
}

function Stepper({ current }: { current: Step }) {
  const steps: { key: Step; label: string; icon: React.ReactNode }[] = [
    { key: "clinical", label: "Clinical", icon: <Stethoscope size={15} /> },
    { key: "pcg", label: "Heart sound", icon: <Waves size={15} /> },
    { key: "ecg", label: "ECG", icon: <Activity size={15} /> },
  ];
  const idx = steps.findIndex((s) => s.key === current);
  return (
    <div className="flex items-center gap-2">
      {steps.map((s, i) => (
        <div key={s.key} className="flex flex-1 items-center gap-2">
          <div
            className={`flex h-8 w-8 items-center justify-center rounded-full transition-colors ${
              i <= idx ? "bg-primary-gradient text-white" : "bg-border text-text-tertiary"
            }`}
          >
            {s.icon}
          </div>
          <span
            className={`text-sm ${i === idx ? "font-semibold text-text-primary" : "text-text-secondary"}`}
          >
            {s.label}
            {i > 0 && <span className="ml-1 text-xs font-normal text-text-tertiary">optional</span>}
          </span>
          {i < steps.length - 1 && <div className="h-px flex-1 bg-border" />}
        </div>
      ))}
    </div>
  );
}

function UploadStep({
  title,
  icon,
  available,
  unavailableReason,
  accept,
  result,
  uploading,
  onUpload,
  onBack,
  onNext,
  nextLabel = "Next",
  nextBusy = false,
}: {
  title: string;
  icon: React.ReactNode;
  available: boolean;
  unavailableReason?: string;
  accept: string;
  result?: string;
  uploading: boolean;
  onUpload: (f: File) => void;
  onBack: () => void;
  onNext: () => void;
  nextLabel?: string;
  nextBusy?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <Card>
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-control bg-primary-soft text-primary">
          {icon}
        </span>
        <h1 className="text-xl font-semibold text-text-primary">{title}</h1>
      </div>

      {!available && (
        <div className="mt-4 rounded-control border border-risk-moderate/30 bg-risk-moderate/5 px-3 py-2 text-sm text-risk-moderate">
          No trained model for this modality yet. You can still upload — the recording is stored and
          quality-checked, but it won't contribute to the score (excluded from fusion, not treated
          as a normal finding).
          {unavailableReason && <span className="mt-1 block text-xs opacity-80">{unavailableReason}</span>}
        </div>
      )}

      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
        className="mt-5 flex cursor-pointer flex-col items-center justify-center rounded-card border-2 border-dashed border-border bg-background px-6 py-10 text-center transition-colors hover:border-primary"
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          className="hidden"
          onChange={(e) => e.target.files?.[0] && onUpload(e.target.files[0])}
        />
        {uploading ? (
          <div className="flex items-center gap-2 text-primary">
            <Loader2 size={18} className="animate-spin" />
            <span className="text-sm">Uploading & checking quality…</span>
          </div>
        ) : (
          <>
            <UploadCloud size={24} className="text-text-tertiary" />
            <span className="mt-2 text-sm font-medium text-text-primary">Click to select a file</span>
            <span className="mt-0.5 text-xs text-text-tertiary">Accepted: {accept}</span>
          </>
        )}
      </div>

      {result && (
        <div className="mt-4 rounded-control bg-primary-soft px-3 py-2 text-sm text-text-secondary">
          {result}
        </div>
      )}

      <div className="mt-6 flex justify-between">
        <button className="btn-secondary" onClick={onBack}>
          <ArrowLeft size={16} /> Back
        </button>
        <button className="btn-primary" onClick={onNext} disabled={nextBusy}>
          {nextBusy && <Loader2 size={16} className="animate-spin" />}
          {nextLabel} {!nextBusy && <ArrowRight size={16} />}
        </button>
      </div>
    </Card>
  );
}
