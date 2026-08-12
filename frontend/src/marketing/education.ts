// Ten short patient-education blurbs, each tied to a field the clinical model
// uses. Written directly (not pulled from an API) so they read as product-
// specific and never fail during a demo.

export interface EducationBlurb {
  title: string;
  body: string;
}

export const EDUCATION: EducationBlurb[] = [
  {
    title: "Why blood pressure matters",
    body: "Sustained high pressure quietly stiffens and scars arteries for years before symptoms appear — which is why it's called the silent killer.",
  },
  {
    title: "What your cholesterol really means",
    body: "Excess cholesterol builds plaque inside coronary arteries, narrowing the path blood takes to feed your heart muscle.",
  },
  {
    title: "Fasting sugar and your heart",
    body: "Raised fasting glucose signals diabetes risk — and diabetes roughly doubles the chance of heart disease.",
  },
  {
    title: "Not all chest pain is the same",
    body: "Predictable pain on exertion that eases with rest is a very different signal from random, fleeting discomfort.",
  },
  {
    title: "What a resting ECG shows",
    body: "It captures the heart's electrical rhythm at rest — useful, but it can look normal even when disease is present.",
  },
  {
    title: "Peak heart rate during exercise",
    body: "How high your heart rate can safely climb under effort is a window into your cardiac reserve.",
  },
  {
    title: "Angina is a signal worth hearing",
    body: "Chest pain brought on by exercise often means the heart isn't getting enough blood when it's working hard.",
  },
  {
    title: "ST-segment depression, simply",
    body: "A dip in a specific part of the ECG trace during stress can reveal areas starved of oxygen.",
  },
  {
    title: "What a stress test measures",
    body: "It compares blood flow to the heart at rest versus under stress, exposing narrowed arteries a resting test misses.",
  },
  {
    title: "A screening signal, not a verdict",
    body: "CardioSense estimates risk to prompt the right next step. Only a clinician can diagnose — and that's by design.",
  },
];
