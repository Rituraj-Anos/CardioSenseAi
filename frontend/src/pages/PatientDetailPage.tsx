import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, Stethoscope, MapPin, Phone, Calendar, Plus } from "lucide-react";
import { apiError, screeningApi, patientApi } from "@/lib/api";
import {
  Card,
  EmptyState,
  ErrorNote,
  FadeIn,
  Skeleton,
  Stagger,
  StaggerItem,
} from "@/components/ui";
import { RiskBadge } from "@/components/RiskBadge";
import type { ScreeningHistoryItem } from "@/lib/types";

export function PatientDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const { data, isLoading, error } = useQuery({
    queryKey: ["patient", id],
    queryFn: () => patientApi.detail(id!),
  });

  const startScreening = useMutation({
    mutationFn: async () => (await screeningApi.create(id!)).id,
    onSuccess: (screeningId) => navigate(`/screening/new/${id}?screening=${screeningId}`),
  });

  if (isLoading)
    return (
      <div className="mx-auto max-w-3xl space-y-5">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-28" />
        <Skeleton className="h-40" />
      </div>
    );
  if (error) return <ErrorNote message={apiError(error)} />;

  const { patient, screenings } = data!;
  const meta = [
    patient.sex && { icon: <span className="capitalize">{patient.sex}</span> },
    patient.age_years && { icon: <Calendar size={13} />, text: `${patient.age_years} yrs` },
    patient.village_or_area && { icon: <MapPin size={13} />, text: patient.village_or_area },
    patient.contact && { icon: <Phone size={13} />, text: patient.contact },
  ].filter(Boolean) as { icon: React.ReactNode; text?: string }[];

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <FadeIn>
        <Link to="/dashboard" className="btn-ghost -ml-2 py-1.5 text-sm">
          <ArrowLeft size={16} /> Dashboard
        </Link>
      </FadeIn>

      <FadeIn delay={0.05}>
        <Card>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex items-center gap-4">
              <span className="grid h-14 w-14 place-items-center rounded-full bg-primary-soft text-lg font-bold text-primary">
                {patient.full_name.split(" ").map((s) => s[0]).slice(0, 2).join("")}
              </span>
              <div>
                <h1 className="text-2xl font-bold text-text-primary">{patient.full_name}</h1>
                <div className="mt-1 flex flex-wrap items-center gap-3 text-sm text-text-secondary">
                  {meta.map((m, i) => (
                    <span key={i} className="flex items-center gap-1">
                      {m.icon}
                      {m.text}
                    </span>
                  ))}
                </div>
              </div>
            </div>
            <button
              className="btn-primary"
              onClick={() => startScreening.mutate()}
              disabled={startScreening.isPending}
            >
              <Plus size={16} /> New screening
            </button>
          </div>
        </Card>
      </FadeIn>

      <FadeIn delay={0.1}>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-text-secondary">
          Screening history
        </h2>
        {screenings.length === 0 ? (
          <EmptyState
            icon={<Stethoscope size={26} />}
            title="No screenings yet"
            hint="Run this patient's first screening to see results here."
          />
        ) : (
          <Stagger className="space-y-2">
            {screenings.map((s) => (
              <StaggerItem key={s.id}>
                <HistoryRow item={s} />
              </StaggerItem>
            ))}
          </Stagger>
        )}
      </FadeIn>
    </div>
  );
}

function HistoryRow({ item }: { item: ScreeningHistoryItem }) {
  const date = new Date(item.created_at).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
  const clickable = !!item.risk_band;
  const content = (
    <div
      className={`flex items-center justify-between rounded-card border border-border bg-surface px-5 py-3.5 ${
        clickable ? "transition-all hover:border-primary/30 hover:shadow-card-hover" : "opacity-80"
      }`}
    >
      <div>
        <p className="text-sm font-medium text-text-primary">{date}</p>
        <p className="text-xs text-text-tertiary">
          {item.modalities_used.length > 0
            ? `Modalities: ${item.modalities_used.join(", ")}`
            : `Status: ${item.status}`}
        </p>
      </div>
      <div className="flex items-center gap-3">
        {item.risk_band ? (
          <>
            <RiskBadge band={item.risk_band} size="sm" />
            {item.final_score != null && (
              <span className="mono text-sm text-text-secondary">
                {Math.round(item.final_score * 100)}%
              </span>
            )}
          </>
        ) : (
          <span className="text-xs text-text-tertiary">Not analysed</span>
        )}
      </div>
    </div>
  );
  return clickable ? <Link to={`/screening/${item.id}/result`}>{content}</Link> : content;
}
