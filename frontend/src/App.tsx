import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { authApi } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { AppLayout } from "@/components/AppLayout";
import { Spinner } from "@/components/ui";
import { MarketingPage } from "@/marketing/MarketingPage";
import { LoginPage } from "@/pages/LoginPage";
import { RegisterPage } from "@/pages/RegisterPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { PatientDetailPage } from "@/pages/PatientDetailPage";
import { NewScreeningPage } from "@/pages/NewScreeningPage";
import { ResultPage } from "@/pages/ResultPage";
import { InsightsPage } from "@/pages/InsightsPage";
import { MethodologyPage } from "@/pages/MethodologyPage";
import { ReferencePage } from "@/pages/ReferencePage";
import { ReferralsPage } from "@/pages/ReferralsPage";

function RequireAuth({ children }: { children: JSX.Element }) {
  const token = useAuthStore((s) => s.accessToken);
  const location = useLocation();
  if (!token) return <Navigate to="/login" state={{ from: location }} replace />;
  return children;
}

export default function App() {
  const { accessToken, user, setUser, clear } = useAuthStore();

  // Rehydrate the current user when a token exists but the user object doesn't
  // (e.g. after a page reload). A 401 here means the token is stale.
  const { isLoading } = useQuery({
    queryKey: ["me"],
    queryFn: authApi.me,
    enabled: !!accessToken && !user,
    retry: false,
  });

  useEffect(() => {
    if (!accessToken) return;
    authApi
      .me()
      .then(setUser)
      .catch(() => clear());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken]);

  if (accessToken && !user && isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner label="Loading…" />
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/" element={<MarketingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/insights" element={<InsightsPage />} />
        <Route path="/referrals" element={<ReferralsPage />} />
        <Route path="/methodology" element={<MethodologyPage />} />
        <Route path="/reference" element={<ReferencePage />} />
        <Route path="/patients/:id" element={<PatientDetailPage />} />
        <Route path="/screening/new/:patientId" element={<NewScreeningPage />} />
        <Route path="/screening/:id/result" element={<ResultPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
