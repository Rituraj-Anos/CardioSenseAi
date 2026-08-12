import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/auth";
import {
  Users,
  Stethoscope,
  TriangleAlert,
  ClipboardCheck,
  Layers,
  Plus,
  ArrowRight,
  UserPlus,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
} from "recharts";
import { apiError, dashboardApi, patientApi, screeningApi } from "@/lib/api";
import {
  AnimatedNumber,
  Card,
  EmptyState,
  ErrorNote,
  FadeIn,
  Skeleton,
  Stagger,
  StaggerItem,
} from "@/components/ui";
import { RiskBadge } from "@/components/RiskBadge";
import type { DashboardStats, PatientSummary, RiskBand } from "@/lib/types";

const RISK_COLORS: Record<RiskBand, string> = {
  low: "#12866F",
  moderate: "#B54708",
  high: "#B42318",
};

export function DashboardPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showNew, setShowNew] = useState(false);

  const queue = useQuery({ queryKey: ["dashboard"], queryFn: dashboardApi.queue });
  const trends = useQuery({ queryKey: ["trends"], queryFn: dashboardApi.trends });

  const startScreening = useMutation({
    mutationFn: async (patientId: string) => {
      const screening = await screeningApi.create(patientId);
      return { patientId, screeningId: screening.id };
    },
    onSuccess: ({ patientId, screeningId }) =>
      navigate(`/screening/new/${patientId}?screening=${screeningId}`),
  });

  if (queue.isLoading) return <DashboardSkeleton />;
  if (queue.error) return <ErrorNote message={apiError(queue.error)} />;

  const stats = queue.data!.stats;
  const rows = queue.data!.queue;

  return (
    <div className="space-y-8">
      <GreetingHero
        stats={stats}
        highRiskName={queue.data!.queue.find((p) => p.latest_risk_band === "high")?.full_name}
        onNew={() => setShowNew(true)}
      />

      <StatsRow stats={stats} />

      <div className="grid gap-5 lg:grid-cols-3">
        <FadeIn delay={0.1} className="lg:col-span-2">
          <Card className="h-full">
            <h2 className="text-sm font-semibold text-text-primary">Screening volume (30 days)</h2>
            <p className="text-xs text-text-secondary">Daily screenings, with high-risk overlaid.</p>
            <div className="mt-4 h-56">
              {trends.isLoading ? (
                <Skeleton className="h-full w-full" />
              ) : (
                <VolumeChart data={trends.data?.daily ?? []} />
              )}
            </div>
          </Card>
        </FadeIn>

        <FadeIn delay={0.15}>
          <Card className="h-full">
            <h2 className="text-sm font-semibold text-text-primary">Risk distribution</h2>
            <p className="text-xs text-text-secondary">Across all analysed screenings.</p>
            {trends.isLoading ? (
              <Skeleton className="mt-4 h-56 w-full" />
            ) : (
              <RiskDonut data={trends.data?.risk_distribution ?? []} />
            )}
          </Card>
        </FadeIn>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <FadeIn delay={0.2} className="lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-text-secondary">
              Triage queue
            </h2>
            <span className="text-xs text-text-tertiary">{rows.length} patients</span>
          </div>
          {rows.length === 0 ? (
            <EmptyState
              icon={<Users size={28} />}
              title="No patients yet"
              hint="Add a patient to run their first screening."
              action={
                <button className="btn-primary" onClick={() => setShowNew(true)}>
                  <Plus size={16} /> Add patient
                </button>
              }
            />
          ) : (
            <Stagger className="space-y-2">
              {rows.map((p) => (
                <StaggerItem key={p.id}>
                  <QueueRow
                    patient={p}
                    onScreen={() => startScreening.mutate(p.id)}
                    busy={startScreening.isPending}
                  />
                </StaggerItem>
              ))}
            </Stagger>
          )}
        </FadeIn>

        <FadeIn delay={0.25}>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-text-secondary">
            Recent activity
          </h2>
          <Card className="!p-3">
            {trends.isLoading ? (
              <div className="space-y-2">
                {[0, 1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : trends.data && trends.data.recent.length > 0 ? (
              <ul className="divide-y divide-border">
                {trends.data.recent.map((a) => (
                  <li key={a.screening_id}>
                    <Link
                      to={`/screening/${a.screening_id}/result`}
                      className="flex items-center justify-between gap-2 rounded-control px-2 py-2.5 transition-colors hover:bg-primary-soft/40"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-text-primary">
                          {a.patient_name}
                        </p>
                        <p className="text-xs text-text-tertiary">
                          {new Date(a.created_at).toLocaleDateString()}
                        </p>
                      </div>
                      <RiskBadge band={a.risk_band} size="sm" />
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="px-2 py-8 text-center text-sm text-text-tertiary">No activity yet.</p>
            )}
          </Card>
        </FadeIn>
      </div>

      {showNew && (
        <NewPatientModal
          onClose={() => setShowNew(false)}
          onCreated={() => {
            queryClient.invalidateQueries({ queryKey: ["dashboard"] });
            queryClient.invalidateQueries({ queryKey: ["trends"] });
            setShowNew(false);
          }}
        />
      )}
    </div>
  );
}

function GreetingHero({
  stats,
  highRiskName,
  onNew,
}: {
  stats: DashboardStats;
  highRiskName?: string;
  onNew: () => void;
}) {
  const user = useAuthStore((s) => s.user);
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  const firstName = (user?.full_name ?? "there").split(" ")[0];
  const today = new Date().toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  });

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      className="relative overflow-hidden rounded-card bg-primary-gradient p-6 text-white shadow-card-hover sm:p-8"
    >
      {/* soft mesh glow */}
      <div className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-white/10 blur-2xl" />
      <div className="pointer-events-none absolute -bottom-20 right-24 h-48 w-48 rounded-full bg-white/5 blur-2xl" />
      <div className="relative flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-white/70">{today}</p>
          <h1 className="mt-1 text-2xl font-bold sm:text-3xl">
            {greeting}, {firstName}
          </h1>
          <p className="mt-2 max-w-lg text-sm text-white/80">
            {stats.high_risk > 0 ? (
              <>
                You have{" "}
                <span className="font-semibold text-white">{stats.high_risk} high-risk</span>{" "}
                {stats.high_risk === 1 ? "patient" : "patients"} in your queue
                {highRiskName ? `, including ${highRiskName}.` : "."} They're sorted to the top.
              </>
            ) : (
              <>Your triage queue is clear of high-risk patients. Keep up the routine screening.</>
            )}
          </p>
        </div>
        <button
          className="btn inline-flex items-center gap-2 rounded-control bg-white px-4 py-2.5 text-sm font-semibold text-primary shadow-sm hover:bg-white/90"
          onClick={onNew}
        >
          <UserPlus size={16} /> New patient
        </button>
      </div>
    </motion.div>
  );
}

function StatsRow({ stats }: { stats: DashboardStats }) {
  const items = [
    { label: "Patients", value: stats.total_patients, icon: <Users size={18} />, tint: "text-primary bg-primary-soft" },
    { label: "Screenings", value: stats.total_screenings, icon: <Stethoscope size={18} />, tint: "text-accent bg-accent/10" },
    { label: "High risk", value: stats.high_risk, icon: <TriangleAlert size={18} />, tint: "text-risk-high bg-risk-high/10" },
    { label: "Moderate", value: stats.moderate_risk, icon: <Layers size={18} />, tint: "text-risk-moderate bg-risk-moderate/10" },
    { label: "Awaiting review", value: stats.pending_review, icon: <ClipboardCheck size={18} />, tint: "text-primary bg-primary-soft" },
    { label: "Multimodal", value: stats.multimodal_screenings, icon: <Layers size={18} />, tint: "text-accent bg-accent/10" },
  ];
  return (
    <Stagger className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {items.map((i) => (
        <StaggerItem key={i.label}>
          <div className="card-interactive !p-4">
            <span className={`inline-grid h-9 w-9 place-items-center rounded-control ${i.tint}`}>
              {i.icon}
            </span>
            <div className="mt-3 stat-value text-text-primary">
              <AnimatedNumber value={i.value} />
            </div>
            <div className="mt-0.5 text-xs text-text-secondary">{i.label}</div>
          </div>
        </StaggerItem>
      ))}
    </Stagger>
  );
}

function VolumeChart({ data }: { data: { date: string; screenings: number; high: number }[] }) {
  if (data.length === 0)
    return (
      <div className="grid h-full place-items-center text-sm text-text-tertiary">
        No screenings in this window yet.
      </div>
    );
  const shaped = data.map((d) => ({
    ...d,
    label: new Date(d.date).toLocaleDateString(undefined, { month: "short", day: "numeric" }),
  }));
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={shaped} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="gScreen" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#0E6E64" stopOpacity={0.35} />
            <stop offset="100%" stopColor="#0E6E64" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="gHigh" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#B42318" stopOpacity={0.3} />
            <stop offset="100%" stopColor="#B42318" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#98A2B3" }} axisLine={false} tickLine={false} minTickGap={24} />
        <Tooltip
          contentStyle={{ borderRadius: 12, border: "1px solid #E4E7EC", fontSize: 12 }}
          labelStyle={{ color: "#475467" }}
        />
        <Area type="monotone" dataKey="screenings" stroke="#0E6E64" strokeWidth={2} fill="url(#gScreen)" name="Screenings" />
        <Area type="monotone" dataKey="high" stroke="#B42318" strokeWidth={2} fill="url(#gHigh)" name="High risk" />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function RiskDonut({ data }: { data: { band: RiskBand; count: number }[] }) {
  const total = data.reduce((s, d) => s + d.count, 0);
  if (total === 0)
    return (
      <div className="grid h-56 place-items-center text-sm text-text-tertiary">No data yet.</div>
    );
  return (
    <div className="relative mt-2">
      <ResponsiveContainer width="100%" height={200}>
        <PieChart>
          <Pie
            data={data}
            dataKey="count"
            nameKey="band"
            innerRadius={58}
            outerRadius={82}
            paddingAngle={3}
            startAngle={90}
            endAngle={-270}
          >
            {data.map((d) => (
              <Cell key={d.band} fill={RISK_COLORS[d.band]} />
            ))}
          </Pie>
          <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #E4E7EC", fontSize: 12 }} />
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <span className="mono text-2xl font-bold text-text-primary">{total}</span>
        <span className="text-xs text-text-tertiary">screenings</span>
      </div>
      <div className="mt-3 flex justify-center gap-4">
        {data.map((d) => (
          <div key={d.band} className="flex items-center gap-1.5 text-xs text-text-secondary">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: RISK_COLORS[d.band] }} />
            <span className="capitalize">{d.band}</span>
            <span className="mono font-semibold text-text-primary">{d.count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function QueueRow({
  patient,
  onScreen,
  busy,
}: {
  patient: PatientSummary;
  onScreen: () => void;
  busy: boolean;
}) {
  return (
    <div className="group flex items-center justify-between rounded-card border border-border bg-surface px-5 py-3.5 transition-all hover:border-primary/30 hover:shadow-card-hover">
      <Link to={`/patients/${patient.id}`} className="min-w-0 flex-1">
        <p className="font-semibold text-text-primary group-hover:text-primary">
          {patient.full_name}
        </p>
        <p className="text-xs text-text-secondary">
          {[
            patient.sex,
            patient.age_years ? `${patient.age_years} yrs` : null,
            patient.village_or_area,
            `${patient.screening_count} screening${patient.screening_count === 1 ? "" : "s"}`,
          ]
            .filter(Boolean)
            .join(" · ")}
        </p>
      </Link>
      <div className="flex items-center gap-4">
        {patient.latest_risk_band ? (
          <div className="flex items-center gap-3">
            <RiskBadge band={patient.latest_risk_band} size="sm" />
            {patient.latest_score != null && (
              <span className="mono hidden text-sm text-text-secondary sm:block">
                {Math.round(patient.latest_score * 100)}%
              </span>
            )}
          </div>
        ) : (
          <span className="text-xs text-text-tertiary">Not screened</span>
        )}
        <button className="btn-secondary py-1.5 text-xs" onClick={onScreen} disabled={busy}>
          Screen <ArrowRight size={14} />
        </button>
      </div>
    </div>
  );
}

function NewPatientModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({
    full_name: "",
    sex: "",
    age_years: "",
    village_or_area: "",
    contact: "",
  });
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      patientApi.create({
        full_name: form.full_name,
        sex: form.sex || undefined,
        age_years: form.age_years ? Number(form.age_years) : undefined,
        village_or_area: form.village_or_area || undefined,
        contact: form.contact || undefined,
      }),
    onSuccess: onCreated,
    onError: (e) => setError(apiError(e)),
  });

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-text-primary/40 px-6 backdrop-blur-sm"
      onClick={onClose}
    >
      <FadeIn className="w-full max-w-md" y={20}>
        <div className="card" onClick={(e) => e.stopPropagation()}>
          <h2 className="text-lg font-semibold text-text-primary">New patient</h2>
          <p className="mt-1 text-xs text-text-secondary">
            Identity is stored separately from clinical data.
          </p>
          <div className="mt-4 space-y-3">
            <div>
              <label className="label">Full name</label>
              <input
                className="input"
                autoFocus
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">Sex</label>
                <select
                  className="input"
                  value={form.sex}
                  onChange={(e) => setForm({ ...form, sex: e.target.value })}
                >
                  <option value="">—</option>
                  <option value="female">Female</option>
                  <option value="male">Male</option>
                </select>
              </div>
              <div>
                <label className="label">Age</label>
                <input
                  type="number"
                  className="input mono"
                  value={form.age_years}
                  onChange={(e) => setForm({ ...form, age_years: e.target.value })}
                />
              </div>
            </div>
            <div>
              <label className="label">Village / area</label>
              <input
                className="input"
                value={form.village_or_area}
                onChange={(e) => setForm({ ...form, village_or_area: e.target.value })}
              />
            </div>
            {error && <ErrorNote message={error} />}
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <button className="btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button
              className="btn-primary"
              onClick={() => create.mutate()}
              disabled={!form.full_name || create.isPending}
            >
              {create.isPending ? "Creating…" : "Create patient"}
            </button>
          </div>
        </div>
      </FadeIn>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-8">
      <Skeleton className="h-9 w-64" />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-28" />
        ))}
      </div>
      <div className="grid gap-5 lg:grid-cols-3">
        <Skeleton className="h-72 lg:col-span-2" />
        <Skeleton className="h-72" />
      </div>
    </div>
  );
}
