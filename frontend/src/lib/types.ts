// Types mirror the backend Pydantic schemas (backend/app/models/schemas.py).
// Kept in sync by hand; the OpenAPI spec at /openapi.json is the source of
// truth if they ever drift.

export type UserRole = "patient" | "health_worker" | "admin";
export type RiskBand = "low" | "moderate" | "high";
export type Modality = "clinical" | "pcg" | "ecg";
export type Sex = "female" | "male";
export type ScreeningStatus = "draft" | "ready" | "analyzed" | "reviewed";

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
}

export interface PatientSummary {
  id: string;
  full_name: string;
  sex: Sex | null;
  age_years: number | null;
  village_or_area: string | null;
  screening_count: number;
  latest_risk_band: RiskBand | null;
  latest_score: number | null;
  latest_screening_at: string | null;
  latest_screening_id: string | null;
}

export interface PatientOut {
  id: string;
  full_name: string;
  contact: string | null;
  sex: Sex | null;
  age_years: number | null;
  village_or_area: string | null;
  created_at: string;
}

export interface ScreeningHistoryItem {
  id: string;
  created_at: string;
  status: ScreeningStatus;
  risk_band: RiskBand | null;
  final_score: number | null;
  modalities_used: Modality[];
}

export interface PatientDetail {
  patient: PatientOut;
  screenings: ScreeningHistoryItem[];
}

export interface ClinicalInput {
  age: number;
  sex: number;
  cp: number;
  trestbps: number;
  chol: number;
  fbs: number;
  restecg: number;
  thalach: number;
  exang: number;
  oldpeak: number;
  slope: number;
  ca: number;
  thal: number;
}

export interface ExplanationFactor {
  feature: string;
  label: string;
  value: number | string | null;
  display_value: string | null;
  direction: "increases_risk" | "decreases_risk";
  magnitude: number;
}

export interface ExplanationOut {
  method: string;
  base_value: number | null;
  top_factors: ExplanationFactor[];
}

export interface PredictionOut {
  modality: Modality;
  model_version: string;
  score: number;
  confidence: number;
  threshold: number | null;
  explanation: ExplanationOut | null;
}

export interface ScreeningResult {
  screening_id: string;
  patient_id: string;
  status: ScreeningStatus;
  created_at: string;
  final_score: number;
  risk_band: RiskBand;
  confidence: number;
  modalities_used: Modality[];
  weights: Record<string, number>;
  recommendation: string;
  uncertainty_note: string;
  fusion_version: string;
  per_modality: PredictionOut[];
  disclaimer: string;
}

export interface ScreeningOut {
  id: string;
  patient_id: string;
  status: ScreeningStatus;
  created_at: string;
}

export interface DashboardStats {
  total_patients: number;
  total_screenings: number;
  high_risk: number;
  moderate_risk: number;
  low_risk: number;
  pending_review: number;
  multimodal_screenings: number;
}

export interface DashboardQueue {
  stats: DashboardStats;
  queue: PatientSummary[];
}

export interface ReferralOut {
  id: string;
  screening_id: string;
  status: string;
  refer_to: string | null;
  note: string | null;
  created_at: string;
}

export interface ModalityStatus {
  available: boolean;
  model_version: string | null;
  reason: string | null;
  signal_pipeline?: boolean;
  explainability: string | null;
}

export interface SystemModels {
  modalities: Record<Modality, ModalityStatus>;
  active_modalities: Modality[];
  fusion: {
    version: string;
    strategy: string;
    base_weights: Record<string, number>;
    note: string;
  };
  disclaimer: string;
}

export interface UploadResult {
  screening_id: string;
  duration_seconds: number;
  sample_rate: number;
  usable: boolean;
  quality_note: string;
  model_available: boolean;
  note: string;
  estimated_heart_rate_bpm?: number | null;
  rhythm?: Record<string, unknown>;
  lead_name?: string;
}

export interface ExtractedFieldInfo {
  value: number;
  confidence: number;
  source_text: string;
}

export interface ReportExtraction {
  engine: string;
  engine_available: boolean;
  engine_note: string;
  elapsed_ms: number;
  extracted: Record<string, ExtractedFieldInfo>;
  fields: Record<string, { value: number | null; matched: boolean; source_value: string }>;
  missing_fields: string[];
  found_count: number;
  raw_text_preview: string;
}

export interface TrendsData {
  risk_distribution: { band: RiskBand; count: number }[];
  daily: { date: string; screenings: number; high: number }[];
  recent: {
    screening_id: string;
    patient_id: string;
    patient_name: string;
    risk_band: RiskBand;
    score: number;
    created_at: string;
  }[];
}

export interface InsightsData {
  total: number;
  risk_factors: { factor: string; prevalence: number }[];
  by_age_band: { band: string; count: number; high: number; moderate: number; low: number }[];
  avg_by_band: {
    band: RiskBand;
    count: number;
    avg_age: number;
    avg_bp: number;
    avg_chol: number;
    avg_max_hr: number;
  }[];
}

export interface ModelCard {
  available: boolean;
  reason?: string;
  model: {
    modality: string;
    version: string;
    algorithm: string;
    calibrated: boolean;
    decision_threshold: number;
    threshold_policy: string;
    created_at: string;
  };
  metrics: {
    roc_auc: number;
    sensitivity: number;
    specificity: number;
    precision: number;
    recall: number;
    f1: number;
    accuracy: number;
    brier_score: number;
    confusion_matrix: {
      true_negative: number;
      false_positive: number;
      false_negative: number;
      true_positive: number;
    };
  };
  metrics_at_0_5: Record<string, number>;
  calibration_curve: { predicted: number; observed: number }[];
  cv_comparison: Record<string, { roc_auc_mean: number; roc_auc_std: number; recall_mean: number }>;
  data: {
    source_file: string;
    rows_used: number;
    duplicates_dropped: number;
    class_balance: { at_risk_1: number; not_at_risk_0: number };
    label_note: string;
  };
  feature_importances: { feature: string; label: string; importance: number }[];
  subgroup_check: Record<string, { n: number; recall?: number; precision?: number; roc_auc?: number }>;
  eval_note: string;
  fusion: { version: string; base_weights: Record<string, number> };
}
