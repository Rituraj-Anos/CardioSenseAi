import axios, { AxiosError } from "axios";
import { useAuthStore } from "@/store/auth";
import type {
  ClinicalInput,
  DashboardQueue,
  InsightsData,
  ModelCard,
  PatientDetail,
  PatientSummary,
  ReferralOut,
  ReportExtraction,
  ScreeningOut,
  ScreeningResult,
  SystemModels,
  TokenResponse,
  TrendsData,
  UploadResult,
  User,
} from "./types";

const API = "/api/v1";

export const http = axios.create({
  baseURL: API,
  withCredentials: true, // send the httpOnly refresh cookie
});

// Attach the access token to every request.
http.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// On a 401, try one silent refresh, then replay the original request. If the
// refresh also fails, log out — this keeps a health worker from being kicked to
// the login screen every 15 minutes when the access token expires.
let refreshing: Promise<string | null> | null = null;

http.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original = error.config;
    const status = error.response?.status;

    if (status === 401 && original && !(original as any)._retried) {
      (original as any)._retried = true;
      try {
        refreshing = refreshing ?? doRefresh();
        const token = await refreshing;
        refreshing = null;
        if (token) {
          original.headers = original.headers ?? {};
          original.headers.Authorization = `Bearer ${token}`;
          return http(original);
        }
      } catch {
        refreshing = null;
      }
      useAuthStore.getState().clear();
    }
    return Promise.reject(error);
  }
);

async function doRefresh(): Promise<string | null> {
  try {
    const { data } = await axios.post<TokenResponse>(
      `${API}/auth/refresh`,
      {},
      { withCredentials: true }
    );
    useAuthStore.getState().setToken(data.access_token);
    return data.access_token;
  } catch {
    return null;
  }
}

/** Extract a human-readable message from a FastAPI error response. */
export function apiError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      // Pydantic 422 validation errors.
      return detail
        .map((d: any) => {
          const field = Array.isArray(d.loc) ? d.loc.slice(1).join(".") : "";
          return field ? `${field}: ${d.msg}` : d.msg;
        })
        .join("; ");
    }
    if (error.code === "ERR_NETWORK") return "Cannot reach the server. Is the backend running?";
  }
  return "Something went wrong. Please try again.";
}

// ---- Auth ----
export interface PasswordCheck {
  ok: boolean;
  score: number;
  errors: string[];
}

export const authApi = {
  register: (body: {
    email: string;
    password: string;
    full_name: string;
    role: "health_worker" | "patient";
  }) => http.post<User>("/auth/register", body).then((r) => r.data),
  login: (body: { email: string; password: string }) =>
    http.post<TokenResponse>("/auth/login", body).then((r) => r.data),
  me: () => http.get<User>("/auth/me").then((r) => r.data),
  logout: () => http.post("/auth/logout"),
  checkPassword: (password: string, email?: string) =>
    http.post<PasswordCheck>("/auth/check-password", { password, email }).then((r) => r.data),
};

// ---- Patients ----
export const patientApi = {
  list: (search?: string) =>
    http
      .get<PatientSummary[]>("/patients", { params: search ? { search } : {} })
      .then((r) => r.data),
  create: (body: {
    full_name: string;
    contact?: string;
    sex?: string;
    age_years?: number;
    village_or_area?: string;
  }) => http.post("/patients", body).then((r) => r.data),
  detail: (id: string) => http.get<PatientDetail>(`/patients/${id}`).then((r) => r.data),
};

// ---- Screenings ----
export const screeningApi = {
  create: (patient_id: string) =>
    http.post<ScreeningOut>("/screenings", { patient_id }).then((r) => r.data),
  submitClinical: (id: string, body: ClinicalInput) =>
    http.post<ScreeningOut>(`/screenings/${id}/clinical`, body).then((r) => r.data),
  uploadPcg: (id: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return http
      .post<UploadResult>(`/screenings/${id}/pcg`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },
  uploadEcg: (id: string, file: File, sampleRate?: number) => {
    const fd = new FormData();
    fd.append("file", file);
    if (sampleRate) fd.append("sample_rate", String(sampleRate));
    return http
      .post<UploadResult>(`/screenings/${id}/ecg`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },
  extractReport: (id: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return http
      .post<ReportExtraction>(`/screenings/${id}/extract-report`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },
  analyze: (id: string) =>
    http.post<ScreeningResult>(`/screenings/${id}/analyze`).then((r) => r.data),
  result: (id: string) =>
    http.get<ScreeningResult>(`/screenings/${id}/result`).then((r) => r.data),
  review: (id: string) => http.post<ScreeningOut>(`/screenings/${id}/review`).then((r) => r.data),
};

// ---- Dashboard / referrals / system ----
export const dashboardApi = {
  queue: () => http.get<DashboardQueue>("/dashboard/queue").then((r) => r.data),
  trends: () => http.get<TrendsData>("/dashboard/trends").then((r) => r.data),
  insights: () => http.get<InsightsData>("/dashboard/insights").then((r) => r.data),
  createReferral: (body: { screening_id: string; refer_to?: string; note?: string }) =>
    http.post<ReferralOut>("/referrals", body).then((r) => r.data),
  systemModels: () => http.get<SystemModels>("/system/models").then((r) => r.data),
  modelCard: () => http.get<ModelCard>("/system/model-card").then((r) => r.data),
  listReferrals: () => http.get<ReferralOut[]>("/referrals").then((r) => r.data),
};
