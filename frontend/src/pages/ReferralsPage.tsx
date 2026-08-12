import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Send } from "lucide-react";
import { apiError, dashboardApi } from "@/lib/api";
import { Card, EmptyState, ErrorNote, FadeIn, Skeleton, Stagger, StaggerItem } from "@/components/ui";

const STATUS_STYLE: Record<string, string> = {
  pending: "bg-risk-moderate/10 text-risk-moderate",
  accepted: "bg-primary-soft text-primary",
  completed: "bg-risk-low/10 text-risk-low",
  cancelled: "bg-border text-text-tertiary",
};

export function ReferralsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["referrals"],
    queryFn: dashboardApi.listReferrals,
  });

  if (isLoading)
    return (
      <div className="space-y-4">
        <Skeleton className="h-9 w-48" />
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-16" />
        ))}
      </div>
    );
  if (error) return <ErrorNote message={apiError(error)} />;
  const referrals = data!;

  return (
    <div className="space-y-6">
      <FadeIn>
        <h1 className="text-2xl font-bold text-text-primary">Referrals</h1>
        <p className="mt-1 text-sm text-text-secondary">
          Patients routed onward for clinical assessment.
        </p>
      </FadeIn>

      {referrals.length === 0 ? (
        <EmptyState
          icon={<Send size={26} />}
          title="No referrals yet"
          hint="Log a referral from any screening result to track it here."
        />
      ) : (
        <Stagger className="space-y-2">
          {referrals.map((r) => (
            <StaggerItem key={r.id}>
              <Card className="flex items-center justify-between !py-4">
                <div>
                  <p className="font-medium text-text-primary">{r.refer_to ?? "Referral"}</p>
                  {r.note && <p className="mt-0.5 text-sm text-text-secondary">{r.note}</p>}
                  <p className="mt-0.5 text-xs text-text-tertiary">
                    {new Date(r.created_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`chip capitalize ${STATUS_STYLE[r.status] ?? ""}`}>{r.status}</span>
                  <Link
                    to={`/screening/${r.screening_id}/result`}
                    className="btn-secondary py-1.5 text-xs"
                  >
                    View screening
                  </Link>
                </div>
              </Card>
            </StaggerItem>
          ))}
        </Stagger>
      )}
    </div>
  );
}
