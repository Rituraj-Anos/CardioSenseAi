import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { FlaskConical, GitBranch, Layers, ShieldAlert } from "lucide-react";
import { apiError, dashboardApi } from "@/lib/api";
import { Card, ErrorNote, FadeIn, Skeleton } from "@/components/ui";

export function MethodologyPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["model-card"],
    queryFn: dashboardApi.modelCard,
  });

  if (isLoading)
    return (
      <div className="space-y-6">
        <Skeleton className="h-9 w-64" />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
        <Skeleton className="h-72" />
      </div>
    );
  if (error) return <ErrorNote message={apiError(error)} />;
  const c = data!;
  if (!c.available) return <ErrorNote message={c.reason ?? "No model available."} />;

  const pct = (v: number) => `${Math.round(v * 100)}%`;

  return (
    <div className="space-y-8">
      <FadeIn>
        <h1 className="text-2xl font-bold text-text-primary">Model & methodology</h1>
        <p className="mt-1 max-w-2xl text-sm text-text-secondary">
          The clinical risk model, evaluated honestly. Every figure below is read directly from the
          trained model's manifest — the numbers it was actually measured at on a held-out test
          split, not inherited or rounded up.
        </p>
      </FadeIn>

      {/* Headline metrics */}
      <FadeIn delay={0.05} className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="ROC-AUC" value={c.metrics.roc_auc?.toFixed(3)} tone="primary" hint="Ranking quality" />
        <Metric label="Sensitivity" value={pct(c.metrics.sensitivity)} tone="good" hint="Sick patients caught" />
        <Metric label="Specificity" value={pct(c.metrics.specificity)} tone="neutral" hint="Healthy ruled out" />
        <Metric label="Brier score" value={c.metrics.brier_score?.toFixed(3)} tone="neutral" hint="Lower = better calibrated" />
      </FadeIn>

      <div className="grid gap-5 lg:grid-cols-2">
        {/* Model summary */}
        <FadeIn delay={0.1}>
          <Card className="h-full">
            <div className="flex items-center gap-2">
              <FlaskConical size={16} className="text-primary" />
              <h2 className="text-sm font-semibold text-text-primary">Selected model</h2>
            </div>
            <dl className="mt-4 space-y-2.5 text-sm">
              <Row k="Algorithm" v={c.model.algorithm} />
              <Row k="Version" v={c.model.version} />
              <Row k="Calibrated" v={c.model.calibrated ? "Yes" : "No (kept better of the two)"} />
              <Row k="Operating threshold" v={String(c.model.decision_threshold)} />
              <Row k="Dataset" v={`${c.data.rows_used} rows (${c.data.duplicates_dropped} duplicate dropped)`} />
              <Row k="Class balance" v={`${c.data.class_balance.at_risk_1} at-risk / ${c.data.class_balance.not_at_risk_0} not`} />
            </dl>
            <p className="mt-4 rounded-control bg-primary-soft/60 px-3 py-2 text-xs leading-relaxed text-text-secondary">
              {c.model.threshold_policy}
            </p>
          </Card>
        </FadeIn>

        {/* Confusion matrix */}
        <FadeIn delay={0.15}>
          <Card className="h-full">
            <div className="flex items-center gap-2">
              <Layers size={16} className="text-primary" />
              <h2 className="text-sm font-semibold text-text-primary">Confusion matrix</h2>
            </div>
            <p className="text-xs text-text-secondary">Held-out test split, at the operating threshold.</p>
            <ConfusionMatrix cm={c.metrics.confusion_matrix} />
          </Card>
        </FadeIn>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        {/* Calibration */}
        <FadeIn delay={0.1}>
          <Card className="h-full">
            <h2 className="text-sm font-semibold text-text-primary">Calibration curve</h2>
            <p className="text-xs text-text-secondary">
              Predicted probability vs observed frequency — closer to the diagonal is better.
            </p>
            <div className="mt-4 h-60">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={c.calibration_curve} margin={{ top: 8, right: 12, bottom: 4, left: -12 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#EEF2F1" />
                  <XAxis type="number" dataKey="predicted" domain={[0, 1]} tick={{ fontSize: 11, fill: "#98A2B3" }} axisLine={false} tickLine={false} />
                  <YAxis type="number" domain={[0, 1]} tick={{ fontSize: 11, fill: "#98A2B3" }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #E4E7EC", fontSize: 12 }} />
                  <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke="#98A2B3" strokeDasharray="4 4" />
                  <Line type="monotone" dataKey="observed" stroke="#0E6E64" strokeWidth={2} dot={{ r: 3 }} name="Observed" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </FadeIn>

        {/* Feature importances */}
        <FadeIn delay={0.15}>
          <Card className="h-full">
            <h2 className="text-sm font-semibold text-text-primary">What drives the model</h2>
            <p className="text-xs text-text-secondary">Global feature importance across all predictions.</p>
            <div className="mt-4 h-60">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={c.feature_importances.slice(0, 8)}
                  layout="vertical"
                  margin={{ left: 20, right: 16, top: 4, bottom: 4 }}
                >
                  <XAxis type="number" hide />
                  <YAxis
                    type="category"
                    dataKey="label"
                    width={140}
                    tick={{ fontSize: 11, fill: "#475467" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #E4E7EC", fontSize: 12 }} />
                  <Bar dataKey="importance" fill="#0E6E64" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </FadeIn>
      </div>

      {/* Model comparison */}
      <FadeIn delay={0.1}>
        <Card>
          <div className="flex items-center gap-2">
            <GitBranch size={16} className="text-primary" />
            <h2 className="text-sm font-semibold text-text-primary">Candidate comparison (5-fold CV)</h2>
          </div>
          <p className="text-xs text-text-secondary">
            Three models were compared on the training split; the best ROC-AUC won — not assumed.
          </p>
          <div className="mt-4 space-y-3">
            {Object.entries(c.cv_comparison).map(([name, m]) => (
              <div key={name}>
                <div className="flex justify-between text-sm">
                  <span className="text-text-primary capitalize">
                    {name.replace(/_/g, " ")}
                    {name === c.model.algorithm && (
                      <span className="chip ml-2 bg-primary-soft text-primary">selected</span>
                    )}
                  </span>
                  <span className="mono text-text-secondary">
                    AUC {m.roc_auc_mean.toFixed(3)} ± {m.roc_auc_std.toFixed(3)}
                  </span>
                </div>
                <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-border">
                  <div
                    className={`h-full rounded-full ${name === c.model.algorithm ? "bg-primary-gradient" : "bg-text-tertiary"}`}
                    style={{ width: `${m.roc_auc_mean * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </Card>
      </FadeIn>

      {/* Scope & limitations */}
      <FadeIn delay={0.15}>
        <Card className="border-primary/20 bg-primary-soft/[0.15]">
          <div className="flex items-center gap-2">
            <ShieldAlert size={16} className="text-primary" />
            <h2 className="text-sm font-semibold text-text-primary">Scope & limitations</h2>
          </div>
          <ul className="mt-3 space-y-2 text-sm leading-relaxed text-text-secondary">
            <li>
              • CardioSense is a <span className="font-medium text-text-primary">screening aid</span>,
              not a diagnostic tool. Every result is a probability with stated confidence, meant to
              prompt clinical follow-up — not to replace it.
            </li>
            <li>
              • The model is tuned to prioritise <span className="font-medium text-text-primary">
              sensitivity</span> (catching at-risk patients). This intentionally accepts more false
              positives so that fewer high-risk patients are missed.
            </li>
            <li>
              • Absolute risk estimates should be locally validated before a new deployment
              population, as risk baselines vary across regions and demographics.
            </li>
            <li>
              • Predictions reflect the data entered. Incomplete or inaccurate inputs reduce
              reliability — which is why every field is reviewable before analysis.
            </li>
          </ul>
        </Card>
      </FadeIn>
    </div>
  );
}

function Metric({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value?: string;
  hint: string;
  tone: "primary" | "good" | "neutral";
}) {
  const color =
    tone === "good" ? "text-risk-low" : tone === "primary" ? "text-primary" : "text-text-primary";
  return (
    <div className="card !p-4">
      <div className={`stat-value ${color}`}>{value ?? "—"}</div>
      <div className="mt-1 text-sm font-medium text-text-primary">{label}</div>
      <div className="text-xs text-text-tertiary">{hint}</div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string | undefined }) {
  return (
    <div className="flex justify-between gap-4 border-b border-border/60 pb-2">
      <dt className="text-text-secondary">{k}</dt>
      <dd className="text-right font-medium text-text-primary">{v}</dd>
    </div>
  );
}

function ConfusionMatrix({
  cm,
}: {
  cm: { true_negative: number; false_positive: number; false_negative: number; true_positive: number };
}) {
  const cell = (label: string, value: number, good: boolean) => (
    <div
      className={`rounded-control p-4 text-center ${
        good ? "bg-risk-low/10 text-risk-low" : "bg-risk-high/10 text-risk-high"
      }`}
    >
      <div className="mono text-2xl font-bold">{value}</div>
      <div className="text-xs font-medium">{label}</div>
    </div>
  );
  return (
    <div className="mt-4 grid grid-cols-2 gap-2">
      {cell("True negative", cm.true_negative, true)}
      {cell("False positive", cm.false_positive, false)}
      {cell("False negative", cm.false_negative, false)}
      {cell("True positive", cm.true_positive, true)}
      <p className="col-span-2 mt-1 text-xs text-text-tertiary">
        False negatives (missed high-risk patients) are the costliest error for a screening tool —
        the threshold is set to keep this box small.
      </p>
    </div>
  );
}
