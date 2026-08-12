import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowUpRight,
  ArrowDownRight,
  Send,
  CheckCircle2,
  Info,
  Loader2,
} from "lucide-react";
import { apiError, dashboardApi, screeningApi } from "@/lib/api";
import {
  Card,
  ConfidenceMeter,
  Disclaimer,
  ErrorNote,
  FadeIn,
  Skeleton,
} from "@/components/ui";
import { RiskGauge } from "@/components/RiskGauge";
import type { ExplanationFactor, PredictionOut, ScreeningResult } from "@/lib/types";

const MODALITY_LABELS: Record<string, string> = {
  clinical: "Clinical vitals",
  pcg: "Heart sound",
  ecg: "ECG",
};

export function ResultPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [referralOpen, setReferralOpen] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["result", id],
    queryFn: () => screeningApi.result(id!),
  });

  const review = useMutation({ mutationFn: () => screeningApi.review(id!) });

  if (isLoading)
    return (
      <div className="mx-auto max-w-3xl space-y-5">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-64" />
        <Skeleton className="h-40" />
      </div>
    );
  if (error) return <ErrorNote message={apiError(error)} />;

  const r = data!;

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <FadeIn>
        <button
          onClick={() => navigate(`/patients/${r.patient_id}`)}
          className="btn-ghost -ml-2 py-1.5 text-sm"
        >
          <ArrowLeft size={16} /> Back to patient
        </button>
      </FadeIn>

      {/* Headline result */}
      <FadeIn delay={0.05}>
        <Card className="overflow-hidden">
          <div className="grid gap-6 sm:grid-cols-[auto_1fr] sm:items-center">
            <div className="flex justify-center">
              <RiskGauge score={r.final_score} band={r.risk_band} />
            </div>
            <div>
              <p className="text-sm text-text-secondary">Screening result</p>
              <h1 className="mt-1 text-xl font-semibold text-text-primary">
                Estimated cardiovascular risk
              </h1>
              <div className="mt-4">
                <ConfidenceMeter value={r.confidence} />
              </div>
            </div>
          </div>

          <div className="mt-6 rounded-control bg-primary-soft/60 p-4">
            <p className="text-sm font-semibold text-text-primary">Recommendation</p>
            <p className="mt-1 text-sm leading-relaxed text-text-secondary">{r.recommendation}</p>
          </div>
        </Card>
      </FadeIn>

      <FadeIn delay={0.1}>
        <ModalitiesCard result={r} />
      </FadeIn>

      {r.per_modality.map((m, i) =>
        m.explanation ? (
          <FadeIn key={m.modality} delay={0.15 + i * 0.05}>
            <ExplanationCard prediction={m} />
          </FadeIn>
        ) : null
      )}

      <FadeIn delay={0.2}>
        <Card>
          <div className="flex items-center gap-2">
            <Info size={16} className="text-text-tertiary" />
            <h2 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">
              What this covers, and what it doesn't
            </h2>
          </div>
          <p className="mt-2 text-sm leading-relaxed text-text-secondary">{r.uncertainty_note}</p>
        </Card>
      </FadeIn>

      <FadeIn delay={0.25} className="flex flex-wrap gap-3">
        <button className="btn-primary" onClick={() => setReferralOpen(true)}>
          <Send size={16} /> Log referral
        </button>
        <button
          className="btn-secondary"
          onClick={() => review.mutate()}
          disabled={review.isPending || review.isSuccess}
        >
          {review.isSuccess ? (
            <>
              <CheckCircle2 size={16} /> Marked reviewed
            </>
          ) : (
            "Mark as reviewed"
          )}
        </button>
      </FadeIn>

      <FadeIn delay={0.3}>
        <Disclaimer text={r.disclaimer} />
      </FadeIn>

      {referralOpen && (
        <ReferralModal screeningId={r.screening_id} onClose={() => setReferralOpen(false)} />
      )}
    </div>
  );
}

function ModalitiesCard({ result }: { result: ScreeningResult }) {
  return (
    <Card>
      <h2 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">
        Contributing modalities
      </h2>
      <p className="mt-1 text-xs text-text-secondary">
        Only modalities that produced a score are shown. Weights are renormalised over what was
        present — absent modalities are excluded, never assumed normal.
      </p>
      <div className="mt-4 space-y-3">
        {result.per_modality.map((m) => {
          const weight = result.weights[m.modality] ?? 0;
          return (
            <div key={m.modality}>
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium text-text-primary">
                  {MODALITY_LABELS[m.modality] ?? m.modality}
                </span>
                <span className="mono text-text-secondary">
                  score {Math.round(m.score * 100)}% · weight {Math.round(weight * 100)}%
                </span>
              </div>
              <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-border">
                <div
                  className="h-full rounded-full bg-primary-gradient"
                  style={{ width: `${weight * 100}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function ExplanationCard({ prediction }: { prediction: PredictionOut }) {
  const exp = prediction.explanation!;
  const isFallback = exp.method !== "shap";
  const max = Math.max(...exp.top_factors.map((f) => f.magnitude), 1e-6);
  return (
    <Card>
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">
          Why this estimate
        </h2>
        <span className="chip bg-primary-soft text-primary">
          {exp.method === "shap" ? "SHAP contributions" : "Global importance (fallback)"}
        </span>
      </div>

      {isFallback && (
        <p className="mt-2 text-xs text-risk-moderate">
          Per-patient explanation was unavailable; showing the model's overall factor importance.
        </p>
      )}

      <div className="mt-4 space-y-2.5">
        {exp.top_factors.map((f) => (
          <FactorRow key={f.feature} factor={f} max={max} />
        ))}
      </div>
    </Card>
  );
}

function FactorRow({ factor, max }: { factor: ExplanationFactor; max: number }) {
  const up = factor.direction === "increases_risk";
  const width = Math.max(6, Math.round((factor.magnitude / max) * 100));
  return (
    <div className="flex items-center gap-3">
      <div className="w-44 shrink-0 text-sm text-text-primary">
        {factor.label}
        {factor.display_value && (
          <span className="mono ml-1 text-xs text-text-tertiary">{factor.display_value}</span>
        )}
      </div>
      <div className="flex flex-1 items-center gap-2">
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-border">
          <div
            className={`h-full rounded-full ${up ? "bg-risk-high" : "bg-risk-low"}`}
            style={{ width: `${width}%` }}
          />
        </div>
        <span
          className={`flex items-center gap-0.5 text-xs font-medium ${
            up ? "text-risk-high" : "text-risk-low"
          }`}
        >
          {up ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}
          {up ? "raises" : "lowers"}
        </span>
      </div>
    </div>
  );
}

function ReferralModal({ screeningId, onClose }: { screeningId: string; onClose: () => void }) {
  const [referTo, setReferTo] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      dashboardApi.createReferral({ screening_id: screeningId, refer_to: referTo, note }),
    onSuccess: onClose,
    onError: (e) => setError(apiError(e)),
  });

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-text-primary/40 px-6 backdrop-blur-sm"
      onClick={onClose}
    >
      <FadeIn className="w-full max-w-md" y={20}>
        <div className="card" onClick={(e) => e.stopPropagation()}>
          <h2 className="text-lg font-semibold text-text-primary">Log a referral</h2>
          <div className="mt-4 space-y-3">
            <div>
              <label className="label">Refer to</label>
              <input
                className="input"
                placeholder="e.g. District Hospital"
                autoFocus
                value={referTo}
                onChange={(e) => setReferTo(e.target.value)}
              />
            </div>
            <div>
              <label className="label">Note</label>
              <textarea
                className="input"
                rows={3}
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
            </div>
            {error && <ErrorNote message={error} />}
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <button className="btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button className="btn-primary" onClick={() => create.mutate()} disabled={create.isPending}>
              {create.isPending && <Loader2 size={16} className="animate-spin" />}
              Save referral
            </button>
          </div>
        </div>
      </FadeIn>
    </div>
  );
}
