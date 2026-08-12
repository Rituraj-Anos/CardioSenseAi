import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { TrendingUp, Users } from "lucide-react";
import { apiError, dashboardApi } from "@/lib/api";
import { Card, EmptyState, ErrorNote, FadeIn, Skeleton } from "@/components/ui";

const BAND_COLORS: Record<string, string> = {
  low: "#12866F",
  moderate: "#B54708",
  high: "#B42318",
};

export function InsightsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["insights"],
    queryFn: dashboardApi.insights,
  });

  if (isLoading)
    return (
      <div className="space-y-6">
        <Skeleton className="h-9 w-56" />
        <div className="grid gap-5 lg:grid-cols-2">
          <Skeleton className="h-80" />
          <Skeleton className="h-80" />
        </div>
      </div>
    );
  if (error) return <ErrorNote message={apiError(error)} />;

  const d = data!;

  if (d.total === 0)
    return (
      <div className="space-y-6">
        <Header />
        <EmptyState
          icon={<TrendingUp size={28} />}
          title="No analysed screenings yet"
          hint="Run a few screenings and cohort insights will appear here."
        />
      </div>
    );

  return (
    <div className="space-y-8">
      <Header total={d.total} />

      <div className="grid gap-5 lg:grid-cols-2">
        <FadeIn>
          <Card className="h-full">
            <h2 className="text-sm font-semibold text-text-primary">Risk-factor prevalence</h2>
            <p className="text-xs text-text-secondary">
              Share of screenings in this cohort showing each factor.
            </p>
            <div className="mt-4 space-y-3">
              {d.risk_factors.map((f) => (
                <div key={f.factor}>
                  <div className="flex justify-between text-sm">
                    <span className="text-text-primary">{f.factor}</span>
                    <span className="mono font-semibold text-text-primary">{f.prevalence}%</span>
                  </div>
                  <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-border">
                    <div
                      className="h-full rounded-full bg-primary-gradient"
                      style={{ width: `${f.prevalence}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </FadeIn>

        <FadeIn delay={0.05}>
          <Card className="h-full">
            <h2 className="text-sm font-semibold text-text-primary">Risk by age band</h2>
            <p className="text-xs text-text-secondary">Screening outcomes across age groups.</p>
            <div className="mt-4 h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={d.by_age_band}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#EEF2F1" vertical={false} />
                  <XAxis dataKey="band" tick={{ fontSize: 12, fill: "#475467" }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "#98A2B3" }} axisLine={false} tickLine={false} allowDecimals={false} />
                  <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #E4E7EC", fontSize: 12 }} />
                  <Bar dataKey="low" stackId="a" fill={BAND_COLORS.low} radius={[0, 0, 0, 0]} name="Low" />
                  <Bar dataKey="moderate" stackId="a" fill={BAND_COLORS.moderate} name="Moderate" />
                  <Bar dataKey="high" stackId="a" fill={BAND_COLORS.high} radius={[4, 4, 0, 0]} name="High" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </FadeIn>
      </div>

      <FadeIn delay={0.1}>
        <Card>
          <h2 className="text-sm font-semibold text-text-primary">Average clinical values by risk band</h2>
          <p className="text-xs text-text-secondary">
            The inputs separate cleanly by outcome — a sanity check that the model keys on
            clinically meaningful signal.
          </p>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-text-tertiary">
                  <th className="pb-2 font-medium">Risk band</th>
                  <th className="pb-2 font-medium">Screenings</th>
                  <th className="pb-2 font-medium">Avg age</th>
                  <th className="pb-2 font-medium">Avg BP</th>
                  <th className="pb-2 font-medium">Avg cholesterol</th>
                  <th className="pb-2 font-medium">Avg peak HR</th>
                </tr>
              </thead>
              <tbody>
                {d.avg_by_band.map((r) => (
                  <tr key={r.band} className="border-b border-border/60">
                    <td className="py-2.5">
                      <span
                        className="chip"
                        style={{ background: `${BAND_COLORS[r.band]}1a`, color: BAND_COLORS[r.band] }}
                      >
                        {r.band}
                      </span>
                    </td>
                    <td className="mono py-2.5">{r.count}</td>
                    <td className="mono py-2.5">{r.avg_age}</td>
                    <td className="mono py-2.5">{r.avg_bp} mm Hg</td>
                    <td className="mono py-2.5">{r.avg_chol} mg/dl</td>
                    <td className="mono py-2.5">{r.avg_max_hr} bpm</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </FadeIn>
    </div>
  );
}

function Header({ total }: { total?: number }) {
  return (
    <FadeIn className="flex items-center justify-between">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Population insights</h1>
        <p className="mt-1 text-sm text-text-secondary">
          Aggregate patterns across your screened patients.
        </p>
      </div>
      {total != null && (
        <span className="chip bg-primary-soft text-primary">
          <Users size={13} /> {total} analysed screenings
        </span>
      )}
    </FadeIn>
  );
}
