// Factual reference content for the 13 clinical features CardioSense uses.
// Sourced from standard cardiology references and the UCI Heart Disease dataset
// documentation. This is educational context for health workers — not medical
// advice, and not model output.

export interface FeatureReference {
  field: string;
  name: string;
  what: string;
  whyItMatters: string;
  typical: string;
}

export const FEATURE_REFERENCE: FeatureReference[] = [
  {
    field: "age",
    name: "Age",
    what: "The patient's age in years.",
    whyItMatters:
      "Cardiovascular risk rises steadily with age as arteries stiffen and plaque accumulates. It is one of the strongest non-modifiable risk factors.",
    typical: "Screened range in this tool: 1–120 years.",
  },
  {
    field: "sex",
    name: "Sex",
    what: "Biological sex (male/female).",
    whyItMatters:
      "Men develop coronary disease earlier on average; women's risk rises after menopause. Symptoms can also present differently between sexes.",
    typical: "Recorded as male or female.",
  },
  {
    field: "cp",
    name: "Chest pain type",
    what: "Category of chest pain: typical angina, atypical angina, non-anginal pain, or asymptomatic.",
    whyItMatters:
      "Typical angina (predictable, exertional chest pain relieved by rest) is more strongly associated with coronary disease. Asymptomatic presentation is common and easily missed.",
    typical: "4 categories.",
  },
  {
    field: "trestbps",
    name: "Resting blood pressure",
    what: "Systolic blood pressure measured at rest, in mm Hg.",
    whyItMatters:
      "Sustained high blood pressure damages arterial walls and strains the heart, accelerating atherosclerosis.",
    typical: "Normal < 120; hypertension ≥ 140 systolic.",
  },
  {
    field: "chol",
    name: "Serum cholesterol",
    what: "Total serum cholesterol in mg/dl.",
    whyItMatters:
      "Elevated cholesterol contributes to plaque build-up in coronary arteries. LDL fractions matter most, but total cholesterol is a useful screening proxy.",
    typical: "Desirable < 200; high ≥ 240 mg/dl.",
  },
  {
    field: "fbs",
    name: "Fasting blood sugar",
    what: "Whether fasting blood sugar exceeds 120 mg/dl.",
    whyItMatters:
      "Elevated fasting glucose signals diabetes or pre-diabetes, both of which substantially raise cardiovascular risk.",
    typical: "Flagged when > 120 mg/dl.",
  },
  {
    field: "restecg",
    name: "Resting ECG finding",
    what: "Resting electrocardiogram result: normal, ST-T wave abnormality, or left ventricular hypertrophy.",
    whyItMatters:
      "Abnormal resting ECG patterns can indicate prior injury, strain, or thickening of the heart muscle.",
    typical: "3 categories.",
  },
  {
    field: "thalach",
    name: "Peak heart rate achieved",
    what: "Maximum heart rate reached during exercise testing, in bpm.",
    whyItMatters:
      "A lower-than-expected peak heart rate can indicate reduced cardiac reserve or chronotropic incompetence. Higher achievable rates are generally healthier.",
    typical: "Roughly 220 minus age at maximum effort.",
  },
  {
    field: "exang",
    name: "Exercise-induced angina",
    what: "Whether exertion brings on angina (chest pain).",
    whyItMatters:
      "Angina triggered by exercise strongly suggests the heart isn't getting enough blood under demand — a hallmark of coronary narrowing.",
    typical: "Yes / No.",
  },
  {
    field: "oldpeak",
    name: "ST depression (oldpeak)",
    what: "ST-segment depression induced by exercise relative to rest, in mm.",
    whyItMatters:
      "Greater ST depression during stress indicates more significant myocardial ischaemia (oxygen shortage).",
    typical: "< 1.0 mm is generally reassuring.",
  },
  {
    field: "slope",
    name: "ST-segment slope",
    what: "The slope of the peak-exercise ST segment: upsloping, flat, or downsloping.",
    whyItMatters:
      "A flat or downsloping ST segment during exercise is more concerning for ischaemia than an upsloping one.",
    typical: "3 categories.",
  },
  {
    field: "ca",
    name: "Major vessels (fluoroscopy)",
    what: "Number of major coronary vessels (0–3) coloured by fluoroscopy.",
    whyItMatters:
      "More vessels showing disease on imaging indicates more extensive coronary artery involvement.",
    typical: "0–3 vessels.",
  },
  {
    field: "thal",
    name: "Thallium stress test",
    what: "Result of a thallium (nuclear) stress test: normal, fixed defect, or reversible defect.",
    whyItMatters:
      "A reversible defect suggests areas of the heart that are ischaemic under stress but still viable — an important marker of significant coronary disease.",
    typical: "3 categories.",
  },
];

export const CVD_FACTS: { stat: string; label: string; source: string }[] = [
  {
    stat: "~32%",
    label: "of global deaths are from cardiovascular disease — the leading cause worldwide",
    source: "World Health Organization",
  },
  {
    stat: "~80%",
    label: "of premature heart disease and stroke is considered preventable with early action",
    source: "World Heart Federation",
  },
  {
    stat: "3 in 4",
    label: "cardiovascular deaths occur in low- and middle-income countries",
    source: "World Health Organization",
  },
];
