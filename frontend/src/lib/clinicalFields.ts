// Clinical intake field metadata.
//
// The coded options below use the SAME encodings the backend verified against
// the original UCI data (see backend/app/ml/clinical/features.py). These are
// NOT the encodings printed in most Kaggle column descriptions for this file —
// four of the five categoricals are remapped. Getting these wrong here would
// silently feed the model mislabelled categories, so they are kept in lockstep
// with the backend on purpose.

export interface NumericField {
  kind: "number";
  name: string;
  label: string;
  unit?: string;
  min: number;
  max: number;
  step?: number;
  hint?: string;
}

export interface SelectField {
  kind: "select";
  name: string;
  label: string;
  options: { value: number; label: string }[];
  hint?: string;
}

export type ClinicalField = NumericField | SelectField;

export const CLINICAL_FIELDS: ClinicalField[] = [
  { kind: "number", name: "age", label: "Age", unit: "years", min: 1, max: 120 },
  {
    kind: "select",
    name: "sex",
    label: "Sex",
    options: [
      { value: 0, label: "Female" },
      { value: 1, label: "Male" },
    ],
  },
  {
    kind: "select",
    name: "cp",
    label: "Chest pain type",
    options: [
      { value: 0, label: "Asymptomatic" },
      { value: 1, label: "Atypical angina" },
      { value: 2, label: "Non-anginal pain" },
      { value: 3, label: "Typical angina" },
    ],
  },
  {
    kind: "number",
    name: "trestbps",
    label: "Resting blood pressure",
    unit: "mm Hg",
    min: 60,
    max: 260,
    hint: "Systolic, measured at rest",
  },
  { kind: "number", name: "chol", label: "Serum cholesterol", unit: "mg/dl", min: 80, max: 700 },
  {
    kind: "select",
    name: "fbs",
    label: "Fasting blood sugar > 120 mg/dl",
    options: [
      { value: 0, label: "No (≤ 120 mg/dl)" },
      { value: 1, label: "Yes (> 120 mg/dl)" },
    ],
  },
  {
    kind: "select",
    name: "restecg",
    label: "Resting ECG finding",
    options: [
      { value: 0, label: "Left ventricular hypertrophy" },
      { value: 1, label: "Normal" },
      { value: 2, label: "ST-T wave abnormality" },
    ],
  },
  {
    kind: "number",
    name: "thalach",
    label: "Peak heart rate reached",
    unit: "bpm",
    min: 50,
    max: 230,
  },
  {
    kind: "select",
    name: "exang",
    label: "Angina brought on by exertion",
    options: [
      { value: 0, label: "No" },
      { value: 1, label: "Yes" },
    ],
  },
  {
    kind: "number",
    name: "oldpeak",
    label: "ST-segment depression",
    unit: "mm",
    min: 0,
    max: 10,
    step: 0.1,
    hint: "ST depression induced by exercise relative to rest",
  },
  {
    kind: "select",
    name: "slope",
    label: "ST-segment slope during exercise",
    options: [
      { value: 0, label: "Downsloping" },
      { value: 1, label: "Flat" },
      { value: 2, label: "Upsloping" },
    ],
  },
  {
    kind: "select",
    name: "ca",
    label: "Major vessels seen on fluoroscopy",
    options: [
      { value: 0, label: "0" },
      { value: 1, label: "1" },
      { value: 2, label: "2" },
      { value: 3, label: "3" },
    ],
    hint: "Number coloured by fluoroscopy (0–3)",
  },
  {
    kind: "select",
    name: "thal",
    label: "Thallium stress-test result",
    options: [
      { value: 1, label: "Fixed defect" },
      { value: 2, label: "Normal" },
      { value: 3, label: "Reversible defect" },
    ],
  },
];

// Sensible demo defaults (a low-risk-leaning profile) so a rehearsal or judge
// can run a screening in a couple of clicks without typing 13 fields.
export const DEMO_NORMAL: Record<string, number> = {
  age: 41, sex: 0, cp: 2, trestbps: 118, chol: 190, fbs: 0, restecg: 1,
  thalach: 172, exang: 0, oldpeak: 0, slope: 2, ca: 0, thal: 2,
};

export const DEMO_CONCERNING: Record<string, number> = {
  age: 67, sex: 1, cp: 0, trestbps: 160, chol: 286, fbs: 0, restecg: 0,
  thalach: 108, exang: 1, oldpeak: 1.5, slope: 1, ca: 3, thal: 3,
};
